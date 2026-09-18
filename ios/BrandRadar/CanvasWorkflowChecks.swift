#if DEBUG
import Foundation

@MainActor enum CanvasWorkflowChecks {
    static func run() throws -> [String] {
        var passed: [String] = []
        func expect(_ value: @autoclosure () -> Bool, _ label: String) throws {
            guard value() else { throw CanvasContentChecks.Failure(message: label) }
            passed.append(label)
        }
        let suite = "com.keyuanshi.brandradar.workflowchecks.\(UUID().uuidString)"
        let preferences = UserDefaults(suiteName: suite)!
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("workflowchecks-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let store = BoardStore(testDirectory: directory, preferences: preferences)
        defer { store.persist(); preferences.removePersistentDomain(forName: suite); try? FileManager.default.removeItem(at: directory) }
        var board = BoardTemplate.blank.make()
        board.workspaceMode = .practice
        board.cards = [RadarCard(id: "a", title: "原标题", body: "原正文"), RadarCard(id: "b", title: "另一个方向", body: "保留"), RadarCard(id: "c", title: "子组内容", body: "第三张")]
        board.groups = [RadarGroup(id: "parent", title: "整个活动", cardIDs: ["a"], groupIDs: ["child"]), RadarGroup(id: "child", title: "执行", cardIDs: ["b", "c"])]
        board.composerDraft = "还没发送的原话"
        store.mode = .practice; store.boards = [board]; store.selectedID = board.id
        store.selectedCardID = "removed-target"
        let messageCount = store.current.messages.count
        store.send("不要丢掉草稿")
        try expect(!store.chatTargetIsValid && store.current.composerDraft == "还没发送的原话" && store.current.messages.count == messageCount && store.busyBoardID == nil, "B03 invalid target rejects send without changing draft or messages")
        try expect(store.error != nil, "B03 invalid target offers an explicit recovery message")
        store.selectedCardID = "parent"
        try expect(store.chatTargetIsValid && store.chatTargetLabel.contains("整个活动") && store.chatTargetLabel.contains("3 张卡片"), "B03 group target counts descendant cards recursively")
        store.selectedCardID = nil
        let base = store.current
        try expect(store.beginVoiceSession(), "B06 isolated real editing session begins without networking")
        var changed = base.cards[0]; changed.title = "AI标题"; changed.body = "AI正文"
        let result = DirectAgentResult(cards: [changed], edges: [], removeIDs: [], removeEdgeIDs: [], summary: "已修改")
        try expect(store.acceptTestUpdate(result, base: base), "B06 real generated update enters the store")
        store.sealTestSession()
        guard let sessionID = store.current.editHistory?.last?.id else { throw CanvasContentChecks.Failure(message: "B06 missing generated session history") }
        try expect(store.current.cards[0].title == "AI标题" && store.current.cards[0].body == "AI正文", "B06 generated changes exist before conditional undo")
        store.update { current in current.cards[0].title = "人的后续标题"; current.cards[0].color = "rose"; current.cards[1].body = "人的另一张修改" }
        let manualID = store.current.editHistory?.last?.id
        store.undoChanges(sessionID: sessionID)
        try expect(store.current.cards[0].title == "人的后续标题" && store.current.cards[0].color == "rose" && store.current.cards[0].body == "原正文" && store.current.cards[1].body == "人的另一张修改", "B06 undo one AI session preserves later human fields and other cards")
        try expect(!((store.current.editHistory ?? []).contains { $0.id == sessionID }) && store.current.editHistory?.contains(where: { $0.id == manualID }) == true, "B06 targeted undo retains the later manual history entry")
        let additionBase = store.current
        try expect(store.beginVoiceSession(), "B06 new-node session begins")
        let newNode = RadarCard(id: "agent-added", title: "新增方向", body: "新内容")
        try expect(store.acceptTestUpdate(DirectAgentResult(cards: [newNode], edges: [], removeIDs: [], removeEdgeIDs: [], summary: ""), base: additionBase), "B06 added node is applied")
        store.sealTestSession()
        let additionSession = store.current.editHistory!.last!.id
        store.update { current in
            current.edges.append(RadarEdge(id: "human-edge", fromID: newNode.id, toID: "a", label: "人的新关系"))
            current.groups?[1].cardIDs.append(newNode.id)
        }
        store.undoChanges(sessionID: additionSession)
        try expect(store.current.cards.contains(where: { $0.id == newNode.id }) && store.current.edges.contains(where: { $0.id == "human-edge" }) && store.current.groups?[1].cardIDs.contains(newNode.id) == true, "B06 targeted undo preserves nodes now used by later human relationships")
        var grouped = BoardTemplate.blank.make()
        grouped.cards = [RadarCard(id: "root", title: "旧卡", body: "")]
        let ungrouped = grouped
        grouped.groups = [RadarGroup(id: "new-group", title: "AI分组", cardIDs: [])]
        let groupDelta = CanvasHistory.diff(ungrouped, grouped)
        grouped.edges = [RadarEdge(id: "later-group-edge", fromID: "root", toID: "new-group", label: "后来关联")]
        CanvasHistory.apply(groupDelta, to: &grouped, backwards: true)
        try expect(grouped.groups?.contains(where: { $0.id == "new-group" }) == true && grouped.edges.count == 1, "B06 undo preserves groups used by later human connections")
        var other = BoardTemplate.blank.make(); other.workspaceMode = .practice; other.composerDraft = "另一张草稿"
        store.boards.append(other); store.selectedID = other.id
        store.appendDictation("  补充口述  ", boardID: board.id)
        try expect(store.boards.first(where: { $0.id == board.id })?.composerDraft == "还没发送的原话\n补充口述" && store.current.composerDraft == "另一张草稿", "B04 dictation appends to captured board without changing the active board draft")
        store.appendDictation(" \n ", boardID: board.id)
        store.appendDictation("不存在的目标", boardID: "missing-board")
        try expect(store.current.composerDraft == "另一张草稿" && store.boards[0].composerDraft == "还没发送的原话\n补充口述", "B04 empty or missing-board dictation cannot erase or reroute a draft")
        store.selectedID = board.id
        let beforeFocus = store.current
        store.focusNode("a")
        try expect(store.selectedCardID == "a" && store.current.updated == beforeFocus.updated && store.current.cards == beforeFocus.cards && store.current.edges == beforeFocus.edges && store.current.groups == beforeFocus.groups, "B06 explicit focus changes viewport without touching content or modified time")
        store.persist()
        let reopened = BoardStore(testDirectory: directory, preferences: preferences)
        try expect(reopened.boards.first(where: { $0.id == board.id })?.composerDraft == "还没发送的原话\n补充口述" && reopened.boards.first(where: { $0.id == other.id })?.composerDraft == "另一张草稿", "B04 separate board drafts survive real file reload")
        return passed
    }
}
#endif
