import SwiftUI
import UniformTypeIdentifiers

@main struct BrandRadarApp: App {
    @StateObject private var store = BoardStore()
    var body: some Scene {
        WindowGroup {
            WorkspaceView().environmentObject(store)
                .tint(Color(red: 0.24, green: 0.39, blue: 0.25))
                .preferredColorScheme(.light)
                .onOpenURL { url in
                    if url.isFileURL { do { store.importCanvas(try CanvasExport.importPackage(url)) } catch { store.error = error.localizedDescription } }
                    else { Task { await store.handleURL(url) } }
                }
                .task {
                    #if DEBUG
                    if ProcessInfo.processInfo.arguments.contains("--canvas-selfcheck") {
                        let result = CanvasAcceptance.run(store: store)
                        let url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("canvas-checks.json")
                        try? JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
                    }
                    #endif
                    await store.checkConnection()
                }
        }
    }
}

struct WorkspaceView: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.scenePhase) private var scenePhase
    @State private var sheet: WorkspaceSheet?
    @State private var editingCard: RadarCard?
    @State private var sharing: ShareContent?
    @State private var renaming = false
    @State private var boardName = ""
    @State private var importingCanvas = false
    @StateObject private var dockSpeech = SpeechInput()
    @State private var holdingVoice = false
    @State private var cancellingVoice = false
    @State private var voiceBoardID: String?
    private let ink = Color(red: 0.14, green: 0.19, blue: 0.14)
    var body: some View {
        ZStack {
            InfiniteCanvas(store: store) { id in
                editingCard = store.current.cards.first { $0.id == id }
            }.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                HStack {
                    Text("\(store.current.visibleCards.count) 张卡片").font(.system(size: 10)).accessibilityIdentifier("cardCountLabel")
                    Spacer()
                }.foregroundStyle(.secondary).padding(.horizontal, 25).padding(.top, 10)
                Spacer()
                if store.current.visibleCards.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "scribble.variable").font(.system(size: 46, weight: .ultraLight))
                        Text("想法还没有边界").font(.system(size: 26, weight: .medium))
                        Text("写一点，或聊一聊。") .font(.subheadline).foregroundStyle(.secondary)
                        Button("选个模板") { sheet = .templates }.buttonStyle(.borderedProminent)
                    }.padding(.bottom, 50)
                    Spacer()
                }
                if let from = store.linkingFrom {
                    HStack {
                        Image(systemName: "arrow.triangle.branch")
                        Text("点另一张卡片，建立关系").font(.subheadline)
                        Button("取消") { store.linkingFrom = nil }
                    }.padding(14).background(.regularMaterial, in: Capsule()).padding(.bottom, 12)
                    .accessibilityIdentifier("linking_\(from)")
                }
                HStack {
                    HStack(spacing: 15) {
                        Button { store.fitRequest += 1 } label: { Image(systemName: "arrow.up.left.and.arrow.down.right") }
                            .accessibilityLabel("查看全貌").accessibilityIdentifier("fitButton")
                        Text(String(format: store.current.zoom < 0.1 ? "%.1f%%" : "%.0f%%", store.current.zoom * 100)).font(.system(size: 11, weight: .medium, design: .monospaced)).frame(minWidth: 35).accessibilityIdentifier("zoomLabel")
                    }.padding(.horizontal, 17).frame(height: 44).background(.regularMaterial, in: Capsule())
                    Spacer()
                    Button { store.addNote() } label: { Image(systemName: "plus").font(.system(size: 21, weight: .medium)).frame(width: 46, height: 46) }
                        .background(.regularMaterial, in: Circle()).accessibilityLabel("添加便签").accessibilityIdentifier("addNoteButton")

                }.padding(.horizontal, 22).padding(.bottom, 15)
                chatDock
            }
        }
        .foregroundStyle(ink)
        .sheet(item: $sheet) { item in
            switch item {
            case .templates: TemplateSheet().environmentObject(store)
            case .chat: ChatSheet().environmentObject(store)
            case .settings: ConnectionSheet().environmentObject(store)
            case .boards: BoardLibrary().environmentObject(store)
            case .relations: RelationsSheet().environmentObject(store)
            }
        }
        .sheet(item: $editingCard) { card in CardEditor(card: card).environmentObject(store) }
        .sheet(item: $sharing) { content in ShareSheet(items: content.items) }
        .alert("需要留意", isPresented: Binding(get: { store.error != nil && sheet == nil && editingCard == nil }, set: { if !$0 { store.error = nil } })) {
            Button("知道了", role: .cancel) { store.error = nil }
        } message: { Text(store.error ?? "") }
        .alert("给画布起个名字", isPresented: $renaming) {
            TextField("画布名称", text: $boardName)
            Button("保存") { store.renameBoard(boardName) }
            Button("取消", role: .cancel) {}
        }
        .fileImporter(isPresented: $importingCanvas, allowedContentTypes: [.data, .item]) { result in
            do { let url = try result.get(); store.importCanvas(try CanvasExport.importPackage(url)) }
            catch { store.error = error.localizedDescription }
        }
        .onDisappear { interruptDockVoice() }
        .onChange(of: sheet) { _, value in if value != nil { interruptDockVoice() } }
        .onChange(of: editingCard?.id) { _, value in if value != nil { interruptDockVoice() } }
        .onChange(of: sharing?.id) { _, value in if value != nil { interruptDockVoice() } }
        .onChange(of: renaming) { _, value in if value { interruptDockVoice() } }
        .onChange(of: store.selectedID) { _, _ in interruptDockVoice() }

        .onChange(of: dockSpeech.transcript) { _, text in if voiceBoardID != nil { store.receiveVoice(text) } }
        .onChange(of: dockSpeech.error) { _, value in if let value { store.interruptVoiceSession(); holdingVoice = false; voiceBoardID = nil; store.error = value } }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { interruptDockVoice(); store.interruptVoiceSession(); store.persist() }
            else { Task { await store.checkConnection() } }
        }
    }
    private var header: some View {
        HStack(spacing: 12) {
            Button { sheet = .boards } label: {
                Image(systemName: "square.stack.3d.up").font(.system(size: 19)).frame(width: 43, height: 43)
            }.background(.white.opacity(0.82), in: Circle()).accessibilityLabel("我的画布").accessibilityIdentifier("boardsButton")
            VStack(alignment: .leading, spacing: 3) {
                Text("BRAND RADAR").font(.system(size: 9, weight: .bold, design: .monospaced)).tracking(2.4)
                Text(store.current.title).font(.system(size: 16, weight: .semibold)).lineLimit(1).accessibilityIdentifier("boardTitle")
            }
            Spacer(minLength: 0)
            Menu {
                Button("重命名画布", systemImage: "pencil") { boardName = store.current.title; renaming = true }
                Button("整理画布", systemImage: "rectangle.3.group") { store.arrange() }
                Button("管理连接关系", systemImage: "arrow.triangle.branch") { sheet = .relations }
                if store.mode == .practice && store.transport == .mac {
                    Button("刷新画布", systemImage: "arrow.clockwise") { Task { await store.refresh() } }
                }
                Button("撤销", systemImage: "arrow.uturn.backward") { store.undo() }.disabled(!store.canUndo)
                Button("重做", systemImage: "arrow.uturn.forward") { store.redo() }.disabled(!store.canRedo)
                Button("导出图片", systemImage: "photo") { exportCanvas("png") }
                Button("导出 PDF", systemImage: "doc") { exportCanvas("pdf") }
                Button("分享可编辑画布", systemImage: "square.and.arrow.up") { exportCanvas("package") }
                Button("导入画布", systemImage: "square.and.arrow.down") { importingCanvas = true }
            } label: { Image(systemName: "ellipsis").frame(width: 36, height: 43) }.accessibilityLabel("画布操作")
            Button { sheet = .settings } label: { Image(systemName: "antenna.radiowaves.left.and.right").font(.system(size: 18)).frame(width: 35, height: 43) }
                .accessibilityLabel("连接设置").accessibilityIdentifier("settingsButton")
        }.padding(.horizontal, 18).padding(.top, 10)
    }
    private func selectionBar(_ card: RadarCard) -> some View {
        HStack(spacing: 20) {
            Button { editingCard = card } label: { Label("编辑", systemImage: "pencil") }.accessibilityIdentifier("editCardButton")
            Button { store.linkingFrom = card.id } label: { Label("连接", systemImage: "arrow.triangle.branch") }
            Button { sheet = .chat } label: { Label("聊这张", systemImage: "sparkles") }
            Button { store.selectedCardID = nil } label: { Image(systemName: "xmark") }.accessibilityLabel("取消选择")
        }.font(.system(size: 12, weight: .medium)).padding(.horizontal, 18).frame(height: 48)
            .background(.regularMaterial, in: Capsule()).padding(.bottom, 13)
    }
    private var chatDock: some View {
        VStack(spacing: 0) {
            if holdingVoice || dockSpeech.finishing {
                HStack(spacing: 8) {
                    Image(systemName: cancellingVoice ? "xmark.circle" : "waveform")
                    Text(voiceTitle).font(.caption).accessibilityIdentifier("voiceState")
                    Spacer()
                    Button("取消") { cancelDockVoice() }.font(.caption).accessibilityIdentifier("cancelVoiceButton")
                }.foregroundStyle(cancellingVoice ? .secondary : .primary).padding(.horizontal, 19).padding(.top, 13)
            }
            if let clarification = store.clarification {
                Button { sheet = .chat } label: { Text(clarification).font(.caption).multilineTextAlignment(.leading).lineLimit(3) }.padding(.horizontal, 19).padding(.top, 12)
            }
            if store.voiceSession == nil, !(store.current.pendingSpeech ?? "").isEmpty {
                Button("继续整理刚才的话") { store.resumeVoice() }.font(.caption).padding(.top, 12)
            }
            if store.isRunning {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(store.activity).font(.caption).lineLimit(1)
                    Spacer()
                    Button("停止") { Task { await store.stop() } }.font(.caption)
                }.padding(.horizontal, 19).padding(.top, 13)
            }
            HStack(spacing: 12) {
                Button { sheet = .templates } label: {
                    Image(systemName: "square.grid.2x2").font(.system(size: 19)).frame(width: 42, height: 48)
                }.accessibilityLabel("画布模板").accessibilityIdentifier("templatesButton")
                Rectangle().fill(ink.opacity(0.12)).frame(width: 1, height: 25)
                HoldToTalkControl(title: voiceTitle, voiceEnabled: (holdingVoice || !store.isRunning) && !dockSpeech.finishing,
                                  active: holdingVoice || dockSpeech.finishing,
                                  onTap: { interruptDockVoice(); sheet = .chat },
                                  onBegin: beginDockVoice,
                                  onCancelChange: { cancellingVoice = $0 },
                                  onEnd: endDockVoice)
                    .frame(height: 48)

            }.padding(.horizontal, 13).padding(.vertical, 14)
        }.background(.white.opacity(0.96), in: RoundedRectangle(cornerRadius: 28))
            .overlay(RoundedRectangle(cornerRadius: 28).strokeBorder(.black.opacity(0.04)))
            .shadow(color: .black.opacity(0.06), radius: 18, y: 4)
            .padding(.horizontal, 16).padding(.bottom, 8)
    }
    private var voiceTitle: String {
        if cancellingVoice { return "松开取消" }
        if dockSpeech.finishing { return "正在转写…" }
        if dockSpeech.starting { return "正在准备…" }
        if holdingVoice { return "松开结束" }
        return "说出你的想法"
    }
    private func beginDockVoice() {
        guard !store.isRunning, !dockSpeech.finishing, store.beginVoiceSession() else { return }
        dockSpeech.transcript = ""
        holdingVoice = true; cancellingVoice = false; voiceBoardID = store.selectedID
        Task { @MainActor in
            guard holdingVoice else { return }
            await dockSpeech.start(requireOnDevice: store.mode == .demo)
        }
    }
    private func endDockVoice(_ cancelled: Bool) {
        guard holdingVoice else { return }
        holdingVoice = false; cancellingVoice = false
        guard !cancelled, let boardID = voiceBoardID else { cancelDockVoice(); return }
        dockSpeech.finish { text in
            voiceBoardID = nil
            let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard scenePhase == .active, store.selectedID == boardID else { store.interruptVoiceSession(); return }
            store.finishVoiceSession(text)
        }
    }
    private func cancelDockVoice() {
        holdingVoice = false; cancellingVoice = false; voiceBoardID = nil
        dockSpeech.stop(); store.cancelVoiceSession()
    }
    private func interruptDockVoice() {
        let wasRecording = voiceBoardID != nil || holdingVoice || dockSpeech.recording || dockSpeech.finishing
        holdingVoice = false; cancellingVoice = false; voiceBoardID = nil
        dockSpeech.stop()
        if wasRecording { store.interruptVoiceSession() }
    }
    private func exportCanvas(_ kind: String) {
        do {
            let url = try kind == "png" ? CanvasExport.png(board: store.current) : kind == "pdf" ? CanvasExport.pdf(board: store.current) : CanvasExport.package(board: store.current)
            sharing = ShareContent(items: [url])
        } catch { store.error = error.localizedDescription }
    }

}

enum WorkspaceSheet: String, Identifiable { case templates, chat, settings, boards, relations; var id: String { rawValue } }
struct ShareContent: Identifiable { let id = UUID(); let items: [Any] }
struct ShareSheet: UIViewControllerRepresentable {
    var items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
