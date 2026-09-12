// Explicit live check. Compile with DIRECT_AGENT_LIVE_CHECK and the shared model fixtures.
// Read only {provider,model,key} from stdin, supplied by a dotenv-aware local script.
// The key never appears in argv, logs, saved outputs, or UserDefaults/Keychain.
#if DIRECT_AGENT_LIVE_CHECK
import Foundation

@main struct DirectAgentLiveCheck {
    enum CheckError: Error { case failed }
    static var stage = "configuration"
    static let outputFolder = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("outputs/ios/direct-agent-groups-live", isDirectory: true)
    static func log(_ object: [String: Any]) throws {
        let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        print(String(data: data, encoding: .utf8)!)
        fflush(stdout)
        try FileManager.default.createDirectory(at: outputFolder, withIntermediateDirectories: true)
        let logURL = outputFolder.appendingPathComponent("checks.jsonl")
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        let handle = try FileHandle(forWritingTo: logURL)
        defer { try? handle.close() }
        try handle.seekToEnd(); try handle.write(contentsOf: data + Data([10]))
    }
    static func require(_ condition: Bool, _ label: String) throws {
        guard condition else { try log(["stage": stage, "status": "failed", "check": label]); throw CheckError.failed }
    }
    static func merged(_ result: DirectAgentResult, into original: RadarBoard) -> RadarBoard {
        var board = original
        for incoming in result.cards {
            var card = incoming
            if let i = board.cards.firstIndex(where: { $0.id == card.id }) {
                let prior = board.cards[i]
                card.x = prior.x; card.y = prior.y; card.status = prior.status; card.history = prior.history
                if card.title != prior.title || card.body != prior.body { card.history.append(prior.title + "\n\n" + prior.body) }
                board.cards[i] = card
            } else { board.cards.append(card) }
        }
        for i in board.cards.indices where result.removeIDs.contains(board.cards[i].id) { board.cards[i].status = "archived" }
        board.edges.removeAll { result.removeEdgeIDs.contains($0.id) }
        for edge in result.edges {
            if let i = board.edges.firstIndex(where: { $0.id == edge.id }) { board.edges[i] = edge }
            else { board.edges.append(edge) }
        }
        var groups = (board.groups ?? []).filter { !result.removeGroupIDs.contains($0.id) }
        for group in result.groups {
            if let i = groups.firstIndex(where: { $0.id == group.id }) { groups[i] = group }
            else { groups.append(group) }
        }
        board.groups = groups
        board.messages.append(RadarMessage(role: "assistant", content: result.summary))
        return board
    }
    static func main() async {
        do {
            try require(CommandLine.arguments.contains("--run-deepseek"), "live invocation must be explicit")
            let input = FileHandle.standardInput.readDataToEndOfFile()
            guard let settings = try JSONSerialization.jsonObject(with: input) as? [String: String],
                  settings["provider"] == "deepseek", let model = settings["model"], let key = settings["key"], !key.isEmpty else {
                throw CheckError.failed
            }
            let configuration = AgentConnection(provider: "DeepSeek", baseURL: "https://api.deepseek.com/v1", model: model)
            try log(["stage": stage, "provider": configuration.provider, "model": model, "baseURL": configuration.baseURL, "hasKey": true])
            let agent = DirectAgent()
            var board = RadarBoard(title: "咖啡与周末的一个小出发", question: "只做创意假设，无需网络取材。", template: "营销企划", cards: [], edges: [])
            let prompt = "把周末自提咖啡陪人出门这个想法做成一张有包含与分支关系的画布，纯创作练习，不搜索、不编造事实。请创建6张卡，id固定brief、idea_a、detail_a、idea_b、detail_b、action。brief写共同目标；idea_a与idea_b写两个确实不同的表达方向；detail_a与detail_b分别写对应的拍摄做法；action写两条方向共同的手机分享准备。groups返回两个组，分别包含idea_a/detail_a、idea_b/detail_b；组名和卡片标题直接写内容。edges让brief分支到两个idea，各idea连接自己的detail，再由两detail汇入action，用短label说明关系。布局brief在(0,300)，idea_a/detail_a在(400,0)/(750,0)，idea_b/detail_b在(400,600)/(750,600)，action在(1100,300)。每卡标题约12字以内，正文40字左右。不要写创意假设、未验证、未引用外部数据等模型自我说明，不要用类型名当标题。所有内容是具体的创作提议，不宣称品牌委托、效果或已发布。一次update_board返回完整卡、组、连线，summary一句话。"
            stage = "generate"
            try log(["stage": stage, "status": "running"])
            board.messages.append(RadarMessage(role: "user", content: prompt))
            let first = try await agent.generate(board: board, prompt: prompt, selectedID: nil, configuration: configuration, apiKey: key)
            try require(Set(first.cards.map(\.id)) == Set(["brief", "idea_a", "detail_a", "idea_b", "detail_b", "action"]), "six stable card IDs")
            try require(first.groups.count == 2 && first.edges.count >= 5 && first.removeIDs.isEmpty && first.removeEdgeIDs.isEmpty, "groups and branch connections in same atomic patch")
            let forbidden = ["创意方向假设", "创意假设", "未引用外部数据", "未验证", "我是模型"]
            try require(first.cards.allSatisfy { card in !forbidden.contains(where: { (card.title + card.body).contains($0) }) }, "content avoids model meta commentary")
            board = merged(first, into: board)
            let cardIDs = Set(board.cards.map(\.id))
            try require(board.edges.allSatisfy { cardIDs.contains($0.fromID) && cardIDs.contains($0.toID) && $0.fromID != $0.toID }, "valid graph")
            try require(Dictionary(grouping: board.edges, by: \.fromID).values.contains { $0.count >= 2 }, "actual outgoing branch")
            let members = (board.groups ?? []).flatMap(\.cardIDs)
            try require(Set(members).count == members.count && members.allSatisfy { cardIDs.contains($0) }, "unique valid containment")
            let index = board.cards.firstIndex(where: { $0.id == "idea_a" })!
            board.cards[index].x = 537; board.cards[index].y = 193; board.cards[index].status = "kept"; board.cards[index].history = ["更早的人工草稿"]
            let before = board
            try log(["stage": stage, "status": "passed", "cards": board.cards.count, "edges": board.edges.count, "groups": board.groups?.count ?? 0])
            stage = "revise"
            let revisionPrompt = "只修改选中的idea_a卡正文，让机制改成出发前把工作状态放下一会儿，写得更轻快。不优惠、不地理攻略，直接写可做的内容。不要添加模型自我说明或免责文字。不要修改标题，不创建新卡，不修改其他卡、分组或任何连线；已有id、位置、采用决定由人保留。直接提交同id的body修改，其余数组空。"
            board.messages.append(RadarMessage(role: "user", content: revisionPrompt))
            try log(["stage": stage, "status": "running"])
            let result = try await agent.generate(board: board, prompt: revisionPrompt, selectedID: "idea_a", configuration: configuration, apiKey: key)
            try require(result.cards.count == 1 && result.cards[0].id == "idea_a", "selected card only")
            let revised = result.cards[0]
            try require(revised.body != before.cards[index].body, "body actually revised")
            try require(revised.x == 537 && revised.y == 193 && revised.status == "kept" && revised.history == before.cards[index].history, "validated result preserves user state")
            try require(result.edges.isEmpty && result.groups.isEmpty && result.removeGroupIDs.isEmpty && result.removeIDs.isEmpty && result.removeEdgeIDs.isEmpty, "relations and groups retained")
            board = merged(result, into: board)
            try require(board.edges == before.edges, "unchanged final graph")
            try require(board.groups == before.groups, "unchanged containment")
            try require(board.cards.filter { $0.id != "idea_a" } == before.cards.filter { $0.id != "idea_a" }, "unrelated cards retained")
            try require(board.cards[index].history.last == before.cards[index].title + "\n\n" + before.cards[index].body, "original preserved on local merge")
            let artifact: [String: Any] = ["title": board.title, "provider": configuration.provider, "model": model,
                "cards": board.cards.map { $0.json.merging(["history": $0.history]) { _, new in new } }, "edges": board.edges.map(\.json),
                "groups": (board.groups ?? []).map(\.json),
                "checks": ["same_batch_cards_groups_edges", "branching", "unique_containment", "concise_content", "selected_revision", "stable_id", "user_placement", "kept_status", "original_history", "valid_relations"],
                "boundary": "Production DirectAgent URLSession and validator on macOS; Foundation model fixtures and test merge, not actual iPhone BoardStore/UI."]
            let data = try JSONSerialization.data(withJSONObject: artifact, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: outputFolder.appendingPathComponent("result.json"), options: .atomic)
            try log(["stage": stage, "status": "passed", "cards": board.cards.count, "edges": board.edges.count, "groups": board.groups?.count ?? 0, "result": "LIVE PASS: grouped branch graph and selected revision preserve containment, IDs, placement, status, history and relations"])
        } catch {
            // Localized DirectAgent errors are sanitized; never dump provider data or request headers.
            let reason = (error as? DirectAgentError)?.localizedDescription ?? (error is CancellationError ? "cancelled" : "local check failed")
            try? log(["stage": stage, "status": "failed", "reason": reason])
            exit(1)
        }
    }
}
#endif
