import SwiftUI

struct CurrentArchiveSheet: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @State private var restoring: RadarCard?
    private var archived: [RadarCard] { store.current.cards.filter { $0.status == "archived" } }
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    Text(store.current.title).font(.subheadline).foregroundStyle(.secondary)
                    if archived.isEmpty {
                        ContentUnavailableView("没有放下的内容", systemImage: "archivebox")
                    }
                    ForEach(archived) { card in
                        Button { restoring = card } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 7) {
                                    Text(card.title).font(.headline).lineLimit(2)
                                    Text(card.effectiveBlocks.first?.summary ?? card.body).font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
                                }
                                Spacer(); Image(systemName: "arrow.uturn.backward")
                            }.padding(18).frame(maxWidth: .infinity, minHeight: 64, alignment: .leading)
                                .background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 20)).contentShape(Rectangle())
                        }.buttonStyle(.plain).disabled(store.isRunning).accessibilityIdentifier("archived_\(card.id)")
                    }
                }.padding(20)
            }.background(RadarPalette.canvas).navigationTitle("已放下").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
        }.sheet(item: $restoring) { CardEditor(card: $0).environmentObject(store) }
    }
}
