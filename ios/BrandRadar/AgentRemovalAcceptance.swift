#if DEBUG
import Foundation

@MainActor enum AgentRemovalAcceptance {
    struct Failure: Error { let label: String }
    static func run() throws -> [String] {
        var passed: [String] = []
        func expect(_ value: Bool, _ label: String) throws {
            guard value else { throw Failure(label: label) }
            passed.append(label)
        }
        let first = CanvasBlock(id: "paragraph_a", kind: "text", text: "第一段")
        let second = CanvasBlock(id: "paragraph_b", kind: "text", text: "第二段")
        var checklist = CanvasBlock(id: "todo", kind: "checklist", text: "待办")
        checklist.items = [CanvasChecklistItem(id: "item_a", text: "保留"), CanvasChecklistItem(id: "item_b", text: "删除")]
        var card = RadarCard(id: "draft", title: "工作稿", body: "第一段\n\n第二段")
        card.blocks = [first, second, checklist]
        let board = RadarBoard(title: "内容删除测试", question: "", template: "", cards: [card], edges: [])
        let removeCardPatch: [String: Any] = ["id": "draft", "remove_block_ids": ["paragraph_b"],
            "blocks": [["id": "todo", "kind": "checklist", "items": [["id": "item_a", "text": "保留"]]]]]
        let patch: [String: Any] = ["cards": [removeCardPatch], "edges": [], "remove_ids": [],
                                    "remove_edge_ids": [], "summary": "删除第二段与一项"]
        let proposal = try DirectAgent.validate(patch: patch, board: board, selectedID: nil).cards[0]
        try expect(proposal.blocks?.map(\.id) == ["paragraph_a", "todo"], "explicit block deletion removes only requested block")
        try expect(proposal.blocks?.last?.items.map(\.id) == ["item_a"], "checklist omission removes requested old item")
        var unknown = patch
        unknown["cards"] = [["id": "draft", "remove_block_ids": ["not_there"]]]
        do { _ = try DirectAgent.validate(patch: unknown, board: board, selectedID: nil); throw Failure(label: "unknown block ID accepted") }
        catch is DirectAgentError { passed.append("unknown block ID rejected") }
        var conflict = patch
        conflict["cards"] = [["id": "draft", "remove_block_ids": ["paragraph_b"],
            "blocks": [["id": "paragraph_b", "kind": "text", "text": "同时修改"]]]]
        do { _ = try DirectAgent.validate(patch: conflict, board: board, selectedID: nil); throw Failure(label: "same-batch remove and update accepted") }
        catch is DirectAgentError { passed.append("same-batch remove and update rejected") }
        var human = card
        human.blocks![1].text = "人刚修改的第二段"
        human.blocks![2].items[1].isChecked = true
        let merged = CanvasHistory.merge(proposal, base: card, current: human)
        try expect(merged.blocks?.first(where: { $0.id == "paragraph_b" })?.text == "人刚修改的第二段", "human-edited block survives model removal")
        try expect(merged.blocks?.last?.items.first(where: { $0.id == "item_b" })?.isChecked == true, "human-checked item survives model removal")
        let clean = CanvasHistory.merge(proposal, base: card, current: card)
        try expect(clean.blocks?.map(\.id) == ["paragraph_a", "todo"] && clean.blocks?.last?.items.map(\.id) == ["item_a"], "untouched block and item are removed")
        var after = board
        after.cards[0] = clean
        let changes = CanvasHistory.diff(board, after)
        CanvasHistory.apply(changes, to: &after, backwards: true)
        try expect(after.cards[0].blocks?.map(\.id) == ["paragraph_a", "paragraph_b", "todo"] && after.cards[0].blocks?.last?.items.map(\.id) == ["item_a", "item_b"], "undo restores deleted block and checklist item")
        func cardPatch(_ fields: [String: Any]) -> [String: Any] {
            ["cards": [fields], "edges": [], "remove_ids": [], "remove_edge_ids": [], "summary": "本批修改"]
        }
        var expected = board
        var actual = board
        actual.cards[0].title = "人工标题"
        let firstResult = try DirectAgent.validate(patch: cardPatch(["id": "draft", "title": "模型标题一", "body": "模型正文一"]), board: actual, selectedID: nil)
        let beforeFirst = actual
        actual.cards[0] = CanvasHistory.merge(firstResult.cards[0], base: expected.cards[0], current: actual.cards[0])
        BoardStore.advanceModelBase(firstResult, before: beforeFirst, board: &expected)
        let secondResult = try DirectAgent.validate(patch: cardPatch(["id": "draft", "body": "模型正文二"]), board: actual, selectedID: nil)
        let beforeSecond = actual
        actual.cards[0] = CanvasHistory.merge(secondResult.cards[0], base: expected.cards[0], current: actual.cards[0])
        BoardStore.advanceModelBase(secondResult, before: beforeSecond, board: &expected)
        try expect(expected.cards[0].title == card.title, "inherited live title does not erase protected request base")
        let thirdResult = try DirectAgent.validate(patch: cardPatch(["id": "draft", "title": "模型标题三", "body": "模型正文三"]), board: actual, selectedID: nil)
        actual.cards[0] = CanvasHistory.merge(thirdResult.cards[0], base: expected.cards[0], current: actual.cards[0])
        try expect(actual.cards[0].title == "人工标题" && actual.cards[0].body == "模型正文三", "three validated batches keep human title while allowing body edits")
        let nextTurnBase = actual.cards[0]
        let nextTurnResult = try DirectAgent.validate(patch: cardPatch(["id": "draft", "title": "下轮明确改题"]), board: actual, selectedID: nil)
        let nextTurn = CanvasHistory.merge(nextTurnResult.cards[0], base: nextTurnBase, current: actual.cards[0])
        try expect(nextTurn.title == "下轮明确改题", "new user turn may edit prior protected title")
        var blockExpected = board
        var blockActual = board
        blockActual.cards[0].blocks![1].text = "人工改第二段"
        for text in ["模型改第一段一", "模型改第一段二"] {
            let result = try DirectAgent.validate(patch: cardPatch(["id": "draft", "blocks": [["id": "paragraph_a", "kind": "text", "text": text]]]), board: blockActual, selectedID: nil)
            let before = blockActual
            blockActual.cards[0] = CanvasHistory.merge(result.cards[0], base: blockExpected.cards[0], current: blockActual.cards[0])
            BoardStore.advanceModelBase(result, before: before, board: &blockExpected)
        }
        try expect(blockActual.cards[0].blocks?.first?.text == "模型改第一段二" && blockActual.cards[0].blocks?[1].text == "人工改第二段", "two model block edits proceed beside a human-edited block")
        var listExpected = board
        var listActual = board
        listActual.cards[0].blocks![2].items[1].isChecked = true
        for text in ["模型改第一项一", "模型改第一项二"] {
            let result = try DirectAgent.validate(patch: cardPatch(["id": "draft", "blocks": [["id": "todo", "kind": "checklist", "items": [
                ["id": "item_a", "text": text], ["id": "item_b", "text": "删除"]]]]]), board: listActual, selectedID: nil)
            let before = listActual
            listActual.cards[0] = CanvasHistory.merge(result.cards[0], base: listExpected.cards[0], current: listActual.cards[0])
            BoardStore.advanceModelBase(result, before: before, board: &listExpected)
        }
        try expect(listActual.cards[0].blocks?.last?.items[0].text == "模型改第一项二" && listActual.cards[0].blocks?.last?.items[1].isChecked == true, "two model checklist edits preserve a human check mark")
        var humanAddedExpected = board
        var humanAddedActual = board
        humanAddedActual.cards[0].blocks!.append(CanvasBlock(id: "human_block", kind: "text", text: "人新加的段落"))
        let inherited = try DirectAgent.validate(patch: cardPatch(["id": "draft", "title": "模型改题"]), board: humanAddedActual, selectedID: nil)
        BoardStore.advanceModelBase(inherited, before: humanAddedActual, board: &humanAddedExpected)
        try expect(humanAddedExpected.cards[0].blocks?.contains(where: { $0.id == "human_block" }) == false, "human-created block is not absorbed into model base")
        let tryRemove = try DirectAgent.validate(patch: cardPatch(["id": "draft", "remove_block_ids": ["human_block"]]), board: humanAddedActual, selectedID: nil)
        humanAddedActual.cards[0] = CanvasHistory.merge(tryRemove.cards[0], base: humanAddedExpected.cards[0], current: humanAddedActual.cards[0])
        try expect(humanAddedActual.cards[0].blocks?.contains(where: { $0.id == "human_block" }) == true, "later model batch cannot remove human-created block")
        var humanCardExpected = board
        var humanCardActual = board
        humanCardActual.cards.append(RadarCard(id: "human_new_card", title: "人新建", body: "", x: 400, y: 0))
        let inheritedCard = try DirectAgent.validate(patch: cardPatch(["id": "human_new_card", "title": "模型想改"]), board: humanCardActual, selectedID: nil)
        BoardStore.advanceModelBase(inheritedCard, before: humanCardActual, board: &humanCardExpected)
        try expect(!humanCardExpected.cards.contains(where: { $0.id == "human_new_card" }), "human-created card is not absorbed into model base")
        let deleteHumanCard: [String: Any] = ["cards": [], "edges": [], "remove_ids": ["human_new_card"], "remove_edge_ids": [], "summary": "删卡"]
        let deletion = try DirectAgent.validate(patch: deleteHumanCard, board: humanCardActual, selectedID: nil)
        BoardStore.advanceModelBase(deletion, before: humanCardActual, board: &humanCardExpected)
        try expect(!humanCardExpected.cards.contains(where: { $0.id == "human_new_card" }), "later model batch cannot archive human-created card")
        let canvasRequest = TaskBlueprint.from(prompt: "请生成三张画布")
        try expect(canvasRequest.newCardCount == nil && canvasRequest.clarification != nil, "independent canvas request does not become card count")
        let answer = TaskBlueprint.from(prompt: "卡片", conversation: [RadarMessage(role: "user", content: "请生成三张画布"),
            RadarMessage(role: "assistant", content: canvasRequest.clarification!), RadarMessage(role: "user", content: "卡片")])
        try expect(answer.newCardCount == 3 && answer.clarification == nil, "card clarification restores exact requested count")
        return passed
    }
}
#endif
