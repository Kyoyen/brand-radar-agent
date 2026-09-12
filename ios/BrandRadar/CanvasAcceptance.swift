#if DEBUG
import Foundation

@MainActor enum CanvasAcceptance {
    static func run(store: BoardStore) -> [String: Any] {
        var passed: [String] = []
        func expect(_ value: @autoclosure () -> Bool, _ label: String) throws {
            guard value() else { throw CanvasContentChecks.Failure(message: label) }; passed.append(label)
        }
        do {
            passed += try CanvasContentChecks.run()
            var board = BoardTemplate.blank.make()
            let a = RadarCard(id: "a", title: "初始", body: "原文"), b = RadarCard(id: "b", title: "后续", body: "")
            board.cards = [a,b]
            var generated = board; generated.cards[0].body = "AI正文"; generated.cards[0].color = "sage"
            let delta = CanvasHistory.diff(board, generated)
            generated.cards[0].title = "人工标题"; generated.cards[0].x = 88
            CanvasHistory.apply(delta, to: &generated, backwards: true)
            try expect(generated.cards[0].body == "原文" && generated.cards[0].title == "人工标题" && generated.cards[0].x == 88, "cancel preserves concurrent human title and position")
            CanvasHistory.apply(delta, to: &generated, backwards: false)
            try expect(generated.cards[0].body == "AI正文" && generated.cards[0].title == "人工标题", "redo only restores reverted fields")
            var human = a; human.body = "人的新正文"
            var incoming = a; incoming.body = "迟到旧回复"
            try expect(CanvasHistory.merge(incoming, base: a, current: human).body == human.body, "stale model fields cannot replace human edit")
            var loop = board; var g = RadarGroup(id:"g",title:"组",cardIDs:[]); var h = RadarGroup(id:"h",title:"子组",cardIDs:[])
            g.groupIDs = ["h"]; h.groupIDs = ["g"]; loop.groups = [g,h]
            var rejected = false; do { try CanvasDocument(loop).validate() } catch { rejected = true }
            try expect(rejected, "containment cycles rejected")
            board.edges = [RadarEdge(fromID:"a",toID:"b",label:"后续"),RadarEdge(fromID:"b",toID:"a",label:"反馈")]
            try CanvasDocument(board).validate(); passed.append("logical feedback cycles accepted")
            store.importCanvas(board)
            store.performCanvasCommand(.group(ids: ["a","b"]))
            let groupID = store.current.groups!.last!.id
            store.performCanvasCommand(.collapse(id: groupID))
            try expect(store.current.groups!.last!.collapsed == true, "group creation and collapse persist")
            store.performCanvasCommand(.move(ids: [groupID,"a"], dx: 15, dy: 20))
            try expect(store.current.cards[0].x == 15 && store.current.cards[1].x == 15, "nested selection moves each node once")
            store.performCanvasCommand(.ungroup(id: groupID))
            try expect(store.current.cards.count == 2 && store.current.groups!.isEmpty, "ungroup preserves children")
            store.performCanvasCommand(.delete(ids: ["a"], includingChildren: true))
            try expect(store.current.cards.count == 1 && store.current.edges.isEmpty, "delete removes incident edges")
            store.undo()
            try expect(store.current.cards.count == 2 && store.current.edges.count == 2, "undo restores node and relationships")
            store.redo(); try expect(store.current.cards.count == 1, "redo delete")
            let reopened = try JSONDecoder().decode(RadarBoard.self, from: JSONEncoder().encode(store.current))
            try expect(reopened.editHistory?.count == store.current.editHistory?.count, "history survives document roundtrip")
            store.importCanvas(board)
            let baseline = store.current
            try expect(store.beginVoiceSession(), "utterance session starts")
            var revised = baseline.cards[0]; revised.body = "口述修改"
            let patch = DirectAgentResult(cards: [revised], edges: [], removeIDs: [], removeEdgeIDs: [], summary: "")
            store.acceptTestUpdate(patch, base: baseline)
            try expect(store.current.cards[0].body == "口述修改", "incremental update visible before release")
            var edited = store.current.cards[0]; edited.title = "人工标题"
            store.editCard(edited)
            store.cancelVoiceSession()
            try expect(store.current.cards[0].body == baseline.cards[0].body && store.current.cards[0].title == "人工标题", "whole utterance cancel preserves interleaved manual edit")
            store.acceptTestUpdate(patch, base: baseline)
            try expect(store.current.cards[0].body == baseline.cards[0].body, "late response ignored after cancellation")
            let base2 = store.current
            _ = store.beginVoiceSession()
            store.acceptTestUpdate(patch, base: base2); store.sealTestSession(); store.undo()
            try expect(store.current.cards[0].body == base2.cards[0].body, "completed utterance undone as one session")
            store.redo(); try expect(store.current.cards[0].body == "口述修改", "completed utterance redo")
            store.importCanvas(board); let original = store.current
            _ = store.beginVoiceSession(); store.receiveVoice("把原有节点连接起来")
            store.performCanvasCommand(.delete(ids: ["a"], includingChildren: true))
            let conflict = DirectAgentResult(cards: [], edges: [RadarEdge(fromID:"a",toID:"b",label:"后续")], removeIDs: [], removeEdgeIDs: [], summary:"已连接")
            let accepted = store.acceptTestUpdate(conflict, base: original)
            try expect(!accepted && store.voiceSession == nil, "conflicting batch stops the edit session")
            try expect(!(store.current.pendingSpeech ?? "").isEmpty, "rejected batch preserves transcript for resume")
            var checked = RadarCard(id:"check",title:"准备",body:"")
            checked.blocks = [CanvasBlock(id:"list",kind:"checklist",items:[CanvasChecklistItem(id:"item",text:"带相机",isChecked:true)])]
            var proposal = checked; proposal.blocks![0].items[0].isChecked = false; proposal.blocks![0].items[0].text = "带备用相机"
            let combined = CanvasHistory.merge(proposal,base:checked,current:checked)
            try expect(combined.blocks![0].items[0].isChecked && combined.blocks![0].items[0].text == "带备用相机", "AI checklist edits preserve completion state")
            return ["passed": passed, "count": passed.count, "status":"passed"]
        } catch {
            return ["passed": passed, "count": passed.count, "status":"failed", "error":String(describing:error)]
        }
    }
}
#endif
