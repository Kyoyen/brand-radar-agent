// xcrun swiftc -D DEBUG -D DIRECT_AGENT_STREAM_CHECKS ios/BrandRadar/{CanvasContent,AgentConnection,DirectAgent,AgentPatchContent,TaskBlueprint,AgentStreamProtocol,AgentStreamGeneration}.swift ios/tests/{DirectAgentChecks,AgentStreamChecks}.swift -o /tmp/radar-stream-checks && /tmp/radar-stream-checks
#if DIRECT_AGENT_STREAM_CHECKS
import Foundation

final class StreamStub: URLProtocol {
    static var responses: [Data] = []
    static var requests: [URLRequest] = []
    static var hang = false
    static var status = 200
    static var contentType = "text/event-stream"
    static var afterResponse: (() -> Void)?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.requests.append(request)
        if Self.hang { return }
        let data = Self.responses.isEmpty ? Data() : Self.responses.removeFirst()
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: Self.status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": Self.contentType])!, cacheStoragePolicy: .notAllowed)
        // Exercise transport boundaries through a Chinese UTF-8 codepoint and SSE lines.
        for index in stride(from: 0, to: data.count, by: 7) { client?.urlProtocol(self, didLoad: data.subdata(in: index..<min(data.count, index + 7))) }
        client?.urlProtocolDidFinishLoading(self)
        Self.afterResponse?()
    }
    override func stopLoading() {}
}

@main struct AgentStreamChecks {
    static var count = 0
    static func expect(_ condition: Bool, _ name: String) { precondition(condition, name); count += 1 }
    static func rejects(_ name: String, _ action: () throws -> Void) {
        do { try action(); fatalError(name) } catch { count += 1 }
    }
    static func patch(_ id: String, complete: Bool, edges: [[String: Any]] = []) -> [String: Any] {
        ["cards": [["id": id, "title": "中文节点", "body": "忠实整理"]], "edges": edges,
         "remove_ids": [], "remove_edge_ids": [], "summary": "已整理", "complete": complete]
    }
    static func event(_ value: [String: Any]) throws -> String {
        "data: " + String(decoding: try JSONSerialization.data(withJSONObject: value), as: UTF8.self) + "\n\n"
    }
    static func stream(_ patch: [String: Any], reason: String = "tool_calls", done: Bool = true) throws -> Data {
        let arguments = String(decoding: try JSONSerialization.data(withJSONObject: patch), as: UTF8.self)
        let midpoint = arguments.index(arguments.startIndex, offsetBy: arguments.count / 2)
        var value = ": keepalive\n\n"
        value += try event(["choices": [["index": 0, "delta": ["tool_calls": [["index": 0, "id": "call_1", "type": "function", "function": ["name": "update_board", "arguments": String(arguments[..<midpoint])]]]]]]])
        value += try event(["choices": [["index": 0, "delta": ["tool_calls": [["index": 0, "function": ["arguments": String(arguments[midpoint...])]]]]]]])
        value += try event(["choices": [["index": 0, "delta": [:], "finish_reason": reason]]])
        if done { value += "data: [DONE]\n\n" }
        return Data(value.utf8)
    }
    static func requestText(_ request: URLRequest) -> String {
        if let data = request.httpBody { return String(decoding: data, as: UTF8.self) }
        guard let stream = request.httpBodyStream else { return "" }
        stream.open(); defer { stream.close() }
        var data = Data(), buffer = [UInt8](repeating: 0, count: 4096)
        while stream.hasBytesAvailable {
            let n = stream.read(&buffer, maxLength: buffer.count)
            if n <= 0 { break }
            data.append(buffer, count: n)
        }
        return String(decoding: data, as: UTF8.self)
    }
    @MainActor static func main() async throws {
        let first = patch("one", complete: false)
        let second = patch("two", complete: true, edges: [["id": "link", "from_id": "one", "to_id": "two", "label": "然后"]])
        var decoder = AgentStreamDecoder(); var emitted = 0
        for line in String(decoding: try stream(first), as: UTF8.self).components(separatedBy: "\n") { emitted += try decoder.consume(line: line).count }
        try decoder.end(); expect(emitted == 1 && decoder.done, "split arguments and unicode decoded once")
        rejects("length finish accepted") {
            var decoder = AgentStreamDecoder()
            for line in String(decoding: try stream(first, reason: "length"), as: UTF8.self).components(separatedBy: "\n") { _ = try decoder.consume(line: line) }
        }
        rejects("missing DONE accepted") {
            var decoder = AgentStreamDecoder()
            for line in String(decoding: try stream(first, done: false), as: UTF8.self).components(separatedBy: "\n") { _ = try decoder.consume(line: line) }; try decoder.end()
        }
        rejects("provider error accepted") {
            var decoder = AgentStreamDecoder(); _ = try decoder.consume(line: "data: {\"error\":{\"message\":\"secret\"}}")
            _ = try decoder.consume(line: "")
        }
        let png = Data([137, 80, 78, 71, 13, 10, 26, 10, 0])
        expect(try DirectAgent.imageContent([DirectAgentImage(data: png, mimeType: "image/png", sourceID: "visual")], knownSourceIDs: ["visual"]).count == 2, "explicit source image content")
        rejects("unknown image source accepted") { _ = try DirectAgent.imageContent([DirectAgentImage(data: png, mimeType: "image/png", sourceID: "x")], knownSourceIDs: []) }
        rejects("false MIME accepted") { _ = try DirectAgent.imageContent([DirectAgentImage(data: Data("secret".utf8), mimeType: "image/png", sourceID: "visual")], knownSourceIDs: ["visual"]) }
        let config = URLSessionConfiguration.ephemeral; config.protocolClasses = [StreamStub.self]
        let agent = DirectAgent(sessionConfiguration: config)
        let connection = AgentConnection(provider: "Test", baseURL: "https://model.invalid/v1", model: "tools")
        let empty = RadarBoard(title: "测试", question: "", template: "", cards: [], edges: [])
        StreamStub.responses = [try stream(first), try stream(second)]
        var results: [DirectAgentResult] = []
        try await agent.generateStream(board: empty, prompt: "先一后二", selectedID: nil, configuration: connection, apiKey: "dummy") { result in
            results.append(result)
            if results.count == 1 { expect(StreamStub.requests.count == 1, "first update arrives before next request") }
        }
        expect(results.count == 2 && results[1].edges[0].fromID == "one", "cumulative cross-batch relation validation")
        expect(StreamStub.requests.count == 2, "bounded small independent tool requests")
        StreamStub.responses = [try stream(patch("visual-card", complete: true))]
        var visualBoard = empty; visualBoard.sources = [RadarSource(id: "visual", title: "输入图", url: nil, excerpt: "用户提供图像")]
        var visualResult: DirectAgentResult?
        try await agent.generateStream(board: visualBoard, prompt: "整理图", selectedID: nil, configuration: connection, apiKey: "dummy",
                                       images: [DirectAgentImage(data: png, mimeType: "image/png", sourceID: "visual")]) { visualResult = $0 }
        expect(visualResult?.cards[0].sourceIDs == ["visual"], "new visual cards retain actual input provenance when model omits it")
        StreamStub.responses = [try stream(first), try stream(patch("bad", complete: true, edges: [["id": "bad-edge", "from_id": "missing", "to_id": "bad", "label": "错"]]))]
        results = []
        do {
            try await agent.generateStream(board: empty, prompt: "整理", selectedID: nil, configuration: connection, apiKey: "dummy") { results.append($0) }
            fatalError("bad batch accepted")
        } catch { expect(results.count == 1, "bad later graph never callback, earlier batch retained") }
        StreamStub.responses = [try stream(first)]; results = []
        let task = Task {
            try await agent.generateStream(board: empty, prompt: "整理", selectedID: nil, configuration: connection, apiKey: "dummy") { result in
                results.append(result)
                withUnsafeCurrentTask { $0?.cancel() }
            }
        }
        do { try await task.value; fatalError("cancel completed normally") }
        catch is CancellationError { expect(results.count == 1, "cancel blocks subsequent updates and requests") }
        StreamStub.hang = true
        let pending = Task { try await agent.generateStream(board: empty, prompt: "整理", selectedID: nil, configuration: connection, apiKey: "dummy") { _ in fatalError("late callback") } }
        try await Task.sleep(nanoseconds: 30_000_000); pending.cancel()
        do { try await pending.value; fatalError("hanging request ignored cancel") }
        catch is CancellationError { count += 1 }
        StreamStub.hang = false
        StreamStub.status = 401
        do { try await agent.generateStream(board: empty, prompt: "整理", selectedID: nil, configuration: connection, apiKey: "dummy") { _ in fatalError("unauthorized callback") }; fatalError("HTTP failure accepted") }
        catch let error as DirectAgentError { expect(!error.localizedDescription.contains("dummy"), "HTTP error sanitized") }
        StreamStub.status = 200; StreamStub.contentType = "application/json"
        do { try await agent.generateStream(board: empty, prompt: "整理", selectedID: nil, configuration: connection, apiKey: "dummy") { _ in fatalError("non SSE callback") }; fatalError("non SSE accepted") }
        catch is DirectAgentError { count += 1 }
        var grouped = empty
        grouped.cards = [RadarCard(id: "inside", title: "组内", body: "原文"), RadarCard(id: "outside", title: "组外", body: "保留")]
        grouped.groups = [RadarGroup(id: "group", title: "选中组", cardIDs: ["inside"])]
        var groupPatch = patch("inside", complete: true); groupPatch.removeValue(forKey: "complete")
        let groupResult = try DirectAgent.validate(patch: groupPatch, board: grouped, selectedID: "group")
        expect(groupResult.cards.first?.id == "inside", "selected group edits its members")
        var outsidePatch = patch("outside", complete: true); outsidePatch.removeValue(forKey: "complete")
        rejects("group scope escaped") { _ = try DirectAgent.validate(patch: outsidePatch, board: grouped, selectedID: "group") }
        var unlabeled = groupPatch; unlabeled["cards"] = []
        unlabeled["edges"] = [["id": "plain-arrow", "from_id": "inside", "to_id": "outside", "directed": true]]
        expect(try DirectAgent.validate(patch: unlabeled, board: grouped, selectedID: nil).edges[0].label.isEmpty, "faithful unlabeled source arrow permits omitted label")
        var nested = groupPatch; nested["cards"] = []
        nested["groups"] = [["id": "parent", "title": "父组", "card_ids": [], "group_ids": ["group"]]]
        nested["edges"] = [["id": "group-edge", "from_id": "parent", "to_id": "outside", "label": "连接", "directed": false]]
        let nestedResult = try DirectAgent.validate(patch: nested, board: grouped, selectedID: nil)
        expect(nestedResult.groups.first?.groupIDs == ["group"] && nestedResult.edges.first?.directed == false, "nested group and group edge supported")
        nested["groups"] = [["id": "parent", "title": "父组", "card_ids": [], "group_ids": ["group"]], ["id": "group", "group_ids": ["parent"]]]
        rejects("containment cycle accepted") { _ = try DirectAgent.validate(patch: nested, board: grouped, selectedID: nil) }
        nested["groups"] = [["id": "parent", "title": "父组", "card_ids": [], "group_ids": ["absent"]]]
        rejects("unknown child group accepted") { _ = try DirectAgent.validate(patch: nested, board: grouped, selectedID: nil) }
        let attachment = CanvasAttachment(id: "photo", name: "用户照片", contentType: "image/png", path: "private/path.png", byteCount: 9)
        grouped.cards[0].blocks = [CanvasBlock(id: "photo-block", kind: "image", attachment: attachment), CanvasBlock(id: "text-block", text: "旧文字")]
        var blocksPatch = groupPatch
        blocksPatch["cards"] = [["id": "inside", "blocks": [["id": "text-block", "kind": "text", "text": "新文字"],
            ["id": "checklist", "kind": "checklist", "items": [["id": "item", "text": "打包", "isChecked": false]]],
            ["id": "table", "kind": "table", "rows": [["任务", "时间"], ["检查", "明天"]]],
            ["id": "link", "kind": "link", "url": "https://example.com"]]]]
        let blocks = try DirectAgent.validate(patch: blocksPatch, board: grouped, selectedID: "inside").cards[0].blocks!
        expect(blocks.count == 5 && blocks[0].attachment == attachment && blocks[1].text == "新文字", "block upsert preserves attachment and stable text identity")
        expect(blocks[2].items[0].id == "item" && blocks[3].rows.count == 2, "editable checklist and table")
        let context = String(decoding: try JSONSerialization.data(withJSONObject: DirectAgent.cardContext(grouped.cards[0])), as: UTF8.self)
        expect(!context.contains("private/path") && context.contains("attachment_id"), "attachment file path excluded from context")
        for invalidBlock: [String: Any] in [["id": "fake", "kind": "image", "attachment_id": "invented"],
            ["id": "bad-url", "kind": "link", "url": "file:///etc/passwd"],
            ["id": "bad-table", "kind": "table", "rows": [["a"], ["a", "b"]]],
            ["id": "inject-path", "kind": "image", "attachment": ["path": "injected"]],
            ["id": "photo-block", "kind": "text", "text": "偷换原图"]] {
            blocksPatch["cards"] = [["id": "inside", "blocks": [invalidBlock]]]
            rejects("unsafe block accepted") { _ = try DirectAgent.validate(patch: blocksPatch, board: grouped, selectedID: "inside") }
        }
        var labelOnly = groupPatch; labelOnly["cards"] = [["id": "label", "title": "短标签"]]
        expect(try DirectAgent.validate(patch: labelOnly, board: empty, selectedID: nil).cards[0].body.isEmpty, "label-only new card permits omitted body")
        let plain = TaskBlueprint.from(prompt: "把原因和结果连起来")
        expect(plain.instructions.isEmpty && plain.newCardCount == nil, "ordinary brief unaffected")
        expect(TaskBlueprint.from(prompt: "直接生成5张卡片").newCardCount == 5, "explicit Arabic card quantity")
        expect(TaskBlueprint.from(prompt: "再加三张卡片").newCardCount == 3, "spoken add-card quantity")
        expect(TaskBlueprint.from(prompt: "帮我生成十二张卡片").newCardCount == 12, "Chinese card quantity")
        expect(TaskBlueprint.from(prompt: "给我３张画布").newCardCount == nil && TaskBlueprint.from(prompt: "给我３张画布").requestedCanvasCount == 3, "independent canvas wording asks for clarification")
        expect(TaskBlueprint.from(prompt: "不要生成5张卡片，生成两张卡片").newCardCount == 2, "negated count is ignored")
        expect(TaskBlueprint.from(prompt: "整理文字\n选中素材内容（作为资料）：生成5张卡片").newCardCount == nil, "material text never becomes quantity command")
        expect(TaskBlueprint.from(prompt: "不要按三幕，保留普通便签").sectionNames.isEmpty, "negated structure is ignored")
        let script = TaskBlueprint.from(prompt: "写一个三幕电影剧本")
        expect(script.sectionNames == ["第一幕", "第二幕", "第三幕"], "three-act script has actual section labels")
        expect(TaskBlueprint.from(prompt: "写成四段式电影脚本").sectionNames == ["第一段", "第二段", "第三段", "第四段"], "explicit segment count overrides default three-act")
        rejects("oversized request silently truncated") { try TaskBlueprint.from(prompt: "生成四十张卡片").checkCapacity(maximum: 36) }
        var threeActs = empty
        threeActs.cards = [RadarCard(id: "act1", title: "第一幕：离开", body: "行动"), RadarCard(id: "act2", title: "第二幕：寻找", body: "冲突"), RadarCard(id: "act3", title: "第三幕：选择", body: "结果")]
        expect(script.isComplete(initial: empty, candidate: threeActs), "three distinct act headings complete blueprint")
        expect(!script.isComplete(initial: threeActs, candidate: threeActs), "unrelated pre-existing act headings cannot satisfy a new task")
        expect(TaskBlueprint.from(prompt: "这个三幕剧本只改第三幕正文").sectionNames.isEmpty, "selected act revision does not demand rebuilding all acts")
        threeActs.cards.removeLast()
        expect(!script.isComplete(initial: empty, candidate: threeActs), "missing third act cannot finish")
        var compactScript = empty
        compactScript.cards = [RadarCard(id: "compact", title: "电影", body: "")]
        compactScript.cards[0].blocks = script.sectionNames.enumerated().map { CanvasBlock(id: "heading-\($0.offset)", text: $0.element, emphasis: "heading") }
        expect(script.isComplete(initial: empty, candidate: compactScript), "act structure can use editable heading blocks")
        // Providers may claim complete before satisfying an explicit quantity. Keep the
        // valid first batch, return a progress receipt and request only the remaining cards.
        StreamStub.contentType = "text/event-stream"; StreamStub.status = 200
        StreamStub.responses = [try stream(patch("count-one", complete: true)), try stream(patch("count-two", complete: true))]
        results = []
        try await agent.generateStream(board: empty, prompt: "直接生成2张卡片", selectedID: nil, configuration: connection, apiKey: "dummy") { results.append($0) }
        expect(results.count == 2, "premature complete continues to exact requested count")
        var tooMany = patch("extra", complete: true)
        tooMany["cards"] = [["id": "extra1", "title": "一"], ["id": "extra2", "title": "二"]]
        StreamStub.responses = [try stream(tooMany)]; results = []
        do { try await agent.generateStream(board: empty, prompt: "生成1张卡片", selectedID: nil, configuration: connection, apiKey: "dummy") { results.append($0) }; fatalError("excess count accepted") }
        catch is DirectAgentError { expect(results.isEmpty, "oversized quantity batch rejected before callback") }
        var noProgress = patch("unused", complete: true); noProgress["cards"] = []
        StreamStub.responses = [try stream(patch("only-one", complete: true)), try stream(noProgress)]; results = []
        do { try await agent.generateStream(board: empty, prompt: "生成2张卡片", selectedID: nil, configuration: connection, apiKey: "dummy") { results.append($0) }; fatalError("missing count reported complete") }
        catch is DirectAgentError { expect(results.count == 1, "incomplete empty final fails while prior valid card remains") }
        expect(TaskBlueprint.from(prompt: "比较电影剧本与品牌表达的关系").instructions.isEmpty, "ordinary film analysis does not trigger writing template")
        expect(TaskBlueprint.from(prompt: "写一份电影几段式脚本").sectionNames.count == 3, "unspecified movie section template defaults to three acts")
        var partialBoard = empty; partialBoard.cards = [RadarCard(id: "from-previous-partial", title: "前一段已生成", body: "内容")]
        StreamStub.responses = [try stream(patch("remaining-one", complete: true))]; results = []
        try await agent.generateStream(board: partialBoard, prompt: "继续补完", selectedID: nil, configuration: connection, apiKey: "dummy",
            taskPrompt: "生成2张卡片", taskBase: empty) { results.append($0) }
        expect(results.count == 1, "taskBase counts previous partial cards toward session target")
        StreamStub.responses = [try stream(tooMany)]; results = []
        do { try await agent.generateStream(board: partialBoard, prompt: "继续补完", selectedID: nil, configuration: connection, apiKey: "dummy",
            taskPrompt: "生成2张卡片", taskBase: empty) { results.append($0) }; fatalError("cross-partial overproduction accepted") }
        catch is DirectAgentError { expect(results.isEmpty, "cross-partial target rejects adding N cards again") }
        blocksPatch["cards"] = [["id": "inside", "blocks": [["id": "text-block", "kind": "text", "text": "正文", "emphasis": "text"]]]]
        expect(try DirectAgent.validate(patch: blocksPatch, board: grouped, selectedID: "inside").cards[0].blocks?.first(where: { $0.id == "text-block" })?.emphasis == "plain", "observed provider text emphasis alias normalizes to plain")
        blocksPatch["cards"] = [["id": "inside", "blocks": [["id": "text-block", "kind": "text", "emphasis": "unknown"]]]]
        rejects("unknown emphasis accepted") { _ = try DirectAgent.validate(patch: blocksPatch, board: grouped, selectedID: "inside") }
        let canvasWords = TaskBlueprint.from(prompt: "生成1张画布")
        expect(canvasWords.newCardCount == nil && canvasWords.clarification?.contains("独立画布") == true, "canvas request never silently creates a card")
        let requestsBeforeClarification = StreamStub.requests.count
        results = []
        try await agent.generateStream(board: empty, prompt: "生成1张画布", selectedID: nil, configuration: connection, apiKey: "dummy") { results.append($0) }
        expect(StreamStub.requests.count == requestsBeforeClarification && results.count == 1 && results[0].cards.isEmpty, "canvas clarification uses no provider request or canvas edit")
        let answered = TaskBlueprint.from(prompt: "卡片", conversation: [RadarMessage(role: "user", content: "生成1张画布"), RadarMessage(role: "assistant", content: canvasWords.clarification!), RadarMessage(role: "user", content: "卡片")])
        expect(answered.newCardCount == 1 && answered.clarification == nil, "clarified card count resumes without another question")
        var archiveBoard = empty
        archiveBoard.cards = [RadarCard(id: "shared", title: "共用物料", body: ""), RadarCard(id: "branch", title: "分支", body: "")]
        archiveBoard.groups = [RadarGroup(id: "plan", title: "计划", cardIDs: ["shared", "branch"])]
        archiveBoard.edges = [RadarEdge(id: "dependency", fromID: "shared", toID: "branch", label: "共用")]
        let archived = DirectAgentResult(cards: [], edges: [], removeIDs: ["shared"], removeEdgeIDs: [], summary: "放下共用物料")
        let continued = DirectAgent.accumulating(archived, into: archiveBoard)
        expect(continued.cards.first(where: { $0.id == "shared" })?.status == "archived" && continued.groups?.first?.cardIDs == ["branch"] && continued.edges.isEmpty,
               "next streaming batch sees archived node detached from groups and edges")
        let sharedPlan = try DirectAgent.validate(patch: [
            "cards": [["id": "materials", "title": "共用物料"], ["id": "warmup", "title": "预热"],
                      ["id": "event", "title": "活动当天"], ["id": "after", "title": "后续"]],
            "edges": [["id": "to_warmup", "from_id": "materials", "to_id": "warmup", "label": "共用"],
                      ["id": "to_event", "from_id": "materials", "to_id": "event", "label": "共用"],
                      ["id": "to_after", "from_id": "materials", "to_id": "after", "label": "共用"]],
            "remove_ids": [], "remove_edge_ids": [], "summary": "分支共用一份物料"
        ], board: empty, selectedID: nil)
        let planned = DirectAgent.accumulating(sharedPlan, into: empty)
        expect(planned.cards.count == 4 && planned.edges.count == 3 && planned.edges.allSatisfy { $0.fromID == "materials" },
               "one shared dependency can connect to three distinct branches")
        let revisedEvent = try DirectAgent.validate(patch: ["cards": [["id": "event", "title": "活动当天 · 线下"]],
            "edges": [], "remove_ids": [], "remove_edge_ids": [], "summary": "当天改为线下"], board: planned, selectedID: "event")
        let revisedPlan = DirectAgent.accumulating(revisedEvent, into: planned)
        expect(revisedPlan.cards.count == 4 && revisedPlan.cards.first(where: { $0.id == "event" })?.title == "活动当天 · 线下",
               "selected correction changes the existing branch instead of adding a duplicate")
        StreamStub.requests = []
        StreamStub.responses = [try stream(patch("attempt", complete: true)), try stream(patch("recovered", complete: true))]
        var actual = empty, callbacks = 0
        try await agent.generateStreamApplied(board: empty, prompt: "先落图再纠正", selectedID: nil, configuration: connection, apiKey: "dummy", onApply: { result in
            callbacks += 1
            if callbacks == 1 { return StreamApplyResult(board: actual, applied: false, feedback: "人工修改使本批未落图。") }
            actual = DirectAgent.accumulating(result, into: actual)
            return StreamApplyResult(board: actual, applied: true, feedback: "已按实际画布保存。")
        })
        expect(callbacks == 2 && actual.cards.map(\.id) == ["recovered"] && StreamStub.requests.count == 2,
               "actual Store rejection prevents false completion and next batch uses actual board")
        let secondRequest = requestText(StreamStub.requests[1])
        expect(secondRequest.contains("未完整应用") && secondRequest.contains("人工修改使本批未落图") && secondRequest.contains("当前实际画布"),
               "next provider round receives concrete execution feedback and fresh board")
        StreamStub.requests = []
        StreamStub.responses = [try stream(patch("doomed", complete: false))]
        do {
            try await agent.generateStreamApplied(board: empty, prompt: "改已删除目标", selectedID: nil, configuration: connection, apiKey: "dummy", onApply: { _ in
                StreamApplyResult(board: empty, applied: false, feedback: "原目标已移除", terminal: true)
            })
            fatalError("terminal missing target continued")
        } catch is DirectAgentError { expect(StreamStub.requests.count == 1, "terminal target loss stops without retry") }
        StreamStub.requests = []
        StreamStub.responses = [try stream(patch("late", complete: false))]
        do {
            try await agent.generateStreamApplied(board: empty, prompt: "已取消的旧转写", selectedID: nil, configuration: connection, apiKey: "dummy", onApply: { _ in throw CancellationError() })
            fatalError("cancelled stream continued")
        } catch is CancellationError { expect(StreamStub.requests.count == 1, "cancelled old transcript cannot start another round") }
        var oversized = patch("too-much", complete: true)
        oversized["cards"] = (1...4).map { ["id": "too-much-\($0)", "title": "超量\($0)"] }
        StreamStub.requests = []
        StreamStub.responses = [try stream(oversized), try stream(patch("corrected", complete: true))]
        results = []
        try await agent.generateStreamApplied(board: empty, prompt: "请整理视觉标签", selectedID: nil,
            configuration: connection, apiKey: "dummy", onApply: { result in
                results.append(result)
                return StreamApplyResult(board: DirectAgent.accumulating(result, into: empty), applied: true, feedback: "已保存。")
            })
        expect(results.count == 1 && results[0].cards.map(\.id) == ["corrected"] && StreamStub.requests.count == 2,
               "oversized first batch never reaches Store and corrected small batch can complete")
        let correctionRequest = requestText(StreamStub.requests[1])
        expect(correctionRequest.contains("本批未落图") && correctionRequest.contains("cards=array4") &&
               correctionRequest.contains("最多3张卡") && correctionRequest.contains("当前实际画布"),
               "shape rejection sends precise counts and the unchanged actual board to the model")
        StreamStub.requests = []
        StreamStub.responses = [try stream(oversized), try stream(oversized), try stream(oversized)]
        results = []
        do {
            try await agent.generateStreamApplied(board: empty, prompt: "整理视觉标签", selectedID: nil,
                configuration: connection, apiKey: "dummy", onApply: { result in
                    results.append(result)
                    return StreamApplyResult(board: empty, applied: true, feedback: "不应执行。")
                })
            fatalError("third invalid shape accepted")
        } catch is DirectAgentError {
            expect(results.isEmpty && StreamStub.requests.count == 3,
                   "two correction requests are the limit and every invalid batch stays off canvas")
        }
        StreamStub.requests = []
        StreamStub.responses = [try stream(oversized), try stream(patch("must-not-run", complete: true))]
        results = []
        var cancellationTask: Task<Void, Error>?
        StreamStub.afterResponse = { if StreamStub.requests.count == 1 { cancellationTask?.cancel() } }
        cancellationTask = Task {
            try await agent.generateStreamApplied(board: empty, prompt: "取消无效批次后的请求", selectedID: nil,
                configuration: connection, apiKey: "dummy", onApply: { result in
                    results.append(result)
                    return StreamApplyResult(board: empty, applied: true, feedback: "不应执行。")
                })
        }
        do { try await cancellationTask!.value; fatalError("cancel after invalid batch continued") }
        catch is CancellationError {
            expect(results.isEmpty && StreamStub.requests.count == 1,
                   "cancellation after invalid shape stops before any correction request")
        }
        StreamStub.afterResponse = nil
        StreamStub.requests = []
        StreamStub.responses = [try stream(patch("saved-first", complete: false)),
                                try stream(oversized), try stream(oversized), try stream(oversized)]
        var savedBoard = empty
        var savedCallbacks = 0
        do {
            try await agent.generateStreamApplied(board: empty, prompt: "先保存一批再处理异常", selectedID: nil,
                configuration: connection, apiKey: "dummy", onApply: { result in
                    savedCallbacks += 1
                    savedBoard = DirectAgent.accumulating(result, into: savedBoard)
                    return StreamApplyResult(board: savedBoard, applied: true, feedback: "已保存。")
                })
            fatalError("invalid correction limit did not stop after a saved batch")
        } catch is DirectAgentError {
            expect(savedCallbacks == 1 && savedBoard.cards.map(\.id) == ["saved-first"] && StreamStub.requests.count == 4,
                   "valid first batch survives exhausted shape corrections without duplicate apply or extra HTTP")
        }
        print("AgentStreamChecks PASS: \(count) checks; URLProtocol only, model fixtures, no remote request.")
    }
}
#endif
