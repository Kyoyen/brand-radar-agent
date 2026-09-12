import UIKit

/// Screen transforms never invalidate world geometry. Moving a node never measures its text.
final class CanvasGeometryCache {
    typealias Curve = (UIBezierPath, CGPoint, CGPoint, CGPoint)
    private(set) var cards: [RadarCard] = []
    private(set) var groups: [RadarGroup] = []
    private(set) var edges: [RadarEdge] = []
    private(set) var hiddenIDs = Set<String>()
    private(set) var rects: [String: CGRect] = [:]
    private(set) var curves: [String: Curve] = [:]
    private(set) var curveBounds: [String: CGRect] = [:]
    private(set) var orderedGroups: [RadarGroup] = []
    private(set) var measurements = 0
    private var previousCards: [String: RadarCard] = [:]
    private var groupsByID: [String: RadarGroup] = [:]
    private var parents: [String: String] = [:]
    private var endpoints: [String: (CGRect, CGRect)] = [:]
    private var previewStrings: [String: String] = [:]
    private var richPreviews: [String: CanvasRichPreview.Prepared] = [:]

    func update(_ board: RadarBoard) {
        cards = board.visibleCards; groups = board.groups ?? []; edges = board.edges
        var nextRects: [String: CGRect] = [:], nextCards: [String: RadarCard] = [:]
        for card in cards {
            let size: CGSize
            if let old = previousCards[card.id], old.width == card.width, old.height == card.height,
               old.body == card.body, old.blocks == card.blocks, let rect = rects[card.id] {
                size = rect.size
            } else { size = CanvasGeometry.cardRect(card).size; measurements += 1 }
            nextRects[card.id] = CGRect(x: card.x, y: card.y, width: size.width, height: size.height)
            nextCards[card.id] = card
            if previousCards[card.id]?.body != card.body || previousCards[card.id]?.blocks != card.blocks {
                previewStrings[card.id] = card.effectiveBlocks.map(\.summary).joined(separator: "\n")
                richPreviews[card.id] = CanvasRichPreview.prepare(blocks: card.effectiveBlocks)
            }
        }
        previousCards = nextCards; rects = nextRects
        previewStrings = previewStrings.filter { nextCards[$0.key] != nil }
        richPreviews = richPreviews.filter { nextCards[$0.key] != nil }
        groupsByID = Dictionary(groups.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        parents = [:]
        for group in groups { for id in group.cardIDs + (group.groupIDs ?? []) { parents[id] = group.id } }
        hiddenIDs = []
        for group in groups where group.collapsed == true {
            var queue = group.cardIDs + (group.groupIDs ?? [])
            while let id = queue.popLast() {
                guard hiddenIDs.insert(id).inserted else { continue }
                if let child = groupsByID[id] { queue += child.cardIDs + (child.groupIDs ?? []) }
            }
        }
        rebuildGroupsAndEdges()
    }
    func richPreview(for id: String) -> CanvasRichPreview.Prepared? { richPreviews[id] }
    func preview(for id: String) -> String { previewStrings[id] ?? "" }
    func visibleEndpoint(_ id: String) -> String? {
        var candidate = id, visited = Set<String>()
        while hiddenIDs.contains(candidate) {
            guard visited.insert(candidate).inserted, let parent = parents[candidate] else { return nil }
            candidate = parent
        }
        return rects[candidate] == nil ? nil : candidate
    }
    func move(origins: [String: CGPoint], delta: CGPoint) {
        for (id, origin) in origins {
            guard var rect = rects[id] else { continue }
            rect.origin = CGPoint(x: origin.x + delta.x, y: origin.y + delta.y); rects[id] = rect
        }
        rebuildGroupsAndEdges()
    }
    func resize(id: String, size: CGSize) {
        if var rect = rects[id], previousCards[id] != nil {
            rect.size = size; rects[id] = rect
            previousCards[id]?.width = size.width; previousCards[id]?.height = size.height
        }
        else if var group = groupsByID[id] {
            group.width = size.width; group.height = size.height; groupsByID[id] = group
        }
        rebuildGroupsAndEdges()
    }
    var contentBounds: CGRect? {
        let visible = rects.filter { !hiddenIDs.contains($0.key) }.map(\.value) + Array(curveBounds.values)
        return visible.dropFirst().reduce(visible.first) { $0?.union($1) ?? $1 }
    }
    private func rebuildGroupsAndEdges() {
        for id in groupsByID.keys { rects.removeValue(forKey: id) }
        func resolve(_ id: String, path: Set<String>) -> CGRect? {
            if let rect = rects[id] { return rect }
            guard !path.contains(id), let group = groupsByID[id] else { return nil }
            let children = (group.cardIDs + (group.groupIDs ?? [])).compactMap { resolve($0, path: path.union([id])) }
            guard let first = children.first else { return nil }
            let union = children.dropFirst().reduce(first) { $0.union($1) }
            let rect = group.collapsed == true
                ? CGRect(x: union.minX - 24, y: union.minY - 54, width: 260, height: 88)
                : CGRect(x: union.minX - 24, y: union.minY - 54, width: max(group.width ?? 0, 230, union.width + 48), height: max(group.height ?? 0, union.height + 78))
            rects[id] = rect; return rect
        }
        for group in groups { _ = resolve(group.id, path: []) }
        orderedGroups = groups.filter { !hiddenIDs.contains($0.id) }.sorted {
            let a = rects[$0.id] ?? .zero, b = rects[$1.id] ?? .zero
            return a.width * a.height > b.width * b.height
        }
        var nextCurves: [String: Curve] = [:], nextBounds: [String: CGRect] = [:], nextEndpoints: [String: (CGRect, CGRect)] = [:]
        for edge in edges {
            guard let aID = visibleEndpoint(edge.fromID), let bID = visibleEndpoint(edge.toID), aID != bID,
                  let a = rects[aID], let b = rects[bID] else { continue }
            let curve: Curve
            if let previous = endpoints[edge.id], previous.0 == a, previous.1 == b, let existing = curves[edge.id] { curve = existing }
            else { curve = CanvasGeometry.curve(from: a, to: b) }
            nextCurves[edge.id] = curve; nextEndpoints[edge.id] = (a,b)
            // Reserve label and arrow extents as well as the actual Bézier path.
            let middle = CGPoint(x: (curve.1.x + curve.2.x) / 2, y: (curve.1.y + curve.2.y) / 2)
            let label = edge.label.isEmpty ? CGRect(origin: middle, size: .zero) : CGRect(x: middle.x - 70, y: middle.y - 14, width: 140, height: 28)
            nextBounds[edge.id] = curve.0.bounds.insetBy(dx: -12, dy: -12).union(label)
        }
        curves = nextCurves; curveBounds = nextBounds; endpoints = nextEndpoints
    }
}
