import UIKit

/// Explicit global arrangement only. Streaming additions keep their existing local placement.
enum CanvasLayout {
    private struct Unit {
        var id: String
        var members: Set<String>
        var positions: [String: CGPoint]
        var size: CGSize
    }
    static func arrange(_ board: inout RadarBoard) {
        let cards = Dictionary(board.visibleCards.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        let groups = Dictionary((board.groups ?? []).map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        let owned = Set((board.groups ?? []).flatMap { $0.cardIDs + ($0.groupIDs ?? []) })
        let edges = board.edges.filter { $0.directed != false }
        func pack(_ units: [Unit]) -> (positions: [String: CGPoint], size: CGSize) {
            guard !units.isEmpty else { return ([:], .zero) }
            var owner: [String: Int] = [:]
            for (index, unit) in units.enumerated() { for id in unit.members { owner[id] = index } }
            var incoming = Array(repeating: Set<Int>(), count: units.count)
            for edge in edges {
                if let a = owner[edge.fromID], let b = owner[edge.toID], a != b { incoming[b].insert(a) }
            }
            var remaining = Set(units.indices), positions: [String: CGPoint] = [:]
            var y: CGFloat = 0, maxWidth: CGFloat = 0
            while !remaining.isEmpty {
                var tier = remaining.filter { incoming[$0].intersection(remaining).isEmpty }.sorted()
                if tier.isEmpty { tier = [remaining.min()!] }
                // Keep independent items compact on a phone instead of making one very wide row.
                for start in stride(from: 0, to: tier.count, by: 3) {
                    let row = Array(tier.dropFirst(start).prefix(3))
                    var x: CGFloat = 0, height: CGFloat = 0
                    for index in row {
                        let unit = units[index]
                        for (id, point) in unit.positions { positions[id] = CGPoint(x: point.x + x, y: point.y + y) }
                        x += unit.size.width + 100; height = max(height, unit.size.height)
                    }
                    maxWidth = max(maxWidth, x - 100); y += height + 120
                }
                remaining.subtract(tier)
            }
            return (positions, CGSize(width: maxWidth, height: max(0, y - 120)))
        }
        func unit(_ id: String, path: Set<String>) -> Unit? {
            if let card = cards[id] { return Unit(id: id, members: [id], positions: [id: .zero], size: CanvasGeometry.cardRect(card).size) }
            guard !path.contains(id), let group = groups[id] else { return nil }
            let children = (group.cardIDs + (group.groupIDs ?? [])).compactMap { unit($0, path: path.union([id])) }
            guard !children.isEmpty else { return nil }
            let packed = pack(children)
            let positions = packed.positions.mapValues { CGPoint(x: $0.x + 24, y: $0.y + 54) }
            let expanded = CGSize(width: max(230, group.width ?? 0, packed.size.width + 48), height: max(group.height ?? 0, packed.size.height + 78))
            return Unit(id: id, members: children.reduce(into: Set([id])) { $0.formUnion($1.members) }, positions: positions, size: group.collapsed == true ? CGSize(width: 260, height: 88) : expanded)
        }
        let roots = board.visibleCards.map(\.id).filter { !owned.contains($0) } + (board.groups ?? []).map(\.id).filter { !owned.contains($0) }
        let packed = pack(roots.compactMap { unit($0, path: []) })
        for index in board.cards.indices {
            if let point = packed.positions[board.cards[index].id] {
                board.cards[index].x = point.x - packed.size.width / 2
                board.cards[index].y = point.y
            }
        }
    }
}
