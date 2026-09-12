import UIKit
import UniformTypeIdentifiers

/// A portable document contains canvas content and its local assets only; connection settings live elsewhere.
enum CanvasExport {
    struct Package: Codable {
        var format = "brandradar.canvas"
        var version = 1
        var board: RadarBoard
        var assets: [String: Data]
    }
    enum ExportError: LocalizedError {
        case invalid, tooLarge, missing(String)
        var errorDescription: String? {
            switch self {
            case .invalid: return "这个文件不是可读取的画布包。"
            case .tooLarge: return "画布包超过 150 MB，请先减少附件。"
            case .missing(let name): return "附件“\(name)”暂不可用，请找回后再导出。"
            }
        }
    }
    static func package(board: RadarBoard) throws -> URL {
        var assets: [String: Data] = [:], total = 0
        for asset in board.cards.flatMap({ $0.effectiveBlocks.compactMap(\.attachment) }) {
            guard let original = CanvasAssets.shared.url(for: asset) else { throw ExportError.missing(asset.name) }
            var urls = [original]
            if let thumbnail = asset.thumbnailPath { urls.append(CanvasAssets.shared.directory.appendingPathComponent(thumbnail)) }
            let background = CanvasAssets.shared.directory.appendingPathComponent(asset.id + "-background.jpg")
            if FileManager.default.fileExists(atPath: background.path) { urls.append(background) }
            for url in urls where assets[url.lastPathComponent] == nil {
                guard url.lastPathComponent == url.pathComponents.last, url.deletingLastPathComponent().standardizedFileURL == CanvasAssets.shared.directory.standardizedFileURL else { throw ExportError.invalid }
                let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
                total += size; guard total <= 110_000_000 else { throw ExportError.tooLarge }
                assets[url.lastPathComponent] = try Data(contentsOf: url)
            }
        }
        var copy = board; copy.activeEditSession = nil; copy.editHistory = nil; copy.redoHistory = nil; copy.remoteID = nil; copy.dirtyCardIDs = nil; copy.dirtyEdgeIDs = nil; copy.removedEdgeIDs = nil
        let data = try JSONEncoder().encode(Package(board: copy, assets: assets))
        let url = temporary("画布.radarcanvas"); try data.write(to: url, options: .atomic); return url
    }
    static func importPackage(_ url: URL) throws -> RadarBoard {
        let access = url.startAccessingSecurityScopedResource(); defer { if access { url.stopAccessingSecurityScopedResource() } }
        guard (try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) <= 150_000_000 else { throw ExportError.tooLarge }
        let package = try JSONDecoder().decode(Package.self, from: Data(contentsOf: url))
        guard package.format == "brandradar.canvas", package.version == 1 else { throw ExportError.invalid }
        try CanvasDocument(package.board).validate()
        for (path, _) in package.assets { guard !path.isEmpty, !path.hasPrefix("."), path == URL(fileURLWithPath: path).lastPathComponent, !path.contains("/") else { throw ExportError.invalid } }
        // New filenames avoid overwriting originals when importing a different revision of an existing package.
        var created: [URL] = []
        var succeeded = false
        defer { if !succeeded { for url in created { try? FileManager.default.removeItem(at: url) } } }
        var map: [String: String] = [:]
        for (path, data) in package.assets {
            let fresh = UUID().uuidString + (URL(fileURLWithPath: path).pathExtension.isEmpty ? "" : "." + URL(fileURLWithPath: path).pathExtension)
            let target = CanvasAssets.shared.directory.appendingPathComponent(fresh)
            try data.write(to: target, options: .atomic); created.append(target); map[path] = fresh
        }
        var board = package.board
        board.id = UUID().uuidString; board.remoteID = nil; board.updated = Date()
        board.activeEditSession = nil; board.editHistory = nil; board.redoHistory = nil
        for i in board.cards.indices {
            var blocks = board.cards[i].effectiveBlocks
            for j in blocks.indices {
                guard var asset = blocks[j].attachment else { continue }
                let newID = UUID().uuidString
                if let bg = map[asset.id + "-background.jpg"] {
                    let target = CanvasAssets.shared.directory.appendingPathComponent(newID + "-background.jpg")
                    try FileManager.default.copyItem(at: CanvasAssets.shared.directory.appendingPathComponent(bg), to: target); created.append(target)
                }
                asset.id = newID; asset.path = map[asset.path] ?? ("missing-" + newID)
                asset.thumbnailPath = asset.thumbnailPath.flatMap { map[$0] }; blocks[j].attachment = asset
            }
            board.cards[i].blocks = blocks
        }
        succeeded = true
        return board
    }
    static func png(board: RadarBoard) throws -> URL {
        let bounds = contentBounds(board)
        let scale = min(2, 4096 / max(bounds.width, bounds.height))
        let format = UIGraphicsImageRendererFormat(); format.scale = 1
        let image = UIGraphicsImageRenderer(size: CGSize(width: bounds.width * scale, height: bounds.height * scale), format: format).image { ctx in
            ctx.cgContext.scaleBy(x: scale, y: scale); ctx.cgContext.translateBy(x: -bounds.minX, y: -bounds.minY); draw(board, bounds: bounds)
        }
        let url = temporary("画布.png"); try image.pngData()?.write(to: url, options: .atomic); return url
    }
    static func pdf(board: RadarBoard) throws -> URL {
        let bounds = contentBounds(board), scale = min(1, 3000 / max(bounds.width, bounds.height))
        let renderer = UIGraphicsPDFRenderer(bounds: CGRect(origin: .zero, size: CGSize(width: bounds.width * scale, height: bounds.height * scale)))
        let url = temporary("画布.pdf")
        try renderer.writePDF(to: url) { ctx in ctx.beginPage(); ctx.cgContext.scaleBy(x: scale, y: scale); ctx.cgContext.translateBy(x: -bounds.minX, y: -bounds.minY); draw(board, bounds: bounds) }
        return url
    }
    private static func temporary(_ name: String) -> URL {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent(name)
    }
    private static func contentBounds(_ board: RadarBoard) -> CGRect {
        let hidden = CanvasGeometry.hiddenIDs(in: board)
        let rects = board.visibleCards.filter { !hidden.contains($0.id) }.map(CanvasGeometry.cardRect) + (board.groups ?? []).filter { !hidden.contains($0.id) }.compactMap { CanvasGeometry.groupRect($0, in: board) }
        return (rects.dropFirst().reduce(rects.first ?? CGRect(x: 0, y: 0, width: 600, height: 400)) { $0.union($1) }).insetBy(dx: -50, dy: -50)
    }
    private static func containsGroup(_ id: String, under group: RadarGroup, in board: RadarBoard, visited: Set<String> = []) -> Bool {
        guard !visited.contains(group.id) else { return false }
        return (group.groupIDs ?? []).contains(id) || (board.groups ?? []).filter { (group.groupIDs ?? []).contains($0.id) }.contains { containsGroup(id, under: $0, in: board, visited: visited.union([group.id])) }
    }
    private static func draw(_ board: RadarBoard, bounds: CGRect) {
        UIColor(red: 0.965, green: 0.96, blue: 0.935, alpha: 1).setFill(); UIRectFill(bounds)
        let hidden = CanvasGeometry.hiddenIDs(in: board)
        for group in board.groups ?? [] where !hidden.contains(group.id) {
            guard let rect = CanvasGeometry.groupRect(group, in: board) else { continue }
            UIColor.systemGreen.withAlphaComponent(0.07).setFill(); UIColor.systemGreen.withAlphaComponent(0.3).setStroke()
            let path = UIBezierPath(roundedRect: rect, cornerRadius: 22); path.fill(); path.stroke()
            (group.title as NSString).draw(in: CGRect(x: rect.minX + 18, y: rect.minY + 14, width: rect.width - 36, height: 30), withAttributes: [.font: UIFont.boldSystemFont(ofSize: 17)])
        }
        func visibleEndpoint(_ id: String) -> String {
            guard hidden.contains(id) else { return id }
            for group in board.groups ?? [] where group.collapsed == true && !hidden.contains(group.id) {
                if CanvasGeometry.descendants(group, in: board).contains(id) || containsGroup(id, under: group, in: board) { return group.id }
            }
            return id
        }
        for edge in board.edges {
            let fromID = visibleEndpoint(edge.fromID), toID = visibleEndpoint(edge.toID)
            guard fromID != toID, let from = CanvasGeometry.rect(fromID, in: board), let to = CanvasGeometry.rect(toID, in: board) else { continue }
            let (path, start, end, control) = CanvasGeometry.curve(from: from, to: to)
            path.lineWidth = 2; UIColor.darkGray.setStroke(); path.stroke()
            if edge.directed != false {
                let angle = atan2(end.y - control.y, end.x - control.x)
                let arrow = UIBezierPath(); arrow.move(to: CGPoint(x: end.x - 10 * cos(angle - 0.5), y: end.y - 10 * sin(angle - 0.5))); arrow.addLine(to: end); arrow.addLine(to: CGPoint(x: end.x - 10 * cos(angle + 0.5), y: end.y - 10 * sin(angle + 0.5))); arrow.stroke()
            }
            (edge.label as NSString).draw(at: CGPoint(x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 - 17), withAttributes: [.font: UIFont.systemFont(ofSize: 12), .backgroundColor: UIColor.white])
        }
        for card in board.visibleCards where !hidden.contains(card.id) {
            let rect = CanvasGeometry.cardRect(card); card.uiColor.setFill(); UIBezierPath(roundedRect: rect, cornerRadius: 22).fill()
            (card.title as NSString).draw(in: CGRect(x: rect.minX + 20, y: rect.minY + 20, width: rect.width - 40, height: 54), withAttributes: [.font: UIFont.boldSystemFont(ofSize: 20)])
            var y = rect.minY + 80
            for block in card.effectiveBlocks {
                if let asset = block.attachment, let image = CanvasAssets.shared.thumbnail(for: asset), y + 70 < rect.maxY {
                    let height = min(130, rect.maxY - y - 20); image.draw(in: CGRect(x: rect.minX + 20, y: y, width: rect.width - 40, height: height)); y += height + 8
                }
                guard y < rect.maxY - 20 else { break }
                let height = min(90, rect.maxY - y - 20)
                (block.summary as NSString).draw(in: CGRect(x: rect.minX + 20, y: y, width: rect.width - 40, height: height), withAttributes: [.font: UIFont.systemFont(ofSize: 14)])
                y += height + 8
            }
        }
    }
}
