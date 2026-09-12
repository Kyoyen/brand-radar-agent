import Foundation

/// Portable content, independent of connection settings and the current viewport.
struct CanvasDocument: Codable {
    var nodes: [RadarCard]
    var groups: [RadarGroup]
    var edges: [RadarEdge]
    init(_ board: RadarBoard) { nodes = board.cards; groups = board.groups ?? []; edges = board.edges }

    func validate() throws {
        let nodeIDs = Set(nodes.map(\.id)), groupIDs = Set(groups.map(\.id))
        guard nodeIDs.count == nodes.count, groupIDs.count == groups.count,
              nodeIDs.isDisjoint(with: groupIDs), Set(edges.map(\.id)).isDisjoint(with: nodeIDs.union(groupIDs)), Set(edges.map(\.id)).count == edges.count else { throw CanvasEditError.invalidGraph }
        let active = nodeIDs.union(groupIDs)
        guard edges.allSatisfy({ active.contains($0.fromID) && active.contains($0.toID) && $0.fromID != $0.toID }) else { throw CanvasEditError.invalidGraph }
        var owned = Set<String>()
        for group in groups {
            guard [group.width, group.height].allSatisfy({ $0 == nil || ($0!.isFinite && $0! >= 88 && $0! <= 4000) }) else { throw CanvasEditError.invalidGraph }
            for id in group.cardIDs {
                guard nodeIDs.contains(id), owned.insert(id).inserted else { throw CanvasEditError.invalidGraph }
            }
            for id in group.groupIDs ?? [] {
                guard groupIDs.contains(id), id != group.id, owned.insert(id).inserted else { throw CanvasEditError.invalidGraph }
            }
        }
        func visit(_ id: String, path: Set<String>) throws {
            guard !path.contains(id) else { throw CanvasEditError.invalidGraph }
            for child in groups.first(where: { $0.id == id })?.groupIDs ?? [] { try visit(child, path: path.union([id])) }
        }
        for id in groupIDs { try visit(id, path: []) }
        guard nodes.allSatisfy({ $0.x.isFinite && $0.y.isFinite && $0.width.isFinite && $0.width >= 100 && $0.width <= 2000 && ($0.height == nil || ($0.height!.isFinite && $0.height! >= 100 && $0.height! <= 4000)) }) else { throw CanvasEditError.invalidGraph }
    }
}

enum CanvasEditError: LocalizedError {
    case invalidGraph
    var errorDescription: String? { "这次连接或分组无法成立，原内容已保留。" }
}

struct CanvasUpdate: Codable {
    var sessionID: String
    var transcriptRevision: Int
    var sequence: Int
    var cards: [RadarCard]
    var groups: [RadarGroup]
    var edges: [RadarEdge]
    var removeIDs: [String]
    var removeGroupIDs: [String]
    var removeEdgeIDs: [String]
}

/// Each changed field has a compare-and-swap inverse. Human edits made later win.
struct CanvasFieldChange: Codable, Equatable {
    var object: String
    var id: String
    var field: String
    var before: Data?
    var after: Data?
}
struct CanvasEditSession: Codable, Identifiable {
    var id = UUID().uuidString
    var title: String
    var changes: [CanvasFieldChange] = []
    var transcript: String? = nil
    var revision = 0
    var sequence = 0
    var complete = false
}

enum CanvasHistory {
    private static func fields<T: Encodable>(_ value: T) -> [String: Data] {
        guard let data = try? JSONEncoder().encode(value), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
        return object.compactMapValues { try? JSONSerialization.data(withJSONObject: $0, options: [.fragmentsAllowed, .sortedKeys]) }
    }
    private static func encoded<T: Encodable>(_ value: T) -> Data? {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys]; return try? encoder.encode(value)
    }
    private static func changes<T: Codable & Identifiable>(before: [T], after: [T], kind: String) -> [CanvasFieldChange] where T.ID == String {
        let old = Dictionary(uniqueKeysWithValues: before.map { ($0.id, $0) })
        let new = Dictionary(uniqueKeysWithValues: after.map { ($0.id, $0) })
        return Set(old.keys).union(new.keys).sorted().flatMap { id -> [CanvasFieldChange] in
            guard let a = old[id], let b = new[id] else {
                return [CanvasFieldChange(object: kind, id: id, field: "*", before: old[id].flatMap(encoded), after: new[id].flatMap(encoded))]
            }
            let x = fields(a), y = fields(b)
            return Set(x.keys).union(y.keys).sorted().compactMap { key in
                x[key] == y[key] ? nil : CanvasFieldChange(object: kind, id: id, field: key, before: x[key], after: y[key])
            }
        }
    }
    static func diff(_ before: RadarBoard, _ after: RadarBoard) -> [CanvasFieldChange] {
        changes(before: before.cards, after: after.cards, kind: "node") + changes(before: before.groups ?? [], after: after.groups ?? [], kind: "group") + changes(before: before.edges, after: after.edges, kind: "edge")
    }
    private static func apply<T: Codable & Identifiable>(_ delta: CanvasFieldChange, values: inout [T], backwards: Bool) where T.ID == String {
        let expected = backwards ? delta.after : delta.before, replacement = backwards ? delta.before : delta.after
        let index = values.firstIndex { $0.id == delta.id }
        if delta.field == "*" {
            guard index.flatMap({ encoded(values[$0]) }) == expected else { return }
            if let replacement, let value = try? JSONDecoder().decode(T.self, from: replacement) {
                if let index { values[index] = value } else { values.append(value) }
            } else if replacement == nil, let index { values.remove(at: index) }
        } else if let index {
            var object = fields(values[index])
            guard object[delta.field] == expected else { return }
            object[delta.field] = replacement
            let raw = object.compactMapValues { try? JSONSerialization.jsonObject(with: $0, options: .fragmentsAllowed) }
            if let data = try? JSONSerialization.data(withJSONObject: raw), let value = try? JSONDecoder().decode(T.self, from: data) { values[index] = value }
        }
    }
    static func apply(_ changes: [CanvasFieldChange], to board: inout RadarBoard, backwards: Bool) {
        for delta in backwards ? Array(changes.reversed()) : changes {
            switch delta.object {
            case "node": apply(delta, values: &board.cards, backwards: backwards)
            case "group": var groups = board.groups ?? []; apply(delta, values: &groups, backwards: backwards); board.groups = groups
            default: apply(delta, values: &board.edges, backwards: backwards)
            }
        }
        // Conditional inverses may preserve a human-edited object. Keep the rest structurally sound.
        let ids = Set(board.visibleCards.map(\.id)).union((board.groups ?? []).map(\.id))
        board.edges.removeAll { !ids.contains($0.fromID) || !ids.contains($0.toID) }
        for i in (board.groups ?? []).indices {
            board.groups?[i].cardIDs.removeAll { !ids.contains($0) }
            board.groups?[i].groupIDs?.removeAll { !ids.contains($0) }
        }
    }
    /// Apply only model fields which still equal their request-time base. Geometry and human decisions never come from stale snapshots.
    static func merge(_ incoming: RadarCard, base: RadarCard, current: RadarCard) -> RadarCard {
        var result = current
        if current.title == base.title { result.title = incoming.title }
        if current.body == base.body { result.body = incoming.body }
        if current.kind == base.kind { result.kind = incoming.kind }
        if current.color == base.color { result.color = incoming.color }
        if current.sourceIDs == base.sourceIDs { result.sourceIDs = incoming.sourceIDs }
        if let blocks = incoming.blocks {
            var merged = current.effectiveBlocks
            for incomingBlock in blocks {
                if let i = merged.firstIndex(where: { $0.id == incomingBlock.id }) {
                    guard let original = base.effectiveBlocks.first(where: { $0.id == incomingBlock.id }) else { continue }
                    let human = merged[i]
                    if human == original { merged[i] = incomingBlock }
                    else if human.kind == "checklist", incomingBlock.kind == "checklist", original.kind == "checklist" {
                        var value = human
                        for item in incomingBlock.items {
                            if let j = value.items.firstIndex(where: { $0.id == item.id }) {
                                if value.items[j].text == original.items.first(where: { $0.id == item.id })?.text { value.items[j].text = item.text }
                            } else if !original.items.contains(where: { $0.id == item.id }) { value.items.append(item) }
                        }
                        merged[i] = value
                    }
                    // Completion belongs to the user even if no concurrent edit occurred.
                    for j in merged[i].items.indices {
                        if let item = human.items.first(where: { $0.id == merged[i].items[j].id }) { merged[i].items[j].isChecked = item.isChecked }
                    }
                } else if !base.effectiveBlocks.contains(where: { $0.id == incomingBlock.id }) { merged.append(incomingBlock) }
            }
            result.blocks = merged
        } else if result.body != current.body, var blocks = current.blocks,
                  let index = blocks.firstIndex(where: { $0.kind == "text" && $0.text == base.body }) {
            blocks[index].text = result.body; result.blocks = blocks
        }
        if result.title != current.title || result.body != current.body { result.history.append(current.title + "\n\n" + current.body) }
        return result
    }
}
