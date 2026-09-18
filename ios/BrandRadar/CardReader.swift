import SwiftUI
import QuickLook
import AVKit

/// Reads the live document by identity; never holds an editable stale card copy.
struct CardReader: View {
    @ObservedObject var store: BoardStore
    let boardID: String
    let cardID: String
    var onEdit: (String) -> Void
    var onContinue: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var preview: URL?
    private var board: RadarBoard? { store.boards.first { $0.id == boardID } }
    private var card: RadarCard? { board?.visibleCards.first { $0.id == cardID } }
    var body: some View {
        NavigationStack {
            Group {
                if let card {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            Text(card.title).font(.title2.bold()).textSelection(.enabled).accessibilityAddTraits(.isHeader)
                            HStack {
                                Label(card.label, systemImage: card.symbol)
                                if card.status == "kept" { Label("已采用", systemImage: "checkmark.circle") }
                            }.font(.subheadline).foregroundStyle(Color(CanvasStyle.secondary))
                            ForEach(card.effectiveBlocks) { block in read(block) }
                            let sources = (board?.sources ?? []).filter { card.sourceIDs.contains($0.id) }
                            if !sources.isEmpty {
                                Divider()
                                Text("来源").font(.headline)
                                ForEach(sources) { source in
                                    VStack(alignment: .leading, spacing: 8) {
                                        if let raw = source.url, let url = webURL(raw) { Link(source.title, destination: url).frame(minHeight: 44, alignment: .leading) }
                                        else { Text(source.title).font(.headline) }
                                        if !source.excerpt.isEmpty { Text(source.excerpt).textSelection(.enabled) }
                                        else if source.url != nil { Text("已保存链接，尚无原文摘录").font(.subheadline).foregroundStyle(.secondary) }
                                    }
                                }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
                    }.accessibilityIdentifier("cardReaderContent")
                } else {
                    ContentUnavailableView {
                        Label("这张卡片已放下或移除", systemImage: "tray")
                    } actions: { Button("回到画布") { dismiss() }.frame(minHeight: 44) }
                }
            }
            .font(.body).foregroundStyle(Color(CanvasStyle.ink))
            .background(RadarPalette.paper)
            .navigationTitle("阅读").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("关闭") { dismiss() }.accessibilityIdentifier("closeCardReader") }
                ToolbarItemGroup(placement: .bottomBar) {
                    Button("继续改", systemImage: "bubble.left") { if card != nil { onContinue(cardID) } }.disabled(card == nil).accessibilityIdentifier("readerContinue")
                    Spacer()
                    Button("编辑", systemImage: "pencil") { if card != nil { onEdit(cardID) } }.disabled(card == nil).accessibilityIdentifier("readerEdit")
                }
            }
        }.tint(RadarPalette.green).quickLookPreview($preview)
    }
    private func webURL(_ value: String) -> URL? {
        guard let url = URL(string: value), ["https", "http"].contains(url.scheme?.lowercased() ?? "") else { return nil }; return url
    }
    @ViewBuilder private func read(_ block: CanvasBlock) -> some View {
        switch block.kind {
        case "text":
            Text(block.text).font(block.emphasis == "heading" ? .headline : .body).bold(block.emphasis == "bold")
                .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
        case "checklist":
            VStack(alignment: .leading, spacing: 12) {
                ForEach(block.items) { item in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: item.isChecked ? "checkmark.circle.fill" : "circle").accessibilityHidden(true)
                        Text(item.text).strikethrough(item.isChecked).textSelection(.enabled)
                    }.accessibilityElement(children: .combine).accessibilityValue(item.isChecked ? "已完成" : "未完成")
                }
            }
        case "table":
            ScrollView(.horizontal) {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(block.rows.indices, id: \.self) { row in
                        HStack(alignment: .top, spacing: 0) {
                            ForEach(0..<(block.rows.map(\.count).max() ?? 0), id: \.self) { column in
                                Text(column < block.rows[row].count ? block.rows[row][column] : "")
                                    .font(row == 0 ? .headline : .body).textSelection(.enabled)
                                    .frame(width: 160, alignment: .leading).padding(12)
                                    .frame(maxHeight: .infinity, alignment: .top)
                                    .background(row == 0 ? RadarPalette.sage : RadarPalette.paper)
                                    .overlay(Rectangle().stroke(Color(CanvasStyle.border), lineWidth: 0.5))
                            }
                        }.fixedSize(horizontal: false, vertical: true)
                    }
                }
            }.accessibilityLabel("表格，\(block.rows.count) 行")
        case "link":
            VStack(alignment: .leading, spacing: 8) {
                if !block.text.isEmpty { Text(block.text).textSelection(.enabled) }
                if let url = webURL(block.url) { Link(block.url, destination: url).frame(minHeight: 44, alignment: .leading) }
                else { Text(block.url).textSelection(.enabled) }
            }
        default:
            VStack(alignment: .leading, spacing: 12) {
                if let asset = block.attachment, let url = CanvasAssets.shared.url(for: asset) {
                    if ["audio", "video"].contains(block.kind) { ReaderMedia(url: url).frame(height: block.kind == "audio" ? 120 : 260) }
                    else if let image = CanvasAssets.shared.thumbnail(for: asset) {
                        Button {
                            preview = block.kind == "drawing" ? asset.thumbnailPath.map { CanvasAssets.shared.directory.appendingPathComponent($0) } : url
                        } label: { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 420) }
                            .buttonStyle(.plain).accessibilityLabel("查看\(asset.name)")
                    } else { Button(asset.name, systemImage: "doc") { preview = url }.frame(minHeight: 44) }
                    ShareLink(item: url) { Label("分享附件", systemImage: "square.and.arrow.up") }.frame(minHeight: 44)
                } else { Label("附件暂不可用", systemImage: "doc.badge.ellipsis").foregroundStyle(.secondary) }
                if !block.text.isEmpty { Text(block.text).textSelection(.enabled) }
            }
        }
    }
}
private struct ReaderMedia: View {
    let url: URL
    @State private var player: AVPlayer?
    var body: some View {
        VideoPlayer(player: player).onAppear { player = AVPlayer(url: url) }.onDisappear { player?.pause() }
    }
}
