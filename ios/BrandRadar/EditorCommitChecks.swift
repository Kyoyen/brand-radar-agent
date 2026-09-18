#if DEBUG
import Foundation

@MainActor enum EditorCommitChecks {
    static func run(store: BoardStore) throws -> [String] {
        var passed: [String] = []
        func expect(_ value: @autoclosure () -> Bool, _ label: String) throws {
            guard value() else { throw CanvasContentChecks.Failure(message: label) }; passed.append(label)
        }
        // Model a change arriving outside this local operation's undo history.
        func externalChange(_ change: (inout RadarBoard) -> Void) {
            guard let index = store.boards.firstIndex(where: { $0.id == store.selectedID }) else { return }
            change(&store.boards[index]); store.persist()
        }
        func fixture() -> RadarCard {
            var card = RadarCard(id: "editor-source", title: "原标题", body: "原正文")
            card.blocks = [CanvasBlock(id: "editor-text", kind: "text", text: "原正文"), CanvasBlock(id: "editor-list", kind: "checklist", items: [CanvasChecklistItem(id: "item", text: "材料", isChecked: true)])]
            var board = BoardTemplate.blank.make(); board.cards = [card, RadarCard(id: "unrelated", title: "另一个方向", body: "保留")]
            store.importCanvas(board); return card
        }
        let baseline = fixture(); let count = store.current.editHistory?.count ?? 0
        var draft = baseline; draft.title = "未保存标题"
        try expect(store.current.cards[0] == baseline && (store.current.editHistory?.count ?? 0) == count, "A01 local draft leaves real store and history unchanged")
        draft.blocks![0].text = "新正文"; draft.body = draft.effectiveBlocks.map(\.summary).joined(separator: "\n\n")
        var concurrent = baseline; concurrent.color = "rose"; concurrent.x = 420; concurrent.y = 310
        concurrent.blocks![1].items[0].text = "并发准备材料"
        externalChange { $0.cards[0] = concurrent; $0.cards[1].body = "其他卡并发更新" }
        try expect(store.saveAndSplitBlock(draft, baseline: baseline, blockID: "editor-text"), "A02 saving and splitting commits through real store")
        let source = store.current.cards.first { $0.id == baseline.id }!
        let node = store.current.cards.first { $0.id != baseline.id && $0.id != "unrelated" }!
        try expect(source.title == draft.title && source.blocks?.count == 1 && node.blocks?.first?.text == "新正文", "A02 split moves exactly the drafted block and saves title")
        try expect(source.color == "rose" && source.x == 420 && source.y == 310 && source.blocks?[0].items[0].text == "并发准备材料", "A02 commit preserves concurrent other fields blocks and position")
        try expect(store.current.cards[1].body == "其他卡并发更新" && store.current.edges.contains { $0.fromID == source.id && $0.toID == node.id }, "A02 split retains unrelated card and creates source relationship")
        try expect((store.current.editHistory?.count ?? 0) == count + 1 && store.splitUndoSessionID == store.current.editHistory?.last?.id, "A04 save and split creates exactly one undo session")
        externalChange { board in
            board.cards[0].color = "sage"; board.cards[0].x = 800; board.cards[1].title = "拆分之后的其他修改"
        }
        store.undo()
        let undone = store.current.cards[0]
        try expect(store.current.cards.count == 2 && store.current.edges.isEmpty && undone.title == baseline.title && undone.blocks?.first?.text == "原正文", "A04 one undo restores editor changes and removes split node and edge")
        try expect(undone.color == "sage" && undone.x == 800 && undone.blocks?[1].items[0].text == "并发准备材料" && store.current.cards[1].title == "拆分之后的其他修改", "A04 undo preserves unrelated edits made before and after split")
        let conflictBase = fixture(); var conflictDraft = conflictBase; conflictDraft.title = "我的标题"
        externalChange { $0.cards[0].title = "另一个新标题" }
        let beforeConflict = store.current.cards
        try expect(!store.editCard(conflictDraft, baseline: conflictBase) && store.editorFeedback != nil && store.current.cards == beforeConflict, "same title conflict rejects full save and retains current document")
        try expect(!store.saveAndSplitBlock(conflictDraft, baseline: conflictBase, blockID: "editor-text") && store.current.cards == beforeConflict && (store.current.editHistory ?? []).isEmpty, "same field conflict rejects split without partial save or history")
        let blockBase = fixture(); var blockDraft = blockBase; blockDraft.blocks![0].text = "我的块"
        externalChange { $0.cards[0].blocks![0].text = "他人的块" }
        try expect(!store.editCard(blockDraft, baseline: blockBase) && store.current.cards[0].blocks![0].text == "他人的块", "same block conflict is rejected")
        let saveBase = fixture(); var saveDraft = saveBase; saveDraft.title = "已保存标题"
        try expect(store.editCard(saveDraft, baseline: saveBase) && store.current.cards[0].title == "已保存标题", "ordinary save returns success and commits draft")
        let roundtrip = try JSONDecoder().decode(RadarBoard.self, from: JSONEncoder().encode(store.current))
        try expect(roundtrip.cards[0].title == "已保存标题", "saved editor content survives document reload")
        let insertBase = fixture(); var inserted = insertBase
        inserted.blocks!.insert(CanvasBlock(id: "middle", kind: "text", text: "中间补充"), at: 1)
        try expect(store.editCard(inserted, baseline: insertBase) && store.current.cards[0].blocks?.map(\.id) == ["editor-text", "middle", "editor-list"], "new draft block keeps its intended position")
        let untouchedBase = fixture(); var untouchedDraft = untouchedBase; untouchedDraft.title = "只改标题"
        externalChange { $0.cards[0].blocks![0].text = "最新内容" }
        try expect(store.editCard(untouchedDraft, baseline: untouchedBase) && store.current.cards[0].blocks![0].text == "最新内容", "ordinary save preserves concurrent untouched content blocks")
        let concurrentBlockBase = fixture()
        try expect(store.saveAndSplitBlock(concurrentBlockBase, baseline: concurrentBlockBase, blockID: "editor-text"), "block-level undo fixture splits through store")
        externalChange { board in
            board.cards[0].blocks![0].items[0].text = "Agent后续更新清单"
            board.cards[0].body = board.cards[0].effectiveBlocks.map(\.summary).joined(separator: "\n\n")
        }
        store.undo()
        try expect(store.current.cards.count == 2 && store.current.cards[0].blocks?.first?.text == "原正文" && store.current.cards[0].blocks?.last?.items.first?.text == "Agent后续更新清单", "A04 undo restores moved block while retaining later change to another block")
        try expect(store.current.cards[0].body == store.current.cards[0].effectiveBlocks.map(\.summary).joined(separator: "\n\n"), "A04 undo rebuilds derived body from merged concurrent blocks")
        store.redo()
        try expect(store.current.cards.count == 3 && store.current.cards[0].blocks?.count == 1 && store.current.cards[0].blocks?.first?.items.first?.text == "Agent后续更新清单", "A04 redo moves only restored block and preserves concurrent remainder")
        try expect(store.current.cards[0].body == store.current.cards[0].effectiveBlocks.map(\.summary).joined(separator: "\n\n"), "A04 redo rebuilds derived body from preserved remainder")
        store.undo()
        try expect(store.current.cards[0].blocks?.first?.text == "原正文", "A04 repeated undo never loses moved content")
        let legacyBodyBase = fixture()
        _ = store.saveAndSplitBlock(legacyBodyBase, baseline: legacyBodyBase, blockID: "editor-text")
        store.undo()
        try expect(store.current.cards[0].body == legacyBodyBase.body && store.current.cards[0].blocks == legacyBodyBase.blocks, "A04 undo retains independent legacy body alongside rich blocks")
        store.redo()
        try expect(store.current.cards[0].body == store.current.cards[0].effectiveBlocks.map(\.summary).joined(separator: "\n\n"), "A04 redo restores derived body after legacy undo")
        let changedNodeBase = fixture()
        _ = store.saveAndSplitBlock(changedNodeBase, baseline: changedNodeBase, blockID: "editor-text")
        let changedNodeID = store.selectedCardID!
        externalChange { board in
            let index = board.cards.firstIndex { $0.id == changedNodeID }!
            board.cards[index].blocks![0].text = "拆出节点上的人工新稿"; board.cards[index].body = "拆出节点上的人工新稿"
        }
        store.undo()
        try expect(store.current.cards.first(where: { $0.id == changedNodeID })?.blocks?.first?.text == "拆出节点上的人工新稿" && store.current.cards[0].blocks?.first?.text == "原正文", "A04 undo preserves human edited split node and restores source version")
        store.redo()
        try expect(store.current.cards.first(where: { $0.id == changedNodeID })?.blocks?.first?.text == "拆出节点上的人工新稿" && store.current.cards[0].blocks?.count == 1, "A04 redo preserves edited destination without duplicating nodes")
        let missingSourceBase = fixture()
        _ = store.saveAndSplitBlock(missingSourceBase, baseline: missingSourceBase, blockID: "editor-text")
        let survivorID = store.selectedCardID!
        externalChange { board in board.cards.removeAll { $0.id == missingSourceBase.id }; board.edges.removeAll() }
        store.undo()
        try expect(store.current.cards.contains { $0.id == survivorID && $0.blocks?.first?.text == "原正文" }, "undo retains moved content if original source was deleted meanwhile")
        return passed
    }
}
#endif
