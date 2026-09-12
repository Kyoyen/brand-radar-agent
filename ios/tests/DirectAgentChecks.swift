// Standalone checks for the production AgentConnection/DirectAgent implementation.
// Run: xcrun swiftc -D DEBUG -D DIRECT_AGENT_CHECKS ios/BrandRadar/{CanvasContent,AgentConnection,DirectAgent,AgentPatchContent,TaskBlueprint}.swift ios/tests/DirectAgentChecks.swift -o /tmp/radar-direct-agent-checks && /tmp/radar-direct-agent-checks
// Foundation-only model fixtures let these network checks run without a simulator.
// The same production files are also typechecked with the actual Models.swift for iOS.
#if DIRECT_AGENT_CHECKS || DIRECT_AGENT_LIVE_CHECK || DIRECT_AGENT_STREAM_CHECKS || DIRECT_AGENT_STREAM_LIVE_CHECK || DIRECT_AGENT_BLUEPRINT_LIVE_CHECK
import Foundation

struct RadarCard: Equatable {
    var id = UUID().uuidString; var kind = "note"; var title: String; var body: String
    var color = "cream"; var x: Double = 0; var y: Double = 0; var width: Double = 280
    var blocks: [CanvasBlock]? = nil; var height: Double? = nil
    var effectiveBlocks: [CanvasBlock] { blocks ?? [CanvasBlock(id: "legacy_\(id)", kind: "text", text: body)] }
    var status = "draft"; var sourceIDs: [String] = []; var history: [String] = []
    var json: [String: Any] { ["id": id, "kind": kind, "title": title, "body": body, "color": color, "x": x, "y": y, "width": width, "status": status, "source_ids": sourceIDs] }
}
struct RadarEdge: Equatable {
    var id = UUID().uuidString; var fromID: String; var toID: String; var label: String
    var directed: Bool? = nil
    var json: [String: Any] { ["id": id, "from_id": fromID, "to_id": toID, "label": label] }
}
struct RadarGroup: Equatable {
    var id = UUID().uuidString; var title: String; var cardIDs: [String]; var color = "sage"
    var groupIDs: [String]? = nil; var collapsed: Bool? = nil; var width: Double? = nil; var height: Double? = nil
    var json: [String: Any] { ["id": id, "title": title, "card_ids": cardIDs, "color": color] }
}
struct RadarMessage { var role: String; var content: String }
struct RadarSource { var id: String; var title: String; var url: String?; var excerpt: String }
struct RadarBoard {
    var title: String; var question: String; var template: String
    var cards: [RadarCard]; var edges: [RadarEdge]; var messages: [RadarMessage] = []; var sources: [RadarSource]? = nil
    var groups: [RadarGroup]? = nil
}
#endif

#if DIRECT_AGENT_CHECKS
final class StubProtocol: URLProtocol {
    static let lock = NSLock()
    static var payload = Data()
    static var status = 200
    static var requests: [URLRequest] = []
    static var hang = false
    static var stopped = false
    static func prepare(_ object: Any, status: Int = 200, hang: Bool = false) throws {
        lock.lock(); defer { lock.unlock() }
        payload = try JSONSerialization.data(withJSONObject: object, options: [.fragmentsAllowed])
        self.status = status; self.hang = hang; requests = []; stopped = false
    }
    static func requestCount() -> Int { lock.lock(); defer { lock.unlock() }; return requests.count }
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.lock.lock()
        Self.requests.append(request)
        let data = Self.payload, status = Self.status, hang = Self.hang
        Self.lock.unlock()
        if hang { return }
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() { Self.lock.lock(); Self.stopped = true; Self.lock.unlock() }
}

@main struct DirectAgentChecks {
    static var checks = 0
    static let config = AgentConnection(provider: "Test", baseURL: "https://model.invalid/v1", model: "tools-model")
    static let key = "local-protocol-dummy-key"
    static func expect(_ value: Bool, _ label: String) {
        precondition(value, label); checks += 1
    }
    static func rejects(_ label: String, _ action: () throws -> Void) {
        do { try action(); fatalError(label) } catch { checks += 1 }
    }
    static func patch(cards: [[String: Any]] = [], edges: [[String: Any]] = [], remove: [String] = [], removeEdges: [String] = [],
                      groups: [[String: Any]]? = nil, removeGroups: [String]? = nil) -> [String: Any] {
        var value: [String: Any] = ["cards": cards, "edges": edges, "remove_ids": remove, "remove_edge_ids": removeEdges, "summary": "已更新草稿"]
        if let groups { value["groups"] = groups }
        if let removeGroups { value["remove_group_ids"] = removeGroups }
        return value
    }
    static func response(_ patch: [String: Any]) throws -> [String: Any] {
        let text = String(data: try JSONSerialization.data(withJSONObject: patch), encoding: .utf8)!
        return ["choices": [["finish_reason": "tool_calls", "message": ["tool_calls": [["id": "call_one", "type": "function", "function": ["name": "update_board", "arguments": text]]]]]]]
    }
    static func requestBody(_ request: URLRequest) throws -> [String: Any] {
        let bodyData: Data
        if let data = request.httpBody { bodyData = data } else {
            let stream = request.httpBodyStream!; stream.open(); defer { stream.close() }
            var data = Data(); var buffer = [UInt8](repeating: 0, count: 4096)
            while stream.hasBytesAvailable { let n = stream.read(&buffer, maxLength: buffer.count); if n <= 0 { break }; data.append(buffer, count: n) }
            bodyData = data
        }
        return try JSONSerialization.jsonObject(with: bodyData) as! [String: Any]
    }
    static func main() async throws {
        let session = URLSessionConfiguration.ephemeral; session.protocolClasses = [StubProtocol.self]
        let agent = DirectAgent(sessionConfiguration: session)
        let board = RadarBoard(title: "测试画布", question: "创意假设", template: "空白",
            cards: [RadarCard(id: "old", title: "原卡", body: "旧稿", x: 537, y: 193, status: "kept", history: ["更早的稿"]),
                    RadarCard(id: "other", title: "旁边", body: "不改")],
            edges: [RadarEdge(id: "old-edge", fromID: "old", toID: "other", label: "启发")])
        expect(try config.endpointURL().absoluteString == "https://model.invalid/v1/chat/completions", "endpoint appended")
        for url in ["http://model.invalid", "https://u:p@model.invalid", "https://model.invalid?key=bad", "https://model.invalid#bad", "file:///tmp/model"] {
            rejects("unsafe URL accepted") { _ = try AgentConnection(provider: "Test", baseURL: url, model: "x").endpointURL() }
        }
        expect(try AgentConnection(provider: "Test", baseURL: "http://127.0.0.1:8000/v1", model: "x").endpointURL().scheme == "http", "explicit debug loopback")
        rejects("header injection accepted") { _ = try DirectAgent.validatedKey("key\r\nInjected: bad") }
        let settings = String(data: try JSONEncoder().encode(config), encoding: .utf8)!
        expect(!settings.contains(key) && !settings.contains("apiKey"), "configuration has no secret")
        expect(StubProtocol.requestCount() == 0, "initialization must be offline")

        let first = patch(cards: [["id": "idea", "title": "假设", "body": "建议尝试", "kind": "idea", "x": 500, "y": 10]],
                          edges: [["id": "next", "from_id": "old", "to_id": "idea", "label": "展开"]])
        try StubProtocol.prepare(response(first))
        let generated = try await agent.generate(board: board, prompt: "展开一个方向", selectedID: "old", configuration: config, apiKey: key)
        expect(generated.cards.count == 1 && generated.cards[0].id == "idea" && generated.edges[0].toID == "idea", "same-batch IDs and edges")
        let request = StubProtocol.requests[0]
        expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer " + key, "key only in Authorization header")
        let body = try requestBody(request)
        let bodyData = try JSONSerialization.data(withJSONObject: body)
        expect(body["parallel_tool_calls"] as? Bool == false && body["tools"] != nil, "forced single tool request")
        expect(body["thinking"] == nil, "other providers receive no DeepSeek extension")
        expect(!String(data: bodyData, encoding: .utf8)!.contains(key), "key absent from prompt")

        let updated = try DirectAgent.validate(patch: patch(cards: [["id": "old", "body": "新稿", "x": 0, "y": 0]]), board: board, selectedID: "old")
        expect(updated.cards[0].x == 537 && updated.cards[0].status == "kept" && updated.cards[0].history == ["更早的稿"], "human layout decision history preserved")
        expect(board.cards[0].body == "旧稿", "validation never mutates input")
        rejects("unselected card edited") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "other", "body": "越界"]]), board: board, selectedID: "old") }
        rejects("unselected card removed") { _ = try DirectAgent.validate(patch: patch(remove: ["other"]), board: board, selectedID: "old") }
        rejects("unknown source accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "source_ids": ["fake"]]]), board: board, selectedID: nil) }
        rejects("unsupported fact accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "kind": "observation"]]), board: board, selectedID: nil) }
        rejects("dangling graph accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "body": "不能部分保存"]], edges: [["id": "bad", "from_id": "old", "to_id": "missing", "label": "错"]]), board: board, selectedID: nil) }
        rejects("self edge accepted") { _ = try DirectAgent.validate(patch: patch(edges: [["id": "bad", "from_id": "old", "to_id": "old", "label": "错"]]), board: board, selectedID: nil) }
        rejects("duplicate IDs accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old"], ["id": "old"]]), board: board, selectedID: nil) }
        rejects("bool coordinate accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "x": true]]), board: board, selectedID: nil) }
        rejects("nonfinite coordinate accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "x": Double.infinity]]), board: board, selectedID: nil) }
        rejects("unexpected status injection accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "status": "archived"]]), board: board, selectedID: nil) }
        rejects("blank existing card title accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "old", "title": " \n\t"]]), board: board, selectedID: nil) }
        rejects("blank new card title accepted") { _ = try DirectAgent.validate(patch: patch(cards: [["id": "new", "title": "", "body": "正文"]]), board: board, selectedID: nil) }
        var wider = board; wider.cards.append(RadarCard(id: "third", title: "第三", body: ""))
        wider.edges.append(RadarEdge(id: "unrelated", fromID: "other", toID: "third", label: "不改"))
        rejects("unrelated edge rewired") { _ = try DirectAgent.validate(patch: patch(edges: [["id": "unrelated", "from_id": "old"]]), board: wider, selectedID: "old") }
        rejects("unrelated edge removed") { _ = try DirectAgent.validate(patch: patch(removeEdges: ["unrelated"]), board: wider, selectedID: "old") }

        let newGroup = ["id": "new-group", "title": "出门的片刻", "card_ids": ["old", "support"], "color": "sage"] as [String: Any]
        let grouped = try DirectAgent.validate(patch: patch(cards: [["id": "support", "title": "三帧就够", "body": "拍下出门一刻。"]],
                                                          groups: [newGroup]), board: board, selectedID: "old")
        expect(grouped.groups[0].cardIDs == ["old", "support"], "same-batch cards can be grouped with selected card")
        expect(grouped.removeGroupIDs.isEmpty, "optional group removal defaults empty")
        let legacy = try DirectAgent.validate(patch: patch(cards: [["id": "old", "body": "继续"]]), board: board, selectedID: "old")
        expect(legacy.groups.isEmpty && legacy.removeGroupIDs.isEmpty, "old patches without group fields remain valid")
        var groupBoard = wider
        groupBoard.groups = [RadarGroup(id: "direction", title: "一个方向", cardIDs: ["old", "other"])]
        let renamed = try DirectAgent.validate(patch: patch(groups: [["id": "direction", "title": "换个角度"]]), board: groupBoard, selectedID: "old")
        expect(renamed.groups[0].cardIDs == ["old", "other"], "partial group edit preserves membership")
        for invalid in [
            patch(groups: [["id": "bad", "title": "缺口", "card_ids": ["missing"]]]),
            patch(groups: [["id": "bad", "title": "空组", "card_ids": []]]),
            patch(groups: [["id": "bad", "title": " \n", "card_ids": ["old"]]]),
            patch(groups: [["id": "bad", "title": "颜色", "card_ids": ["old"], "color": "red"]]),
            patch(groups: [["id": "bad/id", "title": "格式", "card_ids": ["old"]]]),
            patch(groups: [["id": "bad", "title": "重复", "card_ids": ["old", "old"]]]),
            patch(groups: [["id": "bad", "title": "重复组", "card_ids": ["old"]], ["id": "bad", "title": "重复组", "card_ids": ["other"]]]),
            patch(groups: [["id": "bad", "title": "重复归属", "card_ids": ["old"]]]),
            patch(groups: [["id": "direction", "card_ids": ["old"]]]),
            patch(groups: [["id": "direction", "card_ids": ["old", "other", "third"]]]),
            patch(groups: [["id": "new", "title": "无关方向", "card_ids": ["third"]]]),
            patch(removeGroups: ["direction"]), patch(removeGroups: ["missing"])
        ] {
            rejects("invalid or out-of-scope group accepted") { _ = try DirectAgent.validate(patch: invalid, board: groupBoard, selectedID: "old") }
        }
        let moved = try DirectAgent.validate(patch: patch(groups: [["id": "direction", "card_ids": ["other"]],
                                                                  ["id": "selected-direction", "title": "独立推进", "card_ids": ["old"]]]),
                                             board: groupBoard, selectedID: "old")
        expect(moved.groups.count == 2 && moved.groups[0].cardIDs == ["other"], "selected card may move while other memberships stay")
        var singleton = board; singleton.groups = [RadarGroup(id: "one", title: "只含选中卡", cardIDs: ["old"])]
        let removedGroup = try DirectAgent.validate(patch: patch(removeGroups: ["one"]), board: singleton, selectedID: "old")
        expect(removedGroup.removeGroupIDs == ["one"], "selected-only group can be removed")
        let stillGrouped = try DirectAgent.validate(patch: patch(cards: [["id": "old", "body": "只改文字"]]), board: groupBoard, selectedID: "old")
        expect(stillGrouped.groups.isEmpty && groupBoard.groups?[0].cardIDs == ["old", "other"], "revision leaves groups untouched")

        for (status, payload) in [(401, ["error": ["message": key]] as [String: Any]), (429, ["error": ["message": key]]), (302, [:]), (200, ["unexpected": "body"])] {
            try StubProtocol.prepare(payload, status: status)
            do {
                _ = try await agent.generate(board: board, prompt: "继续", selectedID: nil, configuration: config, apiKey: key)
                fatalError("malformed HTTP response accepted")
            } catch { expect(!error.localizedDescription.contains(key), "errors never echo credentials") }
        }
        var badJSON = try response(first)
        badJSON["choices"] = [["finish_reason": "tool_calls", "message": ["tool_calls": [["type": "function", "function": ["name": "update_board", "arguments": "{broken"]]]]]]
        try StubProtocol.prepare(badJSON)
        do { _ = try await agent.generate(board: board, prompt: "继续", selectedID: nil, configuration: config, apiKey: key); fatalError("bad argument JSON accepted") }
        catch { checks += 1 }

        var probePatch = patch()
        probePatch["summary"] = key
        try StubProtocol.prepare(response(probePatch))
        let probe = try await agent.testConnection(configuration: config, apiKey: key)
        expect(probe == "连接成功 · 支持画布工具调用" && !probe.contains(key), "connection probe does not display provider text")
        expect(StubProtocol.requestCount() == 1, "probe sends exactly one request")
        let probeBody = try requestBody(StubProtocol.requests[0])
        expect((probeBody["tools"] as? NSArray) == (body["tools"] as? NSArray), "probe uses the real generation schema")
        expect((probeBody["tool_choice"] as? NSDictionary) == (body["tool_choice"] as? NSDictionary) && probeBody["parallel_tool_calls"] as? Bool == false, "probe forces exactly one board tool")
        expect(probeBody["max_tokens"] as? Int == 256, "probe limits response size")
        for unsupported in [
            ["choices": [["finish_reason": "stop", "message": ["content": "连接成功"]]]] as [String: Any],
            try response(patch(cards: [["id": "unexpected", "title": "额外内容", "body": "不应创建"]])),
            try response(patch(edges: [["id": "bad", "from_id": "a", "to_id": "b", "label": "无效"]]))
        ] {
            try StubProtocol.prepare(unsupported)
            do { _ = try await agent.testConnection(configuration: config, apiKey: key); fatalError("tool-incompatible probe accepted") }
            catch { checks += 1 }
        }
        expect(board.cards[0].body == "旧稿" && board.cards.count == 2 && board.edges.count == 1, "connection probes never change a user board")
        try StubProtocol.prepare(response(patch()))
        _ = try await agent.testConnection(configuration: AgentConnection(provider: "自定义", baseURL: "https://api.deepseek.com/v1", model: "deepseek-v4-flash"), apiKey: key)
        let deepseekBody = try requestBody(StubProtocol.requests[0])
        expect((deepseekBody["thinking"] as? [String: String])?["type"] == "disabled", "official DeepSeek endpoint disables thinking regardless of UI label")
        let guardDelegate = DirectAgentRedirectGuard()
        let redirectSession = URLSession(configuration: .ephemeral)
        let task = redirectSession.dataTask(with: URL(string: "https://model.invalid/v1")!)
        var followed = true
        guardDelegate.urlSession(redirectSession, task: task,
            willPerformHTTPRedirection: HTTPURLResponse(url: URL(string: "https://model.invalid/v1")!, statusCode: 302, httpVersion: nil, headerFields: nil)!,
            newRequest: URLRequest(url: URL(string: "http://leak.invalid")!)) { request in followed = request != nil }
        expect(!followed, "redirect refuses credential forwarding")
        redirectSession.invalidateAndCancel()

        try StubProtocol.prepare([:], hang: true)
        let pending = Task { try await agent.generate(board: board, prompt: "继续", selectedID: nil, configuration: config, apiKey: key) }
        for _ in 0..<100 { if StubProtocol.requestCount() > 0 { break }; try await Task.sleep(nanoseconds: 1_000_000) }
        expect(StubProtocol.requestCount() == 1, "cancel test request started")
        pending.cancel()
        do { _ = try await pending.value; fatalError("cancelled request returned edits") }
        catch is CancellationError { checks += 1 }
        expect(StubProtocol.stopped, "cancellation stops URL loading")
        print("DirectAgentChecks PASS: \(checks) checks; URLProtocol only, no live API key or remote request.")
    }
}
#endif
