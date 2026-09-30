import SwiftUI

/// UIKit and SwiftUI share the same paper and focus colours.
enum CanvasStyle {
    static let background = UIColor(RadarPalette.canvas)
    static let paper = UIColor(RadarPalette.paper)
    static let accent = UIColor(RadarPalette.green)
    static let ink = UIColor(RadarPalette.textPrimary)
    static let secondary = UIColor(RadarPalette.textSecondary)
    static let border = UIColor(RadarPalette.borderSubtle)
    static let minimumHit: CGFloat = RadarPalette.minimumHitSize
    static func typeInk(_ kind: String) -> UIColor {
        switch kind {
        case "idea": return UIColor(red: 0.16, green: 0.40, blue: 0.30, alpha: 1)
        case "observation": return UIColor(red: 0.35, green: 0.29, blue: 0.58, alpha: 1)
        case "question": return UIColor(red: 0.56, green: 0.31, blue: 0.24, alpha: 1)
        case "source": return UIColor(red: 0.24, green: 0.39, blue: 0.51, alpha: 1)
        case "calendar": return UIColor(red: 0.44, green: 0.34, blue: 0.17, alpha: 1)
        default: return accent
        }
    }
    enum Detail { case shape, title, preview }
    // Keep the saved world frame intact. The visible frame contracts continuously around
    // its centre so a distant card does not become a large empty sheet.
    static func presentationRect(_ rect: CGRect, scale: CGFloat) -> CGRect {
        let progress = min(1, max(0, (scale - 0.22) / 0.68))
        let eased = progress * progress * (3 - 2 * progress)
        let width = rect.width * (0.58 + 0.42 * eased)
        let height = rect.height * (0.32 + 0.68 * sqrt(progress))
        return CGRect(x: rect.midX - width / 2, y: rect.midY - height / 2, width: width, height: height)
    }
    // Detail depends on the frame actually drawn, not the larger saved frame.
    static func detail(rect: CGRect, scale: CGFloat) -> Detail {
        guard rect.width * scale >= 38, rect.height * scale >= 25 else { return .shape }
        guard scale >= 0.88, rect.width * scale >= 170, rect.height >= 205 else { return .title }
        return .preview
    }
    static func showsEdgeLabel(scale: CGFloat, selected: Bool, visibleEdges: Int) -> Bool {
        selected || (scale >= 0.46 && visibleEdges <= 6) || (scale >= 0.91 && visibleEdges <= 18)
    }
    static func edgeLabelFont(scale: CGFloat) -> UIFont {
        .systemFont(ofSize: max(11, 10 / scale), weight: .medium)
    }
    static func edgeLabelRect(_ label: String, start: CGPoint, end: CGPoint, scale: CGFloat) -> CGRect {
        let middle = CGPoint(x: (start.x + end.x) / 2, y: (start.y + end.y) / 2)
        let width = min((label as NSString).size(withAttributes: [.font: edgeLabelFont(scale: scale)]).width, 70 / scale)
        let inset = 7 / scale, height = 19 / scale
        return CGRect(x: middle.x - width / 2 - inset, y: middle.y - height / 2,
                      width: width + inset * 2, height: height)
    }
}
