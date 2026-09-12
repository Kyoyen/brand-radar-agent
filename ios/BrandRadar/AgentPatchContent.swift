import Foundation

extension DirectAgent {
    /// Context includes readable blocks and attachment identity, never device file paths.
    static func cardContext(_ card: RadarCard) -> [String: Any] {
        var value = card.json
        let blocks = card.effectiveBlocks
        if !blocks.isEmpty {
            value["blocks"] = blocks.map { block -> [String: Any] in
                var raw: [String: Any] = ["id": block.id, "kind": block.kind, "text": block.text,
                    "items": block.items.map { ["id": $0.id, "text": $0.text, "isChecked": $0.isChecked] },
                    "rows": block.rows, "url": block.url, "emphasis": block.emphasis]
                if let attachment = block.attachment {
                    raw["attachment_id"] = attachment.id; raw["attachment_name"] = attachment.name
                    raw["attachment_type"] = attachment.contentType
                }
                return raw
            }
        }
        return value
    }
    static func groupContext(_ group: RadarGroup) -> [String: Any] {
        var value = group.json; value["group_ids"] = group.groupIDs ?? []
        value["collapsed"] = group.collapsed ?? false
        return value
    }
    static func edgeContext(_ edge: RadarEdge) -> [String: Any] {
        var value = edge.json; value["directed"] = edge.directed ?? true; return value
    }
    static func selectedMembers(_ selectedID: String?, board: RadarBoard) -> Set<String> {
        guard let selectedID else { return [] }
        var seen: Set<String> = [selectedID], queue = [selectedID]
        while let id = queue.popLast(), let group = (board.groups ?? []).first(where: { $0.id == id }) {
            for child in group.cardIDs + (group.groupIDs ?? []) where seen.insert(child).inserted {
                if (board.groups ?? []).contains(where: { $0.id == child }) { queue.append(child) }
            }
        }
        return seen
    }
    static func validateBlocks(_ rawValue: Any, board: RadarBoard, previous: RadarCard?) throws -> [CanvasBlock] {
        let bad = DirectAgentError.invalidResult("模型返回的混合内容无效，本批没有保存。")
        guard let rawBlocks = rawValue as? [[String: Any]], rawBlocks.count <= 30 else { throw bad }
        var attachments: [String: CanvasAttachment] = [:]
        for card in board.cards { for block in card.blocks ?? [] { if let a = block.attachment { attachments[a.id] = a } } }
        var seen = Set<String>()
        let updates: [CanvasBlock] = try rawBlocks.map { raw in
            guard Set(raw.keys).isSubset(of: ["id", "kind", "text", "items", "rows", "url", "emphasis", "attachment_id"]),
                  let id = raw["id"] as? String, validID(id), seen.insert(id).inserted else { throw bad }
            let oldBlock = previous?.effectiveBlocks.first(where: { $0.id == id })
            var block = oldBlock ?? CanvasBlock(id: id)
            if let kind = raw["kind"] { guard let value = kind as? String else { throw bad }; block.kind = value }
            guard ["text", "image", "drawing", "checklist", "table", "link", "file", "audio", "video"].contains(block.kind) else { throw bad }
            if let text = raw["text"] { guard let text = text as? String, text.count <= 16000 else { throw bad }; block.text = text }
            if let emphasis = raw["emphasis"] {
                guard let text = emphasis as? String else { throw bad }
                // Real compatible providers sometimes repeat kind=text in this visual hint.
                // This unambiguous alias changes no content or privilege; unknown hints fail.
                let value = text == "text" ? "plain" : text
                guard ["plain", "bold", "heading", "list"].contains(value) else { throw bad }
                block.emphasis = value
            }
            if let value = raw["items"] {
                guard let items = value as? [[String: Any]], items.count <= 80 else { throw bad }
                var itemIDs = Set<String>()
                block.items = try items.map { item in
                    guard Set(item.keys).isSubset(of: ["id", "text", "isChecked"]), let id = item["id"] as? String,
                          validID(id), itemIDs.insert(id).inserted, let text = item["text"] as? String, text.count <= 2000 else { throw bad }
                    var checked = false
                    if let value = item["isChecked"] { guard let n = value as? NSNumber, CFGetTypeID(n) == CFBooleanGetTypeID() else { throw bad }; checked = n.boolValue }
                    return CanvasChecklistItem(id: id, text: text, isChecked: checked)
                }
            }
            if let value = raw["rows"] {
                guard let rows = value as? [[String]], rows.count <= 50,
                      rows.allSatisfy({ !$0.isEmpty && $0.count <= 12 && $0.allSatisfy { $0.count <= 2000 } }),
                      Set(rows.map(\.count)).count <= 1 else { throw bad }
                block.rows = rows
            }
            if let value = raw["url"] { guard let url = value as? String, url.count <= 4000 else { throw bad }; block.url = url }
            if !block.url.isEmpty {
                guard let url = URLComponents(string: block.url), ["https", "http"].contains(url.scheme?.lowercased() ?? ""),
                      url.host != nil, url.user == nil, url.password == nil else { throw bad }
            }
            if let value = raw["attachment_id"] {
                guard let id = value as? String, let attachment = attachments[id] else { throw bad }; block.attachment = attachment
            }
            if ["image", "drawing", "file", "audio", "video"].contains(block.kind), block.attachment == nil { throw bad }
            if let oldBlock, oldBlock.attachment != nil {
                guard block.kind == oldBlock.kind, block.attachment == oldBlock.attachment else { throw bad }
            }
            return block
        }
        // Blocks are upserts: omitted image, drawing and other material stays attached.
        var result = previous?.effectiveBlocks ?? []
        for block in updates {
            if let index = result.firstIndex(where: { $0.id == block.id }) { result[index] = block }
            else { result.append(block) }
        }
        guard result.count <= 30 else { throw bad }
        return result
    }

    static var blockSchema: [String: Any] {
        let string: [String: Any] = ["type": "string"]
        return ["type": "array", "maxItems": 30, "items": ["type": "object", "additionalProperties": false,
            "properties": ["id": string, "kind": ["type": "string", "enum": ["text", "image", "drawing", "checklist", "table", "link", "file", "audio", "video"]],
                "text": string, "url": string, "attachment_id": string,
                "emphasis": ["type": "string", "enum": ["plain", "bold", "heading", "list"]],
                "rows": ["type": "array", "items": ["type": "array", "items": string]],
                "items": ["type": "array", "items": ["type": "object", "additionalProperties": false,
                    "properties": ["id": string, "text": string, "isChecked": ["type": "boolean"]], "required": ["id", "text"]]]], "required": ["id", "kind"]]]
    }
}
