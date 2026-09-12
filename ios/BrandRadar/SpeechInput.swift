import AVFoundation
import Speech
import SwiftUI

/// The audio thread and main actor exchange request ownership under a short lock.
private final class SpeechAudioRouter: @unchecked Sendable {
    private let lock = NSLock()
    private var target: SFSpeechAudioBufferRecognitionRequest?
    func route(to request: SFSpeechAudioBufferRecognitionRequest?) { lock.lock(); target = request; lock.unlock() }
    func append(_ buffer: AVAudioPCMBuffer) { lock.lock(); target?.append(buffer); lock.unlock() }
}

@MainActor final class SpeechInput: ObservableObject {
    @Published var recording = false
    @Published var starting = false
    @Published var finishing = false
    @Published var transcript = ""
    @Published var error: String?
    private let engine = AVAudioEngine()
    private let router = SpeechAudioRouter()
    private var recognizer: SFSpeechRecognizer?
    private var requests: [Int: SFSpeechAudioBufferRecognitionRequest] = [:]
    private var tasks: [Int: SFSpeechRecognitionTask] = [:]
    private var segments: [Int: String] = [:]
    private var segmentIndex = 0
    private var onDevice = false
    private var installedTap = false
    private var generation = UUID()
    private var rotationTask: Task<Void, Never>?
    private var finishTask: Task<Void, Never>?
    private var finishCallback: ((String) -> Void)?
    private var interruptionObserver: NSObjectProtocol?

    func start(requireOnDevice: Bool = false) async {
        guard !starting && !recording && !finishing else { return }
        stop(); transcript = ""; error = nil; segments = [:]; segmentIndex = 0
        let current = UUID(); generation = current; starting = true
        defer { if generation == current { starting = false } }
        let authorization = await withCheckedContinuation { continuation in SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) } }
        guard generation == current, !Task.isCancelled else { return }
        guard authorization == .authorized else { error = "请在系统设置中允许语音识别。"; return }
        let microphone = await withCheckedContinuation { continuation in AVAudioApplication.requestRecordPermission { continuation.resume(returning: $0) } }
        guard generation == current, !Task.isCancelled else { return }
        guard microphone else { error = "请在系统设置中允许麦克风。"; return }
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "zh-CN")), recognizer.isAvailable else { error = "语音识别暂时不可用。"; return }
        guard !requireOnDevice || recognizer.supportsOnDeviceRecognition else { error = "这台设备暂不支持离线中文听写。"; return }
        self.recognizer = recognizer; onDevice = requireOnDevice
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let node = engine.inputNode, format = engine.inputNode.outputFormat(forBus: 0)
            guard format.sampleRate > 0, format.channelCount > 0 else { throw NSError(domain: "Speech", code: 1, userInfo: [NSLocalizedDescriptionKey: "没有可用的麦克风。"]) }
            recording = true
            beginSegment(generation: current)
            let router = self.router
            node.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in router.append(buffer) }
            installedTap = true; engine.prepare(); try engine.start()
            interruptionObserver = NotificationCenter.default.addObserver(forName: AVAudioSession.interruptionNotification, object: session, queue: .main) { [weak self] notification in
                guard let value = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt, value == AVAudioSession.InterruptionType.began.rawValue else { return }
                Task { @MainActor in self?.error = "收音已中断，刚才的话已保留。"; self?.stop() }
            }
        } catch { self.error = error.localizedDescription; stop() }
    }
    private func beginSegment(generation current: UUID) {
        guard generation == current, recording, let recognizer else { return }
        let previous = segmentIndex; segmentIndex += 1; let index = segmentIndex
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true; request.requiresOnDeviceRecognition = onDevice
        request.addsPunctuation = true
        requests[index] = request; router.route(to: request)
        requests[previous]?.endAudio()
        tasks[index] = recognizer.recognitionTask(with: request) { [weak self] result, recognitionError in
            Task { @MainActor in
                guard let self, self.generation == current else { return }
                if let result {
                    self.segments[index] = result.bestTranscription.formattedString
                    self.transcript = self.segments.keys.sorted().compactMap { self.segments[$0] }.joined(separator: "\n")
                }
                if result?.isFinal == true || recognitionError != nil {
                    self.requests[index] = nil; self.tasks[index] = nil
                    if self.finishing, self.tasks.isEmpty { self.completeRecognition() }
                    else if self.recording, index == self.segmentIndex {
                        if recognitionError != nil && result == nil && (self.segments[index] ?? "").isEmpty {
                            self.error = "听写暂时中断，已识别的内容已保留。"; self.stop()
                        } else { self.beginSegment(generation: current) }
                    }
                }
            }
        }
        rotationTask?.cancel()
        rotationTask = Task { [weak self] in
            do { try await Task.sleep(for: .seconds(50)) } catch { return }
            guard let self, self.generation == current, self.recording, self.segmentIndex == index else { return }
            self.beginSegment(generation: current)
        }
        // Retire an old recognizer after its finalization window; the microphone stays running.
        if previous > 0 {
            Task { [weak self] in
                try? await Task.sleep(for: .seconds(3))
                guard let self, self.generation == current, previous < self.segmentIndex else { return }
                self.tasks.removeValue(forKey: previous)?.cancel(); self.requests[previous] = nil
            }
        }
    }
    func finish(onFinish: @escaping (String) -> Void) {
        if starting { stop(); onFinish(""); return }
        guard recording || finishing else { onFinish(transcript); return }
        guard !finishing else { return }
        finishCallback = onFinish; recording = false; finishing = true
        rotationTask?.cancel(); endAudio(); requests.values.forEach { $0.endAudio() }
        let current = generation
        finishTask = Task { [weak self] in
            do { try await Task.sleep(for: .seconds(2)) } catch { return }
            guard let self, self.generation == current else { return }; self.completeRecognition()
        }
    }
    func stop() {
        generation = UUID(); starting = false; recording = false; finishing = false
        finishTask?.cancel(); finishTask = nil; rotationTask?.cancel(); finishCallback = nil
        endAudio(); requests.values.forEach { $0.endAudio() }; tasks.values.forEach { $0.cancel() }
        requests = [:]; tasks = [:]
        if let interruptionObserver { NotificationCenter.default.removeObserver(interruptionObserver); self.interruptionObserver = nil }
    }
    private func endAudio() {
        router.route(to: nil); engine.stop()
        if installedTap { engine.inputNode.removeTap(onBus: 0); installedTap = false }
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
    private func completeRecognition() { let result = transcript, callback = finishCallback; stop(); callback?(result) }
}
