// Explicit synthetic task only. Supply {"key":...} via stdin; never put the key in argv.
#if DIRECT_AGENT_BLUEPRINT_LIVE_CHECK
import Foundation

@main struct TaskBlueprintLiveCheck {
    @MainActor static func main() async {
        do {
            guard CommandLine.arguments.contains("--run-deepseek"),
                  let input = try JSONSerialization.jsonObject(with: FileHandle.standardInput.readDataToEndOfFile()) as? [String: String],
                  let key = input["key"], !key.isEmpty else { throw DirectAgentError.configuration("缺少显式测试配置。") }
            let config = AgentConnection(provider: "DeepSeek", baseURL: "https://api.deepseek.com/v1", model: "deepseek-flash")
            let prompt = "我想做一个电影的几段式剧本。请直接生成3张卡片。一位快递员在归还错投的信件时，找回与父亲联系的勇气。每卡100字以内，写具体场景、角色行动和必要对白；只写虚构电影内容，不搜索，不添加来源或总结卡。"
            let initial = RadarBoard(title: "合成电影剧本测试", question: "", template: "", cards: [], edges: [])
            var board = initial; var batches = 0; var first: Double?
            let start = Date()
            print("BLUEPRINT LIVE START model=deepseek-flash hasKey=true"); fflush(stdout)
            try await DirectAgent().generateStream(board: initial, prompt: prompt, selectedID: nil, configuration: config, apiKey: key) { result in
                batches += 1; if first == nil { first = Date().timeIntervalSince(start) }
                board = DirectAgent.accumulating(result, into: board)
                print("BLUEPRINT UPDATE batch=\(batches) cards=\(board.cards.count) edges=\(board.edges.count)"); fflush(stdout)
            }
            let blueprint = TaskBlueprint.from(prompt: prompt)
            guard board.cards.count == 3, blueprint.isComplete(initial: initial, candidate: board) else {
                throw DirectAgentError.invalidResult("合成三幕/三卡断言未通过。")
            }
            let record: [String: Any] = ["status": "passed", "provider": "DeepSeek", "model": config.model,
                "prompt": prompt, "cards": board.cards.map(\.json), "groups": (board.groups ?? []).map(\.json), "edges": board.edges.map(\.json),
                "firstBatchSeconds": first ?? -1, "totalSeconds": Date().timeIntervalSince(start), "batches": batches,
                "checks": ["exactly_three_new_cards", "three_act_headings_on_task_content", "ordinary_single_agent_tool_path"],
                "boundary": "Production DirectAgent URLSession and validation with Foundation Radar model fixtures; not iPhone Store/UI."]
            let data = try JSONSerialization.data(withJSONObject: record, options: [.prettyPrinted, .sortedKeys])
            let sanitized = String(decoding: data, as: UTF8.self).replacingOccurrences(of: key, with: "[redacted]")
            let folder = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("outputs/ios/task-blueprint-live")
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            try Data(sanitized.utf8).write(to: folder.appendingPathComponent("verification.json"), options: .atomic)
            print(String(format: "BLUEPRINT LIVE PASS cards=3 batches=%d first=%.2f total=%.2f", batches, first ?? -1, Date().timeIntervalSince(start))); fflush(stdout)
        } catch {
            print("BLUEPRINT LIVE FAIL " + ((error as? DirectAgentError)?.localizedDescription ?? "local failure")); fflush(stdout); exit(1)
        }
    }
}
#endif
