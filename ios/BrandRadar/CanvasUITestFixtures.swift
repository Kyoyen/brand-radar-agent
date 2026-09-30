#if DEBUG
import Foundation
import PencilKit
import UIKit

/// Isolated local data for UI acceptance. Never executes in ordinary launches or release builds.
@MainActor enum CanvasUITestFixtures {
    private static var installed = false
    private static var scheduledReply = false
    private static var syntheticSpeechScheduled = false
    static func install(in store: BoardStore) {
        let arguments = ProcessInfo.processInfo.arguments
        if arguments.contains("--live-acceptance"), arguments.contains("--live-acceptance-material") {
            installSyntheticMaterial(in: store)
            return
        }
        guard arguments.contains("--uitesting"), !installed else { return }
        installed = true
        if arguments.contains("--uitesting-overview") {
            var overview = DemoCanvas.seed()
            overview.id = "overview_fixture"
            overview.offsetX = 90; overview.offsetY = 300; overview.zoom = 0.27
            store.boards = [overview]
            store.selectedID = overview.id
            store.persist()
        }
        if arguments.contains("--uitesting-library") {
            store.boards = (0..<12).map { index in
                var board = DemoCanvas.seed()
                board.id = "library_\(index)"
                board.title = index == 7 ? "湖畔方案" : "方案 \(index + 1)"
                board.updated = Date(timeIntervalSince1970: 1_789_000_000 - Double(index) * 3600)
                if index == 4 { board.cards[0].body = "蓝色风筝在湖边飞起"; board.cards[0].blocks = [CanvasBlock(text: "蓝色风筝在湖边飞起")] }
                return board
            }
            store.mode = .demo; store.selectedID = store.boards[0].id; store.persist()
        }
        if arguments.contains("--uitesting-chat-history") {
            store.update { board in
                board.messages = (0..<40).map { index in
                    RadarMessage(id: "history_\(index)", role: index.isMultiple(of: 2) ? "user" : "assistant", content: "历史第 \(index + 1) 轮：这一段保留原来的表达，讨论周末活动、共同物料和下一步安排。")
                }
            }
        }
    }
    /// Synthetic input material only. Generation still uses BoardStore and the configured real API.
    private static func installSyntheticMaterial(in store: BoardStore) {
        guard !installed else { return }
        installed = true
        let image = UIGraphicsImageRenderer(size: CGSize(width: 320, height: 200)).image { context in
            UIColor.white.setFill(); context.fill(CGRect(x: 0, y: 0, width: 320, height: 200))
            ("PLUM" as NSString).draw(at: CGPoint(x: 15, y: 76), withAttributes: [.font: UIFont.boldSystemFont(ofSize: 32)])
            ("→" as NSString).draw(at: CGPoint(x: 135, y: 72), withAttributes: [.font: UIFont.boldSystemFont(ofSize: 43)])
            ("ORBIT" as NSString).draw(at: CGPoint(x: 195, y: 76), withAttributes: [.font: UIFont.boldSystemFont(ofSize: 30)])
        }
        func stroke(_ locations: [CGPoint]) -> PKStroke {
            let points = locations.enumerated().map { index, point in
                PKStrokePoint(location: point, timeOffset: Double(index) * 0.05, size: CGSize(width: 12, height: 12), opacity: 1, force: 1, azimuth: 0, altitude: .pi / 2)
            }
            return PKStroke(ink: PKInk(.pen, color: .black), path: PKStrokePath(controlPoints: points, creationDate: Date()))
        }
        do {
            let photo = try CanvasAssets.shared.importPhotoData(image.pngData()!)
            let sketch = try CanvasAssets.shared.saveDrawing(PKDrawing(strokes: [
                stroke([CGPoint(x: 90, y: 210), CGPoint(x: 220, y: 210), CGPoint(x: 130, y: 380)]),
                stroke([CGPoint(x: 535, y: 210), CGPoint(x: 635, y: 210), CGPoint(x: 645, y: 290), CGPoint(x: 540, y: 290), CGPoint(x: 535, y: 210)]),
                stroke([CGPoint(x: 645, y: 290), CGPoint(x: 570, y: 380)]),
                stroke([CGPoint(x: 275, y: 290), CGPoint(x: 475, y: 290)]),
                stroke([CGPoint(x: 425, y: 255), CGPoint(x: 475, y: 290), CGPoint(x: 425, y: 325)])
            ]))
            var card = RadarCard(title: "合成图片与手绘素材", body: "两份独立的视觉材料。请按看得清的内容整理，无法辨认的部分保留为问题。", x: 40, y: 80)
            card.blocks = [CanvasBlock(kind: "text", text: card.body), CanvasBlock(kind: "image", attachment: photo), CanvasBlock(kind: "drawing", attachment: sketch)]
            var board = BoardTemplate.blank.make()
            board.workspaceMode = .practice; board.cards = [card]
            board.title = ProcessInfo.processInfo.arguments.contains("--live-acceptance-synthetic-speech") ? "合成分段口述验收" : "合成视觉材料验收"
            if store.mode != .practice { store.setMode(.practice) }
            store.boards.insert(board, at: 0); store.select(board); store.persist()
        } catch { store.error = "合成视觉验收材料创建失败。" }
    }
    /// Opt-in acceptance input: simulated recognized text, not microphone or speech recognition.
    /// The production voice Store and configured API process both revisions.
    static func startSyntheticSpeechIfRequested(in store: BoardStore) {
        let arguments = ProcessInfo.processInfo.arguments
        guard arguments.contains("--live-acceptance"), arguments.contains("--live-acceptance-synthetic-speech"),
              !syntheticSpeechScheduled else { return }
        syntheticSpeechScheduled = true
        let start = Date()
        let originalCount = store.current.visibleCards.count
        Task { @MainActor [weak store] in
            guard let store, store.beginVoiceSession(requiresConfirmation: true) else { return }
            store.receiveVoice("请创建一个周末活动主题节点。")
            var firstUpdateSeconds: Double?
            for _ in 0..<1200 {
                if (store.voiceSession?.sequence ?? 0) > 0, store.busyBoardID == nil {
                    firstUpdateSeconds = Date().timeIntervalSince(start)
                    break
                }
                if store.voiceSession == nil || store.voiceAwaitingReview { break }
                try? await Task.sleep(for: .milliseconds(100))
            }
            let firstSequence = store.voiceSession?.sequence ?? 0
            let firstCount = store.current.visibleCards.count
            if firstUpdateSeconds != nil, store.voiceSession != nil, !store.voiceAwaitingReview {
                store.finishVoiceSession("请创建一个周末活动主题节点。再增加一张执行卡片，并连到主题节点。")
            } else { store.interruptVoiceSession() }
            for _ in 0..<2500 {
                if store.voiceAwaitingReview || store.voiceSession == nil { break }
                try? await Task.sleep(for: .milliseconds(100))
            }
            let evidence: [String: Any] = [
                "input": "synthetic recognized text; microphone and ASR bypassed",
                "firstValidUpdateSeconds": firstUpdateSeconds as Any? ?? NSNull(),
                "firstBatchSequence": firstSequence,
                "finalSequence": store.voiceSession?.sequence ?? 0,
                "initialCardCount": originalCount,
                "firstBatchCardCount": firstCount,
                "finalCardCount": store.current.visibleCards.count,
                "awaitingReview": store.voiceAwaitingReview,
                "elapsedSeconds": Date().timeIntervalSince(start)
            ]
            let url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("live-acceptance-evidence.json")
            if let data = try? JSONSerialization.data(withJSONObject: evidence, options: [.prettyPrinted, .sortedKeys]) { try? data.write(to: url, options: .atomic) }
        }
    }
    static func scheduleHistoryReply(in store: BoardStore) {
        guard ProcessInfo.processInfo.arguments.contains("--uitesting-chat-history"), !scheduledReply else { return }
        scheduledReply = true
        let boardID = store.selectedID
        Task { @MainActor [weak store] in
            try? await Task.sleep(for: .seconds(8))
            guard let store else { return }
            store.update(boardID) { $0.messages.append(RadarMessage(id: "history_new_reply", role: "assistant", content: "新回复：继续补充了刚才的安排。")) }
        }
    }
}
#endif
