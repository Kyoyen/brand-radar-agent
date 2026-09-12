import UIKit
import PDFKit
import PencilKit
import UniformTypeIdentifiers
import ImageIO

final class CanvasAssets {
    static let shared = CanvasAssets()
    let directory: URL
    private let thumbnails = NSCache<NSString, UIImage>()
    init(directory: URL? = nil) {
        self.directory = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("CanvasAssets", isDirectory: true)
        thumbnails.totalCostLimit = 24 * 1024 * 1024
        try? FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
    }
    func url(for asset: CanvasAttachment) -> URL? {
        guard asset.path == URL(fileURLWithPath: asset.path).lastPathComponent, !asset.path.hasPrefix(".") else { return nil }
        let url = directory.appendingPathComponent(asset.path)
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }
    func thumbnail(for asset: CanvasAttachment) -> UIImage? {
        let key = (asset.thumbnailPath ?? asset.path) as NSString
        if let cached = thumbnails.object(forKey: key) { return cached }
        var image: UIImage?
        if let path = asset.thumbnailPath, path == URL(fileURLWithPath: path).lastPathComponent {
            image = UIImage(contentsOfFile: directory.appendingPathComponent(path).path)
        }
        if image == nil, let url = url(for: asset) {
            let options: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceThumbnailMaxPixelSize: 600, kCGImageSourceCreateThumbnailWithTransform: true]
            if let source = CGImageSourceCreateWithURL(url as CFURL, nil), let cg = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) { image = UIImage(cgImage: cg) }
        }
        if let image { thumbnails.setObject(image, forKey: key, cost: Int(image.size.width * image.size.height * 4)) }
        return image
    }
    func importFile(_ source: URL) throws -> CanvasAttachment {
        let access = source.startAccessingSecurityScopedResource(); defer { if access { source.stopAccessingSecurityScopedResource() } }
        let id = UUID().uuidString, ext = source.pathExtension.lowercased()
        let target = directory.appendingPathComponent(id + (ext.isEmpty ? "" : "." + ext))
        try FileManager.default.copyItem(at: source, to: target)
        let size = (try target.resourceValues(forKeys: [.fileSizeKey])).fileSize ?? 0
        var asset = CanvasAttachment(id: id, name: source.lastPathComponent, contentType: UTType(filenameExtension: ext)?.identifier ?? UTType.data.identifier, path: target.lastPathComponent, byteCount: size)
        if let image = UIImage(contentsOfFile: target.path) { asset.thumbnailPath = try saveThumbnail(image, id: id) }
        else if ext == "pdf", let page = PDFDocument(url: target)?.page(at: 0) { asset.thumbnailPath = try saveThumbnail(page.thumbnail(of: CGSize(width: 500, height: 600), for: .mediaBox), id: id) }
        return asset
    }
    func importPhotoData(_ data: Data) throws -> CanvasAttachment {
        guard let image = UIImage(data: data) else { throw CocoaError(.fileReadCorruptFile) }
        let identifier = CGImageSourceCreateWithData(data as CFData, nil).flatMap { CGImageSourceGetType($0) as String? } ?? UTType.image.identifier
        let ext = UTType(identifier)?.preferredFilenameExtension ?? "image"
        let id = UUID().uuidString, path = id + "." + ext
        try data.write(to: directory.appendingPathComponent(path), options: .atomic)
        return CanvasAttachment(id: id, name: "图片." + ext, contentType: identifier, path: path, thumbnailPath: try saveThumbnail(image, id: id), byteCount: data.count)
    }
    func importImage(_ image: UIImage) throws -> CanvasAttachment {
        let data = image.jpegData(compressionQuality: 0.9) ?? Data()
        let id = UUID().uuidString, path = id + ".jpg"
        try data.write(to: directory.appendingPathComponent(path), options: .atomic)
        return CanvasAttachment(id: id, name: "图片.jpg", contentType: UTType.jpeg.identifier, path: path, thumbnailPath: try saveThumbnail(image, id: id), byteCount: data.count)
    }
    func saveDrawing(_ drawing: PKDrawing, background: UIImage? = nil) throws -> CanvasAttachment {
        let id = UUID().uuidString, path = id + ".drawing", data = drawing.dataRepresentation()
        try data.write(to: directory.appendingPathComponent(path), options: .atomic)
        let image = drawingImage(drawing, background: background, maximumPixels: 600)
        let preview = id + "-thumb.jpg"
        try image.jpegData(compressionQuality: 0.85)?.write(to: directory.appendingPathComponent(preview), options: .atomic)
        if let background { try background.jpegData(compressionQuality: 0.95)?.write(to: directory.appendingPathComponent(id + "-background.jpg"), options: .atomic) }
        return CanvasAttachment(id: id, name: "手绘", contentType: "com.apple.pencilkit.drawing", path: path, thumbnailPath: preview, byteCount: data.count)
    }
    func drawing(for asset: CanvasAttachment) -> PKDrawing {
        guard let url = url(for: asset), let data = try? Data(contentsOf: url), let drawing = try? PKDrawing(data: data) else { return PKDrawing() }
        return drawing
    }
    func background(for asset: CanvasAttachment) -> UIImage? { UIImage(contentsOfFile: directory.appendingPathComponent(asset.id + "-background.jpg").path) }
    func extractedText(for asset: CanvasAttachment) -> String? {
        guard let url = url(for: asset) else { return nil }
        if asset.contentType == UTType.pdf.identifier { return PDFDocument(url: url)?.string.map { String($0.prefix(60_000)) } }
        if UTType(asset.contentType)?.conforms(to: .text) == true { return (try? String(contentsOf: url, encoding: .utf8)).map { String($0.prefix(60_000)) } }
        return nil
    }
    private func drawingImage(_ drawing: PKDrawing, background: UIImage?, maximumPixels: CGFloat) -> UIImage {
        let page = CGRect(origin: .zero, size: background?.size ?? CGSize(width: 800, height: 1000))
        let bounds = drawing.bounds.isNull || drawing.bounds.isEmpty ? page : page.union(drawing.bounds.insetBy(dx: -10, dy: -10))
        let ratio = min(1, maximumPixels / max(bounds.width, bounds.height))
        let size = CGSize(width: max(1, floor(bounds.width * ratio)), height: max(1, floor(bounds.height * ratio)))
        let format = UIGraphicsImageRendererFormat(); format.scale = 1
        return UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            UIColor.white.setFill(); ctx.fill(CGRect(origin: .zero, size: size))
            ctx.cgContext.scaleBy(x: ratio, y: ratio); ctx.cgContext.translateBy(x: -bounds.minX, y: -bounds.minY)
            background?.draw(in: page)
            drawing.image(from: bounds, scale: ratio).draw(in: bounds)
        }
    }
    private func saveThumbnail(_ image: UIImage, id: String) throws -> String {
        let ratio = min(1, 600 / max(image.size.width, image.size.height))
        let size = CGSize(width: max(1,image.size.width * ratio), height: max(1,image.size.height * ratio))
        let format = UIGraphicsImageRendererFormat(); format.scale = 1
        let preview = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        let path = id + "-thumb.jpg"
        try preview.jpegData(compressionQuality: 0.8)?.write(to: directory.appendingPathComponent(path), options: .atomic)
        return path
    }
}

extension CanvasAssets {
    enum VisualError: LocalizedError {
        case unavailable(String)
        var errorDescription: String? {
            switch self { case .unavailable(let name): return "无法读取“\(name)”的原件，请重新添加后再整理成图。" }
        }
    }
    func agentImages(for card: RadarCard) throws -> [DirectAgentImage] {
        try card.effectiveBlocks.filter { ["image", "drawing"].contains($0.kind) }.prefix(4).map { block in
            guard let asset = block.attachment, let original = url(for: asset) else { throw VisualError.unavailable(block.attachment?.name ?? "素材") }
            let image: UIImage
            if block.kind == "drawing" {
                guard let data = try? Data(contentsOf: original), let drawing = try? PKDrawing(data: data) else { throw VisualError.unavailable(asset.name) }
                let backgroundURL = directory.appendingPathComponent(asset.id + "-background.jpg")
                let background = background(for: asset)
                if FileManager.default.fileExists(atPath: backgroundURL.path), background == nil { throw VisualError.unavailable(asset.name + "背景") }
                image = drawingImage(drawing, background: background, maximumPixels: 1800)
            } else {
                guard let originalImage = UIImage(contentsOfFile: original.path) else { throw VisualError.unavailable(asset.name) }
                image = originalImage
            }
            let ratio = min(1, 1800 / max(image.size.width, image.size.height))
            let size = CGSize(width: max(1, floor(image.size.width * ratio)), height: max(1, floor(image.size.height * ratio)))
            let format = UIGraphicsImageRendererFormat(); format.scale = 1
            let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
            guard let data = resized.jpegData(compressionQuality: 0.8) else { throw VisualError.unavailable(asset.name) }
            return DirectAgentImage(data: data, mimeType: "image/jpeg", sourceID: block.id)
        }
    }
    func agentText(for card: RadarCard) -> String {
        card.effectiveBlocks.map { block in
            let text = block.attachment.flatMap { extractedText(for: $0) } ?? ""
            return "[内容块 \(block.id)]\n\(block.summary)" + (text.isEmpty ? "" : "\n附件文本：\n" + text)
        }.joined(separator: "\n\n")
    }
}
