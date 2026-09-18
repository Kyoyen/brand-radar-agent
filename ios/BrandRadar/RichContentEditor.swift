import SwiftUI
import PhotosUI
import PencilKit
import QuickLook
import AVKit
import UniformTypeIdentifiers

struct RichContentEditor: View {
    @Binding var blocks: [CanvasBlock]
    var split: (String) -> Void
    @State private var photo: PhotosPickerItem?
    @State private var importing = false
    @State private var drawingID: String?
    @State private var preview: URL?
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            ForEach($blocks) { $block in
                VStack(alignment: .leading, spacing: 10) {
                    blockEditor($block)
                    HStack {
                        Spacer()
                        Menu {
                            Button("上移", systemImage: "arrow.up") { move(block.id, by: -1) }
                            Button("下移", systemImage: "arrow.down") { move(block.id, by: 1) }
                            Button("保存并转为节点", systemImage: "square.on.square") { split(block.id) }.accessibilityIdentifier("splitBlock_\(block.id)")
                            Button("删除", systemImage: "trash", role: .destructive) { blocks.removeAll { $0.id == block.id } }
                        } label: { Image(systemName: "ellipsis").padding(8) }.accessibilityLabel("内容操作")
                    }
                }.padding(12).background(.white.opacity(0.45), in: RoundedRectangle(cornerRadius: 16))
            }
            HStack(spacing: 22) {
                Menu {
                    Button("文字") { blocks.append(CanvasBlock()) }
                    Button("清单") { blocks.append(CanvasBlock(kind: "checklist", items: [CanvasChecklistItem()])) }
                    Button("表格") { blocks.append(CanvasBlock(kind: "table", rows: [["", ""], ["", ""]])) }
                    Button("链接") { blocks.append(CanvasBlock(kind: "link")) }
                    Button("手绘") { let block = CanvasBlock(kind: "drawing"); blocks.append(block); drawingID = block.id }
                    Button("文件或音视频") { importing = true }
                } label: { Label("添加内容", systemImage: "plus.circle") }.accessibilityIdentifier("addContentBlock")
                PhotosPicker(selection: $photo, matching: .images) { Label("图片", systemImage: "photo") }
            }.font(.subheadline)
            if let error { Text(error).font(.caption).foregroundStyle(.red) }
        }
        .onChange(of: photo) { _, value in Task {
            do {
                if let data = try await value?.loadTransferable(type: Data.self) {
                    let asset = try CanvasAssets.shared.importPhotoData(data)
                    blocks.append(CanvasBlock(kind: "image", attachment: asset))
                }
            } catch { self.error = "图片未能导入，请重试。" }
            photo = nil
        } }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.item]) { result in
            do {
                let asset = try CanvasAssets.shared.importFile(result.get())
                let type = UTType(asset.contentType)
                let kind = type?.conforms(to: .audio) == true ? "audio" : type?.conforms(to: .movie) == true ? "video" : type?.conforms(to: .image) == true ? "image" : "file"
                blocks.append(CanvasBlock(kind: kind, attachment: asset))
            } catch { self.error = "文件未能导入，请重试。" }
        }
        .sheet(isPresented: Binding(get: { drawingID != nil }, set: { if !$0 { drawingID = nil } })) {
            if let id = drawingID, let block = blocks.first(where: { $0.id == id }) {
                DrawingEditor(asset: block.kind == "drawing" ? block.attachment : nil,
                              background: block.kind == "image" ? block.attachment.flatMap { CanvasAssets.shared.url(for: $0) }.flatMap { UIImage(contentsOfFile: $0.path) } : block.attachment.flatMap { CanvasAssets.shared.background(for: $0) }) { asset in
                    if let index = blocks.firstIndex(where: { $0.id == id }) {
                        if blocks[index].kind == "image" { blocks.insert(CanvasBlock(kind: "drawing", attachment: asset), at: index + 1) }
                        else { blocks[index].attachment = asset }
                    }
                    drawingID = nil
                }
            }
        }
        .quickLookPreview($preview)
    }
    @ViewBuilder private func blockEditor(_ binding: Binding<CanvasBlock>) -> some View {
        let block = binding.wrappedValue
        switch block.kind {
        case "text":
            TextEditor(text: binding.text).frame(minHeight: 100).scrollContentBackground(.hidden)
                .font(block.emphasis == "heading" ? .title3 : .body).bold(block.emphasis == "bold")
                .accessibilityIdentifier("cardBodyInput")
            Picker("文字样式", selection: binding.emphasis) { Text("正文").tag("plain"); Text("加粗").tag("bold"); Text("标题").tag("heading"); Text("列表").tag("list") }.pickerStyle(.segmented).onChange(of: binding.emphasis.wrappedValue) { _, style in
                if style == "list" { binding.text.wrappedValue = binding.text.wrappedValue.components(separatedBy: "\n").map { $0.hasPrefix("• ") ? $0 : "• " + $0 }.joined(separator: "\n") }
            }
        case "checklist":
            ChecklistBlockEditor(block: binding)
        case "table":
            TableBlockEditor(block: binding)
        case "link":
            TextField("标题与说明", text: binding.text, axis: .vertical)
            TextField("https://", text: binding.url).keyboardType(.URL).textInputAutocapitalization(.never)
            if let url = URL(string: block.url), ["https", "http"].contains(url.scheme ?? "") { Link("打开链接", destination: url) }
        default:
            if let asset = block.attachment, let url = CanvasAssets.shared.url(for: asset) {
                if block.kind == "audio" || block.kind == "video" { MediaBlock(url: url).frame(height: block.kind == "audio" ? 110 : 230) }
                else if let image = CanvasAssets.shared.thumbnail(for: asset) {
                    Button { preview = block.kind == "drawing" ? asset.thumbnailPath.map { CanvasAssets.shared.directory.appendingPathComponent($0) } : url } label: { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 260) }.buttonStyle(.plain)
                } else { Button(asset.name, systemImage: "doc") { preview = url } }
                HStack {
                    if block.kind == "image" || block.kind == "drawing" { Button(block.kind == "image" ? "批注" : "继续画", systemImage: "pencil.tip") { drawingID = block.id } }
                    Spacer(); ShareLink(item: url) { Image(systemName: "square.and.arrow.up") }
                }.font(.caption)
            } else if block.kind == "drawing" { Button("开始画", systemImage: "pencil.tip") { drawingID = block.id } }
            else { Label("附件暂不可用", systemImage: "doc.badge.ellipsis").foregroundStyle(.secondary) }
            TextField("添加说明", text: binding.text, axis: .vertical)
        }
    }
    private func move(_ id: String, by offset: Int) { guard let i = blocks.firstIndex(where: { $0.id == id }), blocks.indices.contains(i + offset) else { return }; blocks.swapAt(i, i + offset) }
    private func moveItem(_ blockID: String, _ itemID: String, _ offset: Int) {
        guard let b = blocks.firstIndex(where: { $0.id == blockID }), let i = blocks[b].items.firstIndex(where: { $0.id == itemID }), blocks[b].items.indices.contains(i + offset) else { return }; blocks[b].items.swapAt(i, i + offset)
    }
}
private extension Array { subscript(safe index: Int) -> Element? { indices.contains(index) ? self[index] : nil } }
private struct MediaBlock: View {
    let url: URL
    @State private var player: AVPlayer?
    var body: some View { VideoPlayer(player: player).onAppear { player = AVPlayer(url: url) }.onDisappear { player?.pause() } }
}

struct DrawingEditor: View {
    var asset: CanvasAttachment?
    var background: UIImage?
    var save: (CanvasAttachment) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var canvas = PKCanvasView()
    @State private var error: String?
    var body: some View {
        NavigationStack {
            DrawingSurface(canvas: canvas, asset: asset, background: background).ignoresSafeArea(edges: .bottom)
                .navigationTitle("手绘").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItemGroup(placement: .topBarLeading) {
                        Button("取消") { dismiss() }
                        Button { canvas.undoManager?.undo() } label: { Image(systemName: "arrow.uturn.backward") }
                            .accessibilityLabel("撤销笔迹").accessibilityIdentifier("drawingUndoButton")
                        Button { canvas.undoManager?.redo() } label: { Image(systemName: "arrow.uturn.forward") }
                            .accessibilityLabel("重做笔迹").accessibilityIdentifier("drawingRedoButton")
                    }
                    ToolbarItem(placement: .confirmationAction) { Button("保存") { do { save(try CanvasAssets.shared.saveDrawing(canvas.drawing, background: background)) } catch { self.error = "手绘未保存，请重试。" } }.accessibilityIdentifier("saveDrawingButton") }
                }.alert("无法保存", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) { Button("好") { error = nil } } message: { Text(error ?? "") }
        }
    }
}
private struct DrawingSurface: UIViewRepresentable {
    let canvas: PKCanvasView
    var asset: CanvasAttachment?
    var background: UIImage?
    final class Coordinator: NSObject, PKCanvasViewDelegate {
        let picker = PKToolPicker()
        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) { updateAccessibility(canvasView) }
        func updateAccessibility(_ canvas: PKCanvasView) {
            let bounds = canvas.drawing.bounds
            canvas.accessibilityValue = "\(canvas.drawing.strokes.count) 条笔迹，宽 \(Int(bounds.isNull ? 0 : bounds.width))，高 \(Int(bounds.isNull ? 0 : bounds.height))"
        }
    }
    func makeCoordinator() -> Coordinator { Coordinator() }
    func makeUIView(context: Context) -> PKCanvasView {
        canvas.drawingPolicy = .anyInput
        canvas.accessibilityIdentifier = "drawingSurface"
        canvas.accessibilityLabel = "手绘画纸"
        canvas.isAccessibilityElement = true
        canvas.delegate = context.coordinator
        canvas.tool = PKInkingTool(.pen, color: .black, width: 4)
        canvas.backgroundColor = background == nil ? .white : .clear
        canvas.isOpaque = false
        canvas.contentSize = background?.size ?? CGSize(width: 800, height: 1000)
        canvas.minimumZoomScale = 0.25; canvas.maximumZoomScale = 3
        if let asset { canvas.drawing = CanvasAssets.shared.drawing(for: asset) }
        if let background {
            let view = UIImageView(image: background); view.frame = CGRect(origin: .zero, size: background.size); view.contentMode = .scaleToFill; canvas.insertSubview(view, at: 0)
        }
        context.coordinator.updateAccessibility(canvas)
        context.coordinator.picker.addObserver(canvas)
        DispatchQueue.main.async { canvas.zoomScale = min(1, canvas.bounds.width / canvas.contentSize.width); canvas.becomeFirstResponder(); context.coordinator.picker.setVisible(true, forFirstResponder: canvas) }
        return canvas
    }
    func updateUIView(_ uiView: PKCanvasView, context: Context) {}
}

private struct ChecklistBlockEditor: View {
    @Binding var block: CanvasBlock
    @State private var editingID: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach($block.items) { $item in
                HStack(alignment: .center, spacing: 0) {
                    Button { item.isChecked.toggle() } label: {
                        Image(systemName: item.isChecked ? "checkmark.circle.fill" : "circle")
                            .font(.system(size: 23, weight: .regular)).foregroundStyle(item.isChecked ? RadarPalette.green : .secondary)
                            .frame(width: 48, height: 48).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityLabel(item.isChecked ? "标为未完成" : "标为完成")
                        .accessibilityValue(item.text).accessibilityIdentifier("checklistToggle_\(item.id)")
                    Button { editingID = item.id } label: {
                        Text(item.text.isEmpty ? "事项" : item.text).font(.body)
                            .foregroundStyle(item.isChecked || item.text.isEmpty ? .secondary : .primary)
                            .strikethrough(item.isChecked, color: .secondary.opacity(0.5))
                            .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("checklistText_\(item.id)")
                    Menu {
                        Button("编辑", systemImage: "pencil") { editingID = item.id }
                        Button("上移", systemImage: "arrow.up") { move(item.id, -1) }.disabled(block.items.first?.id == item.id)
                        Button("下移", systemImage: "arrow.down") { move(item.id, 1) }.disabled(block.items.last?.id == item.id)
                        Button("删除", systemImage: "trash", role: .destructive) { block.items.removeAll { $0.id == item.id } }
                    } label: { Image(systemName: "ellipsis").font(.subheadline).foregroundStyle(.secondary).frame(width: 44, height: 48).contentShape(Rectangle()) }
                    .accessibilityLabel("事项操作")
                }
                if item.id != block.items.last?.id { Divider().padding(.leading, 48) }
            }
            Button { let item = CanvasChecklistItem(); block.items.append(item); editingID = item.id } label: {
                Label("添加事项", systemImage: "plus").font(.subheadline).frame(minHeight: 44).padding(.leading, 12)
            }
        }.sheet(isPresented: Binding(get: { editingID != nil }, set: { if !$0 { editingID = nil } })) {
            if let id = editingID, let index = block.items.firstIndex(where: { $0.id == id }) {
                ContentTextSheet(title: "事项", value: $block.items[index].text)
            }
        }
    }
    private func move(_ id: String, _ offset: Int) {
        guard let index = block.items.firstIndex(where: { $0.id == id }), block.items.indices.contains(index + offset) else { return }
        block.items.swapAt(index, index + offset)
    }
}

private struct TableBlockEditor: View {
    @Binding var block: CanvasBlock
    @State private var selection: TableCell?
    private struct TableCell: Identifiable { var row: Int; var column: Int; var id: String { "\(row)_\(column)" } }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                if !block.text.isEmpty { Text(block.text).font(.headline).frame(maxWidth: .infinity, alignment: .leading) }
                Spacer(minLength: 0)
                Menu {
                    Button("添加行", systemImage: "plus") { block.rows.append(Array(repeating: "", count: max(1, block.rows.first?.count ?? 2))) }
                    Button("添加列", systemImage: "plus") { block.rows = block.rows.isEmpty ? [[""]] : block.rows.map { $0 + [""] } }
                    Button("删除末行", role: .destructive) { if !block.rows.isEmpty { block.rows.removeLast() } }
                    Button("删除末列", role: .destructive) { block.rows = block.rows.map { Array($0.dropLast()) } }
                } label: { Label("编辑表格", systemImage: "tablecells").font(.caption).frame(minHeight: 44) }
                .accessibilityIdentifier("tableActions_\(block.id)")
            }
            ScrollView(.horizontal) {
                VStack(spacing: 1) {
                    ForEach(block.rows.indices, id: \.self) { row in
                        HStack(spacing: 1) {
                            ForEach(block.rows[row].indices, id: \.self) { column in
                                Button { selection = TableCell(row: row, column: column) } label: {
                                    Text(block.rows[row][column].isEmpty ? (row == 0 ? "列 \(column + 1)" : "—") : block.rows[row][column])
                                        .font(row == 0 ? .subheadline.weight(.semibold) : .subheadline)
                                        .foregroundStyle(block.rows[row][column].isEmpty ? .secondary : .primary)
                                        .multilineTextAlignment(.leading).lineLimit(4)
                                        .frame(width: 112, height: rowHeight(row) - 24, alignment: .leading).padding(12)
                                        .background(row == 0 ? RadarPalette.sage.opacity(0.65) : row.isMultiple(of: 2) ? Color.white.opacity(0.5) : RadarPalette.paper)
                                        .contentShape(Rectangle())
                                }.buttonStyle(.plain).accessibilityLabel("第 \(row + 1) 行，第 \(column + 1) 列，\(block.rows[row][column].isEmpty ? "空白" : block.rows[row][column])")
                                    .accessibilityIdentifier("tableCell_\(row)_\(column)")
                            }
                        }
                    }
                }.background(.black.opacity(0.07)).clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(.black.opacity(0.07)))
            }.scrollIndicators(.visible)
        }.sheet(item: $selection) { cell in
            if block.rows.indices.contains(cell.row), block.rows[cell.row].indices.contains(cell.column) {
                ContentTextSheet(title: cellTitle(cell.row, cell.column), value: $block.rows[cell.row][cell.column])
            }
        }
    }
    private func cellTitle(_ row: Int, _ column: Int) -> String {
        if row == 0 { return "列标题" }
        guard let first = block.rows.first, first.indices.contains(column), !first[column].isEmpty else { return "单元格" }
        return first[column]
    }
    private func rowHeight(_ row: Int) -> CGFloat {
        let font = UIFont.preferredFont(forTextStyle: .subheadline)
        return max(48, min(font.lineHeight * 4 + 24, block.rows[row].map { ($0 as NSString).boundingRect(with: CGSize(width: 112, height: 1000), options: [.usesLineFragmentOrigin, .usesFontLeading], attributes: [.font: font], context: nil).height + 24 }.max() ?? 48))
    }
}

private struct ContentTextSheet: View {
    var title: String
    @Binding var value: String
    @Environment(\.dismiss) private var dismiss
    @FocusState private var focused: Bool
    var body: some View {
        NavigationStack {
            TextEditor(text: $value).font(.body).padding(16).scrollContentBackground(.hidden)
                .focused($focused).accessibilityIdentifier("contentValueInput")
                .background(RadarPalette.paper).navigationTitle(title).navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() }.accessibilityIdentifier("finishContentValue") } }
                .onAppear { focused = true }
        }.presentationDetents([.medium, .large]).presentationDragIndicator(.visible)
    }
}
