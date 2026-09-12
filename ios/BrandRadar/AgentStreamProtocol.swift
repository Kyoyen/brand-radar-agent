import Foundation

/// In-memory, explicitly selected visual material. No URL fetching or implicit file reads.
struct DirectAgentImage {
    let data: Data
    let mimeType: String
    let sourceID: String
}

struct AgentStreamCall {
    let id: String
    let arguments: String
    var patch: [String: Any] {
        get throws {
            guard let value = try JSONSerialization.jsonObject(with: Data(arguments.utf8)) as? [String: Any] else {
                throw DirectAgentError.invalidResult("本批画布数据不完整，已完成的内容仍然保留。")
            }
            return value
        }
    }
    var json: [String: Any] {
        ["id": id, "type": "function", "function": ["name": "update_board", "arguments": arguments]]
    }
}

/// SSE lines are decoded from raw bytes, preserving empty delimiters and split UTF-8 characters.
/// Tool argument deltas are never interpreted as executable edits until finish_reason.
struct AgentStreamDecoder {
    private struct Partial { var id = ""; var name = ""; var arguments = ""; var type = "" }
    private var partials: [Int: Partial] = [:]
    private var eventLines: [String] = []
    private var bytes = 0
    private(set) var finished = false
    private(set) var done = false
    private(set) var calls: [AgentStreamCall] = []

    mutating func consume(line: String) throws -> [AgentStreamCall] {
        bytes += line.utf8.count
        guard bytes <= 1_000_000 else { throw invalid }
        if line.isEmpty { return try flushEvent() }
        if line.hasPrefix("data:") {
            var value = String(line.dropFirst(5))
            if value.hasPrefix(" ") { value.removeFirst() }
            eventLines.append(value)
        }
        return []
    }
    mutating func end() throws {
        _ = try flushEvent()
        guard finished, done else { throw invalid }
    }
    private var invalid: DirectAgentError {
        .invalidResult("模型流式结果中断或格式无效，已完成的内容仍然保留。")
    }
    private mutating func flushEvent() throws -> [AgentStreamCall] {
        guard !eventLines.isEmpty else { return [] }
        let text = eventLines.joined(separator: "\n"); eventLines.removeAll()
        if text == "[DONE]" {
            guard finished, !done else { throw invalid }
            done = true; return []
        }
        guard !done, let object = try? JSONSerialization.jsonObject(with: Data(text.utf8)),
              let value = object as? [String: Any], value["error"] == nil,
              let choices = value["choices"] as? [[String: Any]] else { throw invalid }
        if choices.isEmpty { return [] } // Optional usage-only event.
        guard !finished, choices.count == 1, let choice = choices.first,
              (choice["index"] as? Int ?? 0) == 0,
              let delta = choice["delta"] as? [String: Any] else { throw invalid }
        if let toolValue = delta["tool_calls"] {
            guard let updates = toolValue as? [[String: Any]], updates.count <= 12 else { throw invalid }
            for update in updates {
                guard let index = update["index"] as? Int, index >= 0, index < 12 else { throw invalid }
                var partial = partials[index] ?? Partial()
                if let id = update["id"] as? String {
                    guard partial.id.isEmpty || partial.id == id, id.count <= 200 else { throw invalid }; partial.id = id
                }
                if let type = update["type"] as? String {
                    guard type == "function", partial.type.isEmpty || partial.type == type else { throw invalid }; partial.type = type
                }
                if let function = update["function"] as? [String: Any] {
                    if let name = function["name"] as? String { partial.name += name }
                    if let arguments = function["arguments"] as? String { partial.arguments += arguments }
                }
                guard partial.arguments.utf8.count <= 100_000, partial.name.count <= 100 else { throw invalid }
                partials[index] = partial
            }
        }
        if let reason = choice["finish_reason"] as? String {
            guard reason == "tool_calls", !partials.isEmpty,
                  partials.keys.sorted() == Array(0..<partials.count) else { throw invalid }
            var ids = Set<String>()
            calls = try partials.keys.sorted().map { index in
                let partial = partials[index]!
                guard !partial.id.isEmpty, ids.insert(partial.id).inserted,
                      partial.type == "function", partial.name == "update_board" else { throw invalid }
                let call = AgentStreamCall(id: partial.id, arguments: partial.arguments)
                _ = try call.patch
                return call
            }
            finished = true
            return calls
        }
        return []
    }
}
