import Foundation

struct CanvasChecklistItem: Codable, Equatable, Identifiable {
    var id = UUID().uuidString
    var text = ""
    var isChecked = false
}

struct CanvasAttachment: Codable, Equatable, Identifiable {
    var id: String
    var name: String
    var contentType: String
    var path: String
    var thumbnailPath: String?
    var byteCount: Int
}

struct CanvasBlock: Codable, Equatable, Identifiable {
    var id = UUID().uuidString
    var kind = "text"
    var text = ""
    var attachment: CanvasAttachment?
    var items: [CanvasChecklistItem] = []
    var rows: [[String]] = []
    var url = ""
    var emphasis = "plain"
    var summary: String {
        switch kind {
        case "checklist": return items.map { ($0.isChecked ? "✓ " : "○ ") + $0.text }.joined(separator: "\n")
        case "table": return rows.map { $0.joined(separator: " · ") }.joined(separator: "\n")
        case "link": return text.isEmpty ? url : text
        default: return text.isEmpty ? (attachment?.name ?? "") : text
        }
    }
}

extension CanvasBlock {
    enum CodingKeys: String, CodingKey { case id, kind, text, attachment, items, rows, url, emphasis }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        kind = try c.decodeIfPresent(String.self, forKey: .kind) ?? "text"
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        attachment = try c.decodeIfPresent(CanvasAttachment.self, forKey: .attachment)
        items = try c.decodeIfPresent([CanvasChecklistItem].self, forKey: .items) ?? []
        rows = try c.decodeIfPresent([[String]].self, forKey: .rows) ?? []
        url = try c.decodeIfPresent(String.self, forKey: .url) ?? ""
        emphasis = try c.decodeIfPresent(String.self, forKey: .emphasis) ?? "plain"
    }
}

extension CanvasChecklistItem {
    enum CodingKeys: String, CodingKey { case id, text, isChecked }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        isChecked = try c.decodeIfPresent(Bool.self, forKey: .isChecked) ?? false
    }
}
