#if DEBUG
import UIKit
import PencilKit
import PDFKit

/// Exercises the production document and system codecs in an isolated UI-test launch.
enum CanvasContentChecks {
    struct Failure: Error { var message: String }
    @MainActor static func run() throws -> [String] {
        var checks: [String] = []
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) throws {
            guard condition() else { throw Failure(message: label) }; checks.append(label)
        }
        let manager = FileManager.default
        let before = Set((try? manager.contentsOfDirectory(atPath: CanvasAssets.shared.directory.path)) ?? [])
        let temp = manager.temporaryDirectory.appendingPathComponent("content-check-" + UUID().uuidString)
        try manager.createDirectory(at: temp, withIntermediateDirectories: true)
        defer {
            let after = Set((try? manager.contentsOfDirectory(atPath: CanvasAssets.shared.directory.path)) ?? [])
            for path in after.subtracting(before) { try? manager.removeItem(at: CanvasAssets.shared.directory.appendingPathComponent(path)) }
            try? manager.removeItem(at: temp)
        }
        let source = Data("{\"id\":\"legacy\",\"kind\":\"text\",\"text\":\"文字\"}".utf8)
        let text = try JSONDecoder().decode(CanvasBlock.self, from: source)
        try expect(text.items.isEmpty && text.text == "文字", "minimal block migration")
        let image = UIGraphicsImageRenderer(size: CGSize(width: 180, height: 120)).image { ctx in
            UIColor.white.setFill(); ctx.fill(CGRect(x: 0, y: 0, width: 180, height: 120))
            ("A → B" as NSString).draw(at: CGPoint(x: 10, y: 40), withAttributes: [.font: UIFont.systemFont(ofSize: 26)])
        }
        let original = image.pngData()!
        let photo = try CanvasAssets.shared.importPhotoData(original)
        let restoredOriginal = try Data(contentsOf: CanvasAssets.shared.url(for: photo)!)
        try expect(restoredOriginal == original, "photo original bytes preserved")
        let retinaFormat = UIGraphicsImageRendererFormat(); retinaFormat.scale = 3
        let largeImage = UIGraphicsImageRenderer(size: CGSize(width: 1200, height: 800), format: retinaFormat).image { ctx in
            UIColor.red.setFill(); ctx.fill(CGRect(x: 0, y: 0, width: 1200, height: 800))
        }
        let largePhoto = try CanvasAssets.shared.importPhotoData(largeImage.jpegData(compressionQuality: 0.8)!)
        let thumbnail = CanvasAssets.shared.thumbnail(for: largePhoto)!
        try expect(max(thumbnail.cgImage!.width, thumbnail.cgImage!.height) <= 600, "thumbnail is bounded to 600 actual pixels")
        var largeCard = RadarCard(title: "像素检查", body: "")
        largeCard.blocks = [CanvasBlock(kind: "image", attachment: largePhoto)]
        let visual = try CanvasAssets.shared.agentImages(for: largeCard)
        let visualImage = UIImage(data: visual[0].data)!
        try expect(max(visualImage.cgImage!.width, visualImage.cgImage!.height) <= 1800, "agent image is bounded to 1800 actual pixels on Retina")
        let points = [CGPoint(x: 15, y: 20), CGPoint(x: 120, y: 60)].enumerated().map { i, point in
            PKStrokePoint(location: point, timeOffset: Double(i) * 0.1, size: CGSize(width: 4, height: 4), opacity: 1, force: 1, azimuth: 0, altitude: .pi / 2)
        }
        let drawing = PKDrawing(strokes: [PKStroke(ink: PKInk(.pen, color: .black), path: PKStrokePath(controlPoints: points, creationDate: Date()))])
        let sketch = try CanvasAssets.shared.saveDrawing(drawing, background: image)
        let reopened = CanvasAssets.shared.drawing(for: sketch)
        try expect(reopened.strokes.count == 1 && reopened.bounds == drawing.bounds, "PencilKit strokes round trip")
        try expect(CanvasAssets.shared.background(for: sketch) != nil, "drawing background preserved")
        var drawingCard = RadarCard(title: "手绘原件", body: "")
        var noThumbnailSketch = sketch; noThumbnailSketch.thumbnailPath = "missing-preview.jpg"
        drawingCard.blocks = [CanvasBlock(kind: "drawing", attachment: noThumbnailSketch)]
        let drawingVisual = try CanvasAssets.shared.agentImages(for: drawingCard)
        let drawingVisualImage = UIImage(data: drawingVisual[0].data)!
        try expect(max(drawingVisualImage.cgImage!.width, drawingVisualImage.cgImage!.height) <= 1800, "drawing vision is rendered from editable original without thumbnail")
        try expect(drawingVisualImage.cgImage!.width > 0, "drawing original remains readable")
        let textURL = temp.appendingPathComponent("note.txt"); try Data("正文依据 123".utf8).write(to: textURL)
        let textAsset = try CanvasAssets.shared.importFile(textURL)
        try expect(CanvasAssets.shared.extractedText(for: textAsset) == "正文依据 123", "text attachment extraction")
        let pdfURL = temp.appendingPathComponent("source.pdf")
        try UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: 300, height: 200)).writePDF(to: pdfURL) { ctx in ctx.beginPage(); ("PDF evidence 456" as NSString).draw(at: CGPoint(x: 20, y: 30), withAttributes: [.font: UIFont.systemFont(ofSize: 16)]) }
        let pdfAsset = try CanvasAssets.shared.importFile(pdfURL)
        try expect(CanvasAssets.shared.extractedText(for: pdfAsset)?.contains("PDF evidence 456") == true, "PDF text extraction")
        var card = RadarCard(id: "original", title: "混合节点", body: "文字", x: 30, y: 50, status: "kept", history: ["旧内容"])
        card.blocks = [text, CanvasBlock(kind: "image", attachment: photo), CanvasBlock(kind: "drawing", attachment: sketch), CanvasBlock(kind: "checklist", items: [CanvasChecklistItem(text: "完成", isChecked: true)]), CanvasBlock(kind: "table", rows: [["A", "B"]]), CanvasBlock(kind: "file", attachment: pdfAsset), CanvasBlock(kind: "file", attachment: textAsset)]
        let other = RadarCard(id: "other", title: "另一节点", body: "B", x: 450)
        var board = RadarBoard(title: "往返画布", question: "", template: "空白", cards: [card, other], edges: [RadarEdge(fromID: card.id, toID: other.id, label: "依赖")])
        board.editHistory = [CanvasEditSession(title: "本机撤销")]; board.activeEditSession = CanvasEditSession(title: "进行中")
        board.groups = [RadarGroup(id: "g", title: "分组", cardIDs: [card.id])]
        let packageURL = try CanvasExport.package(board: board)
        defer { try? manager.removeItem(at: packageURL.deletingLastPathComponent()) }
        let imported = try CanvasExport.importPackage(packageURL)
        try expect(imported.id != board.id && imported.cards.map(\.id) == board.cards.map(\.id), "import uses new board and stable object IDs")
        try expect(imported.editHistory == nil && imported.activeEditSession == nil && imported.redoHistory == nil, "local undo sessions excluded from portable package")
        try expect(imported.edges == board.edges && imported.groups == board.groups, "graph structure round trip")
        try expect(imported.cards[0].status == "kept" && imported.cards[0].history == ["旧内容"] && imported.cards[0].x == 30, "human state and position preserved")
        try expect(imported.cards[0].effectiveBlocks[3].items.first?.isChecked == true, "checklist completed state preserved")
        for block in imported.cards[0].effectiveBlocks {
            if let asset = block.attachment { try expect(CanvasAssets.shared.url(for: asset) != nil, "attachment restored: " + block.kind) }
        }
        let importedSketch = imported.cards[0].effectiveBlocks[2].attachment!
        try expect(CanvasAssets.shared.drawing(for: importedSketch).strokes.count == 1 && CanvasAssets.shared.background(for: importedSketch) != nil, "editable drawing package round trip")
        let png = try CanvasExport.png(board: board), pdf = try CanvasExport.pdf(board: board)
        defer { try? manager.removeItem(at: png.deletingLastPathComponent()); try? manager.removeItem(at: pdf.deletingLastPathComponent()) }
        try expect(UIImage(contentsOfFile: png.path) != nil && PDFDocument(url: pdf)?.pageCount == 1, "PNG and PDF export readable")
        let encoded = try Data(contentsOf: packageURL)
        let json = String(data: encoded, encoding: .utf8)!
        try expect(!json.contains("apiKey") && !json.contains("api_key") && !json.contains("AgentSetup"), "package has no connection credentials")
        var malicious = try JSONDecoder().decode(CanvasExport.Package.self, from: encoded)
        malicious.assets["../outside.txt"] = Data("no".utf8)
        let malformedURL = temp.appendingPathComponent("malformed.radarcanvas")
        try JSONEncoder().encode(malicious).write(to: malformedURL)
        do { _ = try CanvasExport.importPackage(malformedURL); throw Failure(message: "path traversal accepted") }
        catch is CanvasExport.ExportError { checks.append("path traversal rejected") }
        var incomplete = try JSONDecoder().decode(CanvasExport.Package.self, from: encoded)
        incomplete.assets.removeValue(forKey: photo.path)
        try JSONEncoder().encode(incomplete).write(to: malformedURL)
        let partial = try CanvasExport.importPackage(malformedURL)
        try expect(CanvasAssets.shared.url(for: partial.cards[0].effectiveBlocks[1].attachment!) == nil && partial.cards.count == 2, "missing packaged attachment restores placeholder without losing graph")
        var invalid = try JSONDecoder().decode(CanvasExport.Package.self, from: encoded)
        invalid.board.cards[0].width = -1
        try JSONEncoder().encode(invalid).write(to: malformedURL)
        let countBefore = try manager.contentsOfDirectory(atPath: CanvasAssets.shared.directory.path).count
        do { _ = try CanvasExport.importPackage(malformedURL); throw Failure(message: "invalid geometry accepted") }
        catch is CanvasEditError { checks.append("document invariant validation rejects invalid geometry") }
        let countAfter = try manager.contentsOfDirectory(atPath: CanvasAssets.shared.directory.path).count
        try expect(countBefore == countAfter, "failed import writes no assets")
        var missingBoard = board; missingBoard.cards[0].blocks![1].attachment!.path = "does-not-exist.png"
        do { _ = try CanvasExport.package(board: missingBoard); throw Failure(message: "missing asset silently exported") }
        catch is CanvasExport.ExportError { checks.append("missing attachment export retains original document and reports error") }
        do { _ = try CanvasAssets.shared.agentImages(for: missingBoard.cards[0]); throw Failure(message: "missing original silently sent to vision") }
        catch let error as CanvasAssets.VisualError { try expect(error.localizedDescription.contains("原件"), "missing visual original reports readable error") }
        try expect(CanvasAssets.shared.thumbnail(for: missingBoard.cards[0].blocks![1].attachment!) != nil, "missing original leaves thumbnail usable")
        var draftCard = RadarCard(id: "draft", title: "组内正文", body: "过时摘要不应出现", history: ["HIDDEN_PRIVATE_HISTORY"])
        draftCard.blocks = [CanvasBlock(id: "text", kind: "text", text: "当前有效正文"),
                            CanvasBlock(id: "list", kind: "checklist", items: [CanvasChecklistItem(text: "已完成事项", isChecked: true), CanvasChecklistItem(text: "未完成事项")]),
                            CanvasBlock(id: "table", kind: "table", rows: [["列一", "列二"], ["带|竖线", "跨\n两行"], ["不齐的行"]]),
                            CanvasBlock(id: "link", kind: "link", text: "外部参考", url: "https://example.com/only-link"),
                            CanvasBlock(id: "attachment", kind: "image", attachment: photo)]
        draftCard.sourceIDs = ["reference"]
        var nestedCard = RadarCard(id: "nested", title: "子组内容", body: "子组当前正文"); nestedCard.sourceIDs = ["reference"]
        let archivedCard = RadarCard(id: "archived", title: "HIDDEN_ARCHIVED", body: "HIDDEN_ARCHIVED_BODY", status: "archived")
        let ungroupedCard = RadarCard(id: "ungrouped", title: "散落内容", body: "散落当前正文")
        var draft = RadarBoard(title: "可读工作稿", question: "本次问题", template: "空白", cards: [ungroupedCard, nestedCard, draftCard, archivedCard], edges: [RadarEdge(id: "visible", fromID: "draft", toID: "nested", label: "后续"), RadarEdge(id: "hidden", fromID: "draft", toID: "archived", label: "HIDDEN_EDGE")])
        draft.groups = [RadarGroup(id: "child", title: "子分组", cardIDs: ["nested"]), RadarGroup(id: "parent", title: "父分组", cardIDs: ["draft", "draft", "archived"], groupIDs: ["child", "child"])]
        draft.sources = [RadarSource(id: "reference", title: "来源一", url: "https://example.com/source", excerpt: ""), RadarSource(id: "unused", title: "HIDDEN_UNREFERENCED_SOURCE", url: "https://example.com/private", excerpt: "")]
        draft.messages = [RadarMessage(role: "user", content: "HIDDEN_PRIVATE_CHAT_AND_KEY")]
        let markdown = CanvasExport.markdownText(board: draft)
        func position(_ needle: String) -> Int { markdown.range(of: needle).map { markdown.distance(from: markdown.startIndex, to: $0.lowerBound) } ?? Int.max }
        try expect(position("## 父分组") < position("### 组内正文") && position("### 组内正文") < position("### 子分组") && position("### 子分组") < position("## 未分组内容"), "Markdown follows root cards child groups then ungrouped order")
        try expect(markdown.components(separatedBy: "### 组内正文").count == 2 && markdown.components(separatedBy: "#### 子组内容").count == 2, "Markdown emits each node once despite repeated membership")
        try expect(markdown.contains("当前有效正文") && !markdown.contains("过时摘要不应出现") && markdown.contains("散落当前正文"), "Markdown uses current rich content and legacy body")
        try expect(markdown.contains("- [x] 已完成事项") && markdown.contains("- [ ] 未完成事项"), "Markdown preserves checklist decisions")
        try expect(markdown.contains("带\\|竖线") && markdown.contains("跨<br>两行") && markdown.contains("| 不齐的行 |  |"), "Markdown escapes table delimiters and pads ragged rows")
        try expect(markdown.contains("https://example.com/only-link") && markdown.contains("已保存链接，暂无摘录"), "Markdown retains traceable links without claiming they were read")
        try expect(markdown.components(separatedBy: "### 来源一").count == 2 && !markdown.contains("HIDDEN_"), "Markdown excludes archived content private history chat and unused sources")
        try expect(markdown.contains("附件：") && markdown.contains(photo.name) && !markdown.contains(photo.path) && !markdown.contains(photo.thumbnailPath ?? "UNLIKELY_SENTINEL"), "Markdown describes attachments without local paths")
        var unsafe = draft
        unsafe.cards[0].blocks = [CanvasBlock(kind: "link", url: "https://user:PRIVATE_CREDENTIAL@example.com/source"), CanvasBlock(kind: "link", url: "file:///PRIVATE_LOCAL_PATH")]
        let sanitized = CanvasExport.markdownText(board: unsafe)
        try expect(!sanitized.contains("PRIVATE_CREDENTIAL") && !sanitized.contains("PRIVATE_LOCAL_PATH"), "Markdown excludes authenticated and local link locations")
        let markdownURL = try CanvasExport.markdown(board: draft)
        defer { try? manager.removeItem(at: markdownURL.deletingLastPathComponent()) }
        let exportedMarkdown = try String(contentsOf: markdownURL, encoding: .utf8)
        try expect(exportedMarkdown == markdown && markdownURL.pathExtension == "md", "Markdown export writes the real UTF8 reading draft")
        return checks
    }
}
#endif
