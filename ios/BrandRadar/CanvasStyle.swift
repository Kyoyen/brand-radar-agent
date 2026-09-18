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
    enum Detail { case shape, title, preview }
    // Screen font and available area determine detail; world geometry never changes.
    static func detail(rect: CGRect, scale: CGFloat) -> Detail {
        guard 23 * scale >= 10, rect.width * scale >= 90, rect.height * scale >= 44 else { return .shape }
        guard 13 * scale >= 11, rect.width * scale >= 170, rect.height * scale >= 125 else { return .title }
        return .preview
    }
    static func showsEdgeLabel(scale: CGFloat, selected: Bool, visibleEdges: Int) -> Bool {
        11 * scale >= 10 && (selected || visibleEdges <= 18)
    }
}
