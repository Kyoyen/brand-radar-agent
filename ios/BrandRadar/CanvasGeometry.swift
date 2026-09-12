import UIKit

/// All hit testing, layout bounds and connector anchors use the same geometry.
enum CanvasGeometry {
    static func cardRect(_ card: RadarCard) -> CGRect {
        let width = max(180, min(900, card.width))
        let preview = card.effectiveBlocks.map(\.summary).joined(separator: "\n")
        let body = (preview as NSString).boundingRect(with: CGSize(width: width - 44, height: 240), options: .usesLineFragmentOrigin, attributes: [.font: UIFont.systemFont(ofSize: 14)], context: nil).height
        return CGRect(x: card.x, y: card.y, width: width, height: max(150, min(1800, card.height ?? max(238, body + 145, card.effectiveBlocks.contains(where: { $0.kind == "image" || $0.kind == "drawing" }) ? 310 : 0)) ))
    }
    static func descendants(_ group: RadarGroup, in board: RadarBoard, visited: Set<String> = []) -> Set<String> {
        guard !visited.contains(group.id) else { return [] }
        var ids = Set(group.cardIDs)
        for child in board.groups ?? [] where (group.groupIDs ?? []).contains(child.id) {
            ids.formUnion(descendants(child, in: board, visited: visited.union([group.id])))
        }
        return ids
    }
    static func groupRect(_ group: RadarGroup, in board: RadarBoard, visited: Set<String> = []) -> CGRect? {
        guard !visited.contains(group.id) else { return nil }
        var rects = board.visibleCards.filter { group.cardIDs.contains($0.id) }.map(cardRect)
        rects += (board.groups ?? []).filter { (group.groupIDs ?? []).contains($0.id) }.compactMap { groupRect($0, in: board, visited: visited.union([group.id])) }
        guard let first = rects.first else { return nil }
        let union = rects.dropFirst().reduce(first) { $0.union($1) }
        let frame = CGRect(x: union.minX - 24, y: union.minY - 54, width: max(group.width ?? 0, 230, union.width + 48), height: max(group.height ?? 0, union.height + 78))
        return group.collapsed == true ? CGRect(x: frame.minX, y: frame.minY, width: 260, height: 88) : frame
    }
    static func hiddenIDs(in board: RadarBoard) -> Set<String> {
        var hidden = Set<String>()
        func collect(_ group: RadarGroup, visited: Set<String>) {
            guard !visited.contains(group.id) else { return }
            hidden.formUnion(group.cardIDs)
            for child in board.groups ?? [] where (group.groupIDs ?? []).contains(child.id) {
                hidden.insert(child.id); collect(child, visited: visited.union([group.id]))
            }
        }
        for group in board.groups ?? [] where group.collapsed == true { collect(group, visited: []) }
        return hidden
    }
    static func rect(_ id: String, in board: RadarBoard) -> CGRect? {
        if let card = board.visibleCards.first(where: { $0.id == id }) { return cardRect(card) }
        if let group = board.groups?.first(where: { $0.id == id }) { return groupRect(group, in: board) }
        return nil
    }
    static func curve(from a: CGRect, to b: CGRect) -> (UIBezierPath, CGPoint, CGPoint, CGPoint) {
        let horizontal = abs(b.midX - a.midX) > abs(b.midY - a.midY)
        let forward = horizontal ? b.midX >= a.midX : b.midY >= a.midY
        let start = horizontal ? CGPoint(x: forward ? a.maxX : a.minX, y: a.midY) : CGPoint(x: a.midX, y: forward ? a.maxY : a.minY)
        let end = horizontal ? CGPoint(x: forward ? b.minX : b.maxX, y: b.midY) : CGPoint(x: b.midX, y: forward ? b.minY : b.maxY)
        let bend = max(40, (horizontal ? abs(end.x-start.x) : abs(end.y-start.y)) * 0.5) * (forward ? 1 : -1)
        let c1 = horizontal ? CGPoint(x:start.x+bend,y:start.y) : CGPoint(x:start.x,y:start.y+bend)
        let c2 = horizontal ? CGPoint(x:end.x-bend,y:end.y) : CGPoint(x:end.x,y:end.y-bend)
        let path = UIBezierPath(); path.move(to:start); path.addCurve(to:end,controlPoint1:c1,controlPoint2:c2)
        return (path,start,end,c2)
    }
}

enum CanvasCommand {
    case resize(id: String, width: Double, height: Double)
    case move(ids: Set<String>, dx: Double, dy: Double)
    case connect(from: String, to: String)
    case createConnected(from: String, x: Double, y: Double)
    case rename(id: String, title: String)
    case delete(ids: Set<String>, includingChildren: Bool)
    case duplicate(ids: Set<String>)
    case group(ids: Set<String>)
    case ungroup(id: String)
    case collapse(id: String)
    case edge(id: String, label: String, directed: Bool, reversed: Bool)
}
