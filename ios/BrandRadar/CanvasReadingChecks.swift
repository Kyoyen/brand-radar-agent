#if DEBUG
import UIKit

@MainActor enum CanvasReadingChecks {
    static func run() throws -> [String] {
        var results: [String] = []
        func check(_ passes: Bool, _ label: String) throws {
            guard passes else { throw CanvasContentChecks.Failure(message: label) }; results.append(label)
        }
        var board = BoardTemplate.blank.make()
        board.cards = (0..<120).map { index in
            var card = RadarCard(id: "reading_\(index)", title: String(repeating: "完整中文标题", count: 8), body: String(repeating: "正文保留，不随全貌缩放改写。", count: 30))
            card.x = Double(index % 12) * 450; card.y = Double(index / 12) * 400
            return card
        }
        let cache = CanvasGeometryCache(); cache.update(board)
        let measured = cache.measurements, initial = cache.rects
        for scale: CGFloat in [0.12, 0.65, 1, 1.5] {
            for rect in cache.rects.values { _ = CanvasStyle.detail(rect: rect, scale: scale) }
        }
        try check(cache.measurements == measured && cache.rects == initial, "reading detail changes preserve 120-node positions and text measurement cache")
        let normal = CGRect(x: 0, y: 0, width: 320, height: 240)
        try check(CanvasStyle.detail(rect: normal, scale: 0.2) == .shape && CanvasStyle.detail(rect: normal, scale: 0.65) == .title && CanvasStyle.detail(rect: normal, scale: 1) == .preview, "overview removes unreadable body while readable zoom retains mixed preview")
        let far = CanvasStyle.presentationRect(normal, scale: 0.2)
        let middle = CanvasStyle.presentationRect(normal, scale: 0.65)
        let near = CanvasStyle.presentationRect(normal, scale: 1)
        try check(far.midX == normal.midX && far.midY == normal.midY && far.height < middle.height && middle.height < near.height && near == normal,
                  "far and middle card frames contract around the saved centre without moving the card")
        var connected = BoardTemplate.blank.make()
        connected.cards = [RadarCard(id: "a", title: "A", body: "a", x: 0, y: 0),
                           RadarCard(id: "b", title: "B", body: "b", x: 420, y: 0)]
        connected.edges = [RadarEdge(id: "ab", fromID: "a", toID: "b", label: "")]
        let connectedCache = CanvasGeometryCache(); connectedCache.update(connected)
        connectedCache.setPresentationScale(0.4)
        let presentedA = connectedCache.displayRects["a"]!, presentedB = connectedCache.displayRects["b"]!
        try check(connectedCache.rects["a"] == CanvasGeometry.cardRect(connected.cards[0]) && presentedA.width < connectedCache.rects["a"]!.width &&
                  connectedCache.displayCurves["ab"]!.1 == CGPoint(x: presentedA.maxX, y: presentedA.midY) &&
                  connectedCache.displayCurves["ab"]!.2 == CGPoint(x: presentedB.minX, y: presentedB.midY),
                  "overview hit frames and connection endpoints follow the visible cards")
        try check(!CanvasStyle.showsEdgeLabel(scale: 0.5, selected: true, visibleEdges: 2) && !CanvasStyle.showsEdgeLabel(scale: 1, selected: false, visibleEdges: 80) && CanvasStyle.showsEdgeLabel(scale: 1, selected: true, visibleEdges: 80), "edge labels respect screen font and dense selected context")
        func luminance(_ color: UIColor) -> Double {
            var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
            color.getRed(&r, green: &g, blue: &b, alpha: &a)
            func linear(_ x: CGFloat) -> Double { let v = Double(x); return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4) }
            return linear(r) * 0.2126 + linear(g) * 0.7152 + linear(b) * 0.0722
        }
        for (name, ink) in [("primary", CanvasStyle.ink), ("secondary", CanvasStyle.secondary), ("action", CanvasStyle.accent)] {
            let contrast = (luminance(CanvasStyle.paper) + 0.05) / (luminance(ink) + 0.05)
            try check(contrast >= 4.5, "paper \(name) contrast \(String(format: "%.2f", contrast)):1 exceeds normal text target")
        }
        return results
    }
}
#endif
