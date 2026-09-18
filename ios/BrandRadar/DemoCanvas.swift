import Foundation

/// An explicitly scripted, network-free demonstration. This is never a live-model fallback.
enum DemoCanvas {
    static let startPrompt = "演示：把上海周末咖啡这个 Brief，展开成一张有逻辑关系的画布。"
    static let refinePrompt = "演示：保留这个方向，把表达改得更轻快、更适合手机阅读。"
    static let copyPrompt = "演示：把这个想法做成一条可以分享的内容稿。"

    static func seed() -> RadarBoard {
        var board = BoardTemplate.campaign.make()
        let stableIDs = ["demo_brief", "demo_idea", "demo_question", "demo_action"]
        let mapping = Dictionary(uniqueKeysWithValues: zip(board.cards.map(\.id), stableIDs))
        for i in board.cards.indices { board.cards[i].id = stableIDs[i] }
        for i in board.edges.indices {
            board.edges[i].fromID = mapping[board.edges[i].fromID]!
            board.edges[i].toID = mapping[board.edges[i].toID]!
        }
        board.title = "周末，带上一个好想法"
        board.workspaceMode = .demo
        board.demoStage = 0
        board.groups = [RadarGroup(id: "demo_context", title: "从周末出发", cardIDs: ["demo_brief", "demo_question"], color: "sand"),
                        RadarGroup(id: "demo_creation", title: "把想法拍出来", cardIDs: ["demo_idea", "demo_action"], color: "sage")]
        return board
    }

    static func apply(prompt: String, selectedID: String?, to board: inout RadarBoard) -> String {
        if let selectedID, let group = board.groups?.first(where: { $0.id == selectedID }) {
            let members = DirectAgent.selectedMembers(group.id, board: board)
            let ids = board.visibleCards.filter { members.contains($0.id) }.map(\.id)
            guard !ids.isEmpty else { return "这个分组还没有卡片。" }
            for id in ids { _ = apply(prompt: prompt, selectedID: id, to: &board) }
            return "已更新这个分组里的 \(ids.count) 张卡片。"
        }
        let isCopy = prompt.contains("内容稿") || prompt.contains("文案") || prompt.contains("分享")
        let isRefine = selectedID != nil || prompt.contains("轻快") || prompt.contains("改稿")
        if isRefine, let id = selectedID ?? board.visibleCards.first(where: { $0.kind == "idea" })?.id,
           let index = board.cards.firstIndex(where: { $0.id == id }) {
            let old = board.cards[index]
            board.cards[index].history.append(old.title + "\n\n" + old.body)
            board.cards[index].title = isCopy ? "周末，从这一杯出发" : "带杯咖啡，出门转转"
            board.cards[index].body = isCopy
                ? "周末不用安排得太满。\n拿上咖啡，去那条一直想走的街。\n下一站，不妨听听自己的。\n\n#周末出发 #咖啡陪我走走"
                : "不写一整份城市攻略，只记一个出门的小瞬间。\n\n一杯咖啡、一段路、一个想去的地方。把「取杯 → 出门 → 抵达」连成三帧，让咖啡陪着人去做自己的事。"
            board.demoStage = max(board.demoStage ?? 0, isCopy ? 3 : 2)
            return "这张已改好，旧稿也留着。"
        }
        if isCopy {
            let card = RadarCard(id: "demo_copy", kind: "note", title: "周末，从这一杯出发", body: "周末不用安排得太满。\n拿上咖啡，去那条一直想走的街。\n下一站，不妨听听自己的。\n\n#周末出发 #咖啡陪我走走", color: "rose", x: 700, y: 300)
            upsert(card, into: &board)
            if let source = board.visibleCards.first(where: { $0.kind == "idea" }) {
                link(source.id, card.id, "写成内容", board: &board)
            }
            board.demoStage = 3
            return "内容稿放在粉色卡片里。"
        }
        let entries: [(String, String, String, String, String)] = [
            ("demo_scene", "出门前的那一分钟", "用户准备去一个想去的地方，顺路自提一杯咖啡。", "idea", "sage"),
            ("demo_story", "三帧，就能讲完", "① 拿到咖啡：今天想去哪里？\n② 出门途中：留一个真实细节。\n③ 抵达目的地：把镜头还给生活。", "note", "lavender"),
            ("demo_check", "把想法变成能做的事", "确认场景与门店条件 → 拍摄三帧 → 写一条短文案 → 人工审核 → 从手机分享。", "calendar", "sand")
        ]
        let baseY = (board.visibleCards.map(\.y).max() ?? -300) + 300
        for (i, entry) in entries.enumerated() {
            upsert(RadarCard(id: entry.0, kind: entry.3, title: entry.1, body: entry.2, color: entry.4,
                             x: Double(i % 2) * 350, y: baseY + Double(i / 2) * 300), into: &board)
        }
        if let source = board.visibleCards.first(where: { $0.kind == "idea" && !$0.id.hasPrefix("demo_scene") }) {
            link(source.id, "demo_scene", "放进场景", board: &board)
        }
        link("demo_scene", "demo_story", "形成表达", board: &board)
        link("demo_story", "demo_check", "落实行动", board: &board)
        board.demoStage = max(board.demoStage ?? 0, 1)
        return "场景、分镜和准备清单已连好。"
    }

    private static func upsert(_ card: RadarCard, into board: inout RadarBoard) {
        if let i = board.cards.firstIndex(where: { $0.id == card.id }) {
            var edited = card
            let previous = board.cards[i]
            edited.x = previous.x; edited.y = previous.y; edited.status = previous.status
            edited.history = previous.history
            if previous.title != edited.title || previous.body != edited.body { edited.history.append(previous.title + "\n\n" + previous.body) }
            board.cards[i] = edited
        } else { board.cards.append(card) }
    }
    private static func link(_ from: String, _ to: String, _ label: String, board: inout RadarBoard) {
        let id = "demo_edge_\(from)_\(to)"
        if !board.edges.contains(where: { $0.id == id }) { board.edges.append(RadarEdge(id: id, fromID: from, toID: to, label: label)) }
    }
}
