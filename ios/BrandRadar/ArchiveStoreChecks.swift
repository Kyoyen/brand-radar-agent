#if DEBUG
import Foundation

@MainActor enum ArchiveStoreChecks {
    static func run(store: BoardStore) throws -> [String] {
        var passed: [String] = []
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) throws {
            guard condition() else { throw CanvasContentChecks.Failure(message: label) }
            passed.append(label)
        }
        var board = BoardTemplate.blank.make()
        board.cards = [RadarCard(id: "a", title: "A", body: ""), RadarCard(id: "b", title: "B", body: "正文", status: "kept"), RadarCard(id: "c", title: "C", body: "")]
        board.edges = [RadarEdge(id: "ab", fromID: "a", toID: "b", label: "起点"), RadarEdge(id: "bc", fromID: "b", toID: "c", label: "继续")]
        board.groups = [RadarGroup(id: "g", title: "分组", cardIDs: ["a", "b", "c"])]
        store.importCanvas(board)
        var draft = store.current.cards[1]; draft.status = "archived"
        try expect(store.editCard(draft), "A05 Store archives with relationships")
        try expect(store.current.cards[1].archiveRecord?.edges.count == 2 && store.current.edges.isEmpty, "A05 archived graph recorded atomically")
        let saved = try JSONDecoder().decode(RadarBoard.self, from: JSONEncoder().encode(store.current))
        store.importCanvas(saved)
        draft = store.current.cards[1]; draft.status = "draft"
        try expect(store.editCard(draft), "A06 Store restores decoded archived document")
        try expect(store.current.edges.count == 2 && store.current.groups?[0].cardIDs == ["a", "b", "c"] && store.current.cards[1].status == "kept", "A06 restored edges group and adopted state")
        store.undo()
        try expect(store.current.cards[1].status == "archived" && store.current.edges.isEmpty, "A08 undo restore returns to archived state")
        store.redo()
        try expect(store.current.edges.count == 2 && Set(store.current.edges.map(\.id)).count == 2, "A08 redo restore does not duplicate edges")
        store.importCanvas(board)
        let base = store.current
        _ = store.beginVoiceSession()
        let removed = DirectAgentResult(cards: [], edges: [], removeIDs: ["b"], removeEdgeIDs: [], summary: "")
        try expect(store.acceptTestUpdate(removed, base: base), "Agent archive update accepted")
        store.sealTestSession()
        try expect(store.current.cards[1].archiveRecord?.edges.count == 2, "Agent archive uses same recoverable relation record")
        draft = store.current.cards[1]; draft.status = "draft"
        try expect(store.editCard(draft) && store.current.edges.count == 2, "Agent-archived card can restore full graph")
        return passed
    }
}
#endif
