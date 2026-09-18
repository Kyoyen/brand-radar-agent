#if DEBUG
import Foundation

/// Isolated local data for UI acceptance. Never executes in ordinary launches or release builds.
@MainActor enum CanvasUITestFixtures {
    private static var installed = false
    private static var scheduledReply = false
    static func install(in store: BoardStore) {
        let arguments = ProcessInfo.processInfo.arguments
        guard arguments.contains("--uitesting"), !installed else { return }
        installed = true
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
