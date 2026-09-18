import UIKit

/// Prepare once when a node changes; draw only the bounded visible preview during canvas frames.
enum CanvasRichPreview {
    struct Prepared {
        var segments: [Segment]
        var remainingBlocks: Int
        var hasStructuredContent: Bool
    }
    enum Segment {
        case text(String, emphasized: Bool)
        case checklist([(text: String, checked: Bool)], total: Int)
        case table([[String]], totalRows: Int, totalColumns: Int)
        case media(CanvasAttachment, caption: String)
        case attachment(String, symbol: String)
    }
    static func prepare(blocks: [CanvasBlock]) -> Prepared {
        let segments: [Segment] = blocks.prefix(4).compactMap { block -> Segment? in
            if block.kind == "text" && block.text.isEmpty { return nil }
            switch block.kind {
            case "checklist": return .checklist(block.items.prefix(4).map { (String($0.text.prefix(160)), $0.isChecked) }, total: block.items.count)
            case "table":
                let rows = block.rows.prefix(4).map { $0.prefix(3).map { String($0.prefix(100)) } }
                return .table(rows, totalRows: block.rows.count, totalColumns: block.rows.prefix(4).map(\.count).max() ?? 0)
            case "image", "drawing":
                if let asset = block.attachment { return .media(asset, caption: String(block.text.prefix(100))) }
                return .attachment("附件暂不可用", symbol: "photo")
            case "file", "audio", "video":
                return .attachment(String((block.text.isEmpty ? block.attachment?.name ?? "附件" : block.text).prefix(120)), symbol: block.kind == "audio" ? "waveform" : block.kind == "video" ? "play.rectangle" : "doc")
            case "link": return .attachment(String((block.text.isEmpty ? block.url : block.text).prefix(160)), symbol: "link")
            default: return .text(String(block.text.prefix(260)), emphasized: block.emphasis == "bold" || block.emphasis == "heading")
            }
        }
        return Prepared(segments: segments, remainingBlocks: max(0, blocks.count - 4), hasStructuredContent: blocks.prefix(4).contains { ["checklist", "table"].contains($0.kind) })
    }
    static func draw(blocks: [CanvasBlock], in rect: CGRect, ink: UIColor) { draw(prepare(blocks: blocks), in: rect, ink: ink) }
    static func draw(_ prepared: Prepared, in rect: CGRect, ink: UIColor) {
        guard rect.width > 12, rect.height > 12, let context = UIGraphicsGetCurrentContext() else { return }
        context.saveGState(); context.clip(to: rect); defer { context.restoreGState() }
        var y = rect.minY
        let footer = prepared.remainingBlocks > 0 ? CGFloat(18) : 0
        for (index, segment) in prepared.segments.enumerated() {
            let remaining = prepared.segments.count - index - 1
            let available = rect.maxY - footer - y - CGFloat(remaining) * 27
            guard available >= 16 else { break }
            let height = min(desiredHeight(segment), available)
            let box = CGRect(x: rect.minX, y: y, width: rect.width, height: height)
            switch segment {
            case .text(let value, let emphasized):
                text(value, in: box, font: emphasized ? .boldSystemFont(ofSize: 14) : .systemFont(ofSize: 14), ink: ink, wrap: true)
            case .checklist(let items, let total): drawChecklist(items, total: total, in: box, ink: ink)
            case .table(let rows, let totalRows, let totalColumns): drawTable(rows, totalRows: totalRows, totalColumns: totalColumns, in: box, ink: ink)
            case .media(let asset, let caption):
                if let image = CanvasAssets.shared.thumbnail(for: asset) {
                    let imageBox = CGRect(x: box.minX, y: box.minY, width: box.width, height: max(12, box.height - (caption.isEmpty ? 0 : 20)))
                    let ratio = min(imageBox.width / image.size.width, imageBox.height / image.size.height)
                    let size = CGSize(width: image.size.width * ratio, height: image.size.height * ratio)
                    context.saveGState(); UIBezierPath(roundedRect: imageBox, cornerRadius: 6).addClip()
                    image.draw(in: CGRect(x: imageBox.midX - size.width / 2, y: imageBox.midY - size.height / 2, width: size.width, height: size.height)); context.restoreGState()
                    if !caption.isEmpty { text(caption, in: CGRect(x: box.minX, y: imageBox.maxY + 3, width: box.width, height: 17), font: .systemFont(ofSize: 11), ink: ink) }
                } else { text("附件暂不可用", in: box, font: .systemFont(ofSize: 12), ink: ink) }
            case .attachment(let value, let symbol):
                UIImage(systemName: symbol)?.withTintColor(ink, renderingMode: .alwaysOriginal).draw(in: CGRect(x: box.minX, y: box.minY + 1, width: 15, height: 15))
                text(value, in: CGRect(x: box.minX + 22, y: box.minY, width: box.width - 22, height: box.height), font: .systemFont(ofSize: 13), ink: ink)
            }
            y += height + 7
        }
        if prepared.remainingBlocks > 0 { text("还有 \(prepared.remainingBlocks) 项内容", in: CGRect(x: rect.minX, y: rect.maxY - 16, width: rect.width, height: 16), font: .systemFont(ofSize: 12), ink: CanvasStyle.secondary) }
    }
    private static func desiredHeight(_ segment: Segment) -> CGFloat {
        switch segment {
        case .text: return 50
        case .checklist(let items, let total): return CGFloat(max(1, items.count)) * 23 + (total > items.count ? 16 : 0)
        case .table(let rows, let totalRows, let totalColumns): return CGFloat(max(1, rows.count)) * 25 + (totalRows > rows.count || totalColumns > 3 ? 16 : 0)
        case .media: return 100
        case .attachment: return 34
        }
    }
    private static func drawChecklist(_ items: [(text: String, checked: Bool)], total: Int, in box: CGRect, ink: UIColor) {
        let rows = min(items.count, max(0, Int((box.height - (total > 4 ? 16 : 0)) / 23)))
        for (index, item) in items.prefix(rows).enumerated() {
            let y = box.minY + CGFloat(index) * 23
            let circle = UIBezierPath(ovalIn: CGRect(x: box.minX + 1, y: y + 3, width: 14, height: 14))
            circle.lineWidth = 1.3
            if item.checked {
                ink.withAlphaComponent(0.75).setFill(); circle.fill()
                let check = UIBezierPath(); check.move(to: CGPoint(x: box.minX + 4, y: y + 10)); check.addLine(to: CGPoint(x: box.minX + 7, y: y + 13)); check.addLine(to: CGPoint(x: box.minX + 12, y: y + 7)); check.lineWidth = 1.3; UIColor.white.setStroke(); check.stroke()
            } else { ink.withAlphaComponent(0.55).setStroke(); circle.stroke() }
            text(item.text, in: CGRect(x: box.minX + 23, y: y, width: box.width - 23, height: 21), font: .systemFont(ofSize: 13), ink: ink.withAlphaComponent(item.checked ? 0.55 : 1), strike: item.checked)
        }
        if total > rows { text("还有 \(total - rows) 项", in: CGRect(x: box.minX + 23, y: box.minY + CGFloat(rows) * 23, width: box.width - 23, height: 16), font: .systemFont(ofSize: 12), ink: CanvasStyle.secondary) }
    }
    private static func drawTable(_ rows: [[String]], totalRows: Int, totalColumns: Int, in box: CGRect, ink: UIColor) {
        let columns = min(3, rows.map(\.count).max() ?? 0)
        guard columns > 0 else { text("空表格", in: box, font: .systemFont(ofSize: 12), ink: ink); return }
        let shown = min(rows.count, max(1, Int((box.height - (totalRows > 4 || totalColumns > 3 ? 16 : 0)) / 25)))
        let width = box.width / CGFloat(columns)
        for (r, values) in rows.prefix(shown).enumerated() {
            for c in 0..<columns {
                let cell = CGRect(x: box.minX + CGFloat(c) * width, y: box.minY + CGFloat(r) * 25, width: width, height: 25)
                ink.withAlphaComponent(r == 0 ? 0.09 : 0.025).setFill(); UIRectFill(cell)
                ink.withAlphaComponent(0.13).setStroke(); UIBezierPath(rect: cell).stroke()
                text(c < values.count ? values[c] : "", in: cell.insetBy(dx: 5, dy: 5), font: r == 0 ? .boldSystemFont(ofSize: 13) : .systemFont(ofSize: 13), ink: ink)
            }
        }
        if totalRows > shown || totalColumns > columns { text("\(totalRows) 行 · \(totalColumns) 列", in: CGRect(x: box.minX, y: box.minY + CGFloat(shown) * 25 + 1, width: box.width, height: 15), font: .systemFont(ofSize: 12), ink: CanvasStyle.secondary) }
    }
    private static func text(_ value: String, in rect: CGRect, font: UIFont, ink: UIColor, strike: Bool = false, wrap: Bool = false) {
        let paragraph = NSMutableParagraphStyle(); paragraph.lineBreakMode = wrap ? .byWordWrapping : .byTruncatingTail
        var attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: ink, .paragraphStyle: paragraph]
        if strike { attributes[.strikethroughStyle] = NSUnderlineStyle.single.rawValue }
        (value as NSString).draw(in: rect, withAttributes: attributes)
    }
}
