#if DEBUG || ARCHIVE_CHECKS
import Foundation

// Standalone: xcrun swiftc -D ARCHIVE_CHECKS ios/BrandRadar/{CanvasContent,CanvasEditing,CanvasArchiving,ArchiveChecks}.swift -o /tmp/radar-archive-checks && /tmp/radar-archive-checks
// Foundation fixtures are used only by this command. ArchiveChecks.run() can also run with the real iOS models.
#if ARCHIVE_CHECKS
struct RadarCard: Codable, Identifiable, Equatable {
    var id = UUID().uuidString; var kind = "note"; var title: String; var body: String
    var color = "cream"; var x: Double = 0; var y: Double = 0; var width: Double = 280
    var status = "draft"; var sourceIDs: [String] = []; var history: [String] = []
    var blocks: [CanvasBlock]?; var height: Double?; var archiveRecord: RadarCardArchive?
    var effectiveBlocks: [CanvasBlock] { blocks ?? [CanvasBlock(id: "legacy_\(id)", kind: "text", text: body)] }
}
struct RadarEdge: Codable, Identifiable, Equatable {
    var id = UUID().uuidString; var fromID: String; var toID: String; var label: String; var directed: Bool?
}
struct RadarGroup: Codable, Identifiable, Equatable {
    var id = UUID().uuidString; var title: String; var cardIDs: [String]; var color = "sage"
    var groupIDs: [String]?; var collapsed: Bool?; var width: Double?; var height: Double?
}
struct RadarBoard: Codable {
    var title: String; var question: String; var template: String; var cards: [RadarCard]; var edges: [RadarEdge]
    var groups: [RadarGroup]?
    var visibleCards: [RadarCard] { cards.filter { $0.status != "archived" } }
}
@main enum ArchiveCheckMain {
    static func main() throws { print("Archive checks: \(try ArchiveChecks.run()) passed") }
}
#endif

enum ArchiveChecks {
    struct Failure: Error { let message: String }
    static func run() throws -> Int {
        var count = 0
        func check(_ value: @autoclosure () -> Bool, _ message: String) throws {
            guard value() else { throw Failure(message: message) }; count += 1
        }
        func fixture() -> RadarBoard {
            var b = RadarCard(id: "B", title: "中段", body: "保留我的原稿", x: 421, y: -170, status: "kept")
            b.blocks = [CanvasBlock(id: "photo", kind: "image", attachment: CanvasAttachment(id: "asset", name: "照片", contentType: "image/png", path: "assets/photo.png", byteCount: 32))]
            b.history = ["更早的原稿"]; b.sourceIDs = ["source"]
            return RadarBoard(title: "归档检查", question: "", template: "blank", cards: [RadarCard(id: "A", title: "开始", body: ""), b, RadarCard(id: "C", title: "结果", body: "")], edges: [RadarEdge(id: "AB", fromID: "A", toID: "B", label: "开启", directed: true), RadarEdge(id: "BC", fromID: "B", toID: "C", label: "导向", directed: false)], groups: [RadarGroup(id: "G", title: "原分组", cardIDs: ["A", "B", "C"])])
        }
        func assertValid(_ board: RadarBoard) throws {
            try CanvasDocument(board).validate()
            let active = Set(board.visibleCards.map(\.id)).union((board.groups ?? []).map(\.id))
            try check(board.edges.allSatisfy { active.contains($0.fromID) && active.contains($0.toID) }, "no archived or dangling edge endpoint")
        }
        let original = fixture()
        var board = original
        try check(CanvasArchiving.archive(&board, cardID: "B").changed, "archive changed")
        try check(board.cards[1].status == "archived" && board.edges.isEmpty, "archive hides incident edges")
        try check(board.groups?[0].cardIDs == ["A", "C"], "archive detaches membership")
        let archived = board
        try check(!CanvasArchiving.archive(&board, cardID: "B").changed && board.cards == archived.cards, "repeated archive preserves record")
        // Persist/reopen uses the exact production Codable metadata.
        board = try JSONDecoder().decode(RadarBoard.self, from: JSONEncoder().encode(board))
        let restored = CanvasArchiving.restore(&board, cardID: "B")
        try check(restored.restoredEdgeCount == 2 && restored.restoredGroupID == "G" && restored.warnings.isEmpty, "restore complete")
        try check(board.cards == original.cards, "ID geometry attachments sources content status history preserved")
        try check(board.edges == original.edges && board.groups == original.groups, "graph and group ordering preserved after reopen")
        try check(!CanvasArchiving.restore(&board, cardID: "B").changed, "repeated restore no-op")
        try assertValid(board)

        board = archived
        board.cards.removeAll { $0.id == "A" }; board.groups = []
        let deleted = CanvasArchiving.restore(&board, cardID: "B")
        try check(board.edges.map(\.id) == ["BC"] && board.groups?.isEmpty == true, "deleted endpoints and groups stay deleted")
        try check(deleted.warnings.count == 2 && deleted.message?.contains("已删除") == true, "concrete missing edge and group warnings")
        try assertValid(board)

        board = archived
        board.groups?.append(RadarGroup(id: "H", title: "人工归属", cardIDs: ["B"]))
        board.edges.append(RadarEdge(id: "AB", fromID: "A", toID: "C", label: "人工改线"))
        let conflict = CanvasArchiving.restore(&board, cardID: "B")
        try check(board.groups?.first { $0.id == "H" }?.cardIDs == ["B"] && board.groups?[0].cardIDs == ["A", "C"], "human regrouping wins")
        try check(board.edges.first { $0.id == "AB" }?.toID == "C" && conflict.warnings.count == 2, "occupied edge ID wins and both conflicts reported")
        try assertValid(board)

        for archiveOrder in [["A", "B"], ["B", "A"], ["A", "B", "C"]] {
            for restoreOrder in [archiveOrder, Array(archiveOrder.reversed())] {
                board = fixture()
                for id in archiveOrder { CanvasArchiving.archive(&board, cardID: id) }
                for id in restoreOrder { CanvasArchiving.restore(&board, cardID: id); try assertValid(board) }
                try check(Set(board.edges.map(\.id)) == ["AB", "BC"], "adjacent archive/restore order restores all edges")
                try check(board.cards.allSatisfy { $0.archiveRecord == nil }, "resolved records consumed across both endpoints")
                try check(Set(board.groups?[0].cardIDs ?? []) == ["A", "B", "C"], "adjacent group membership restored once")
            }
        }

        board = fixture()
        for id in ["A", "B", "C"] { CanvasArchiving.archive(&board, cardID: id) }
        let pending = CanvasArchiving.restore(&board, cardID: "A")
        try check(pending.restoredEdgeCount == 0 && pending.message?.contains("仍已放下") == true, "deferred edge explained")
        CanvasArchiving.restore(&board, cardID: "B")
        board.edges.removeAll { $0.id == "AB" } // Explicit deletion after restoration must win.
        CanvasArchiving.restore(&board, cardID: "C")
        CanvasArchiving.archive(&board, cardID: "A"); CanvasArchiving.restore(&board, cardID: "A")
        try check(board.edges.map(\.id) == ["BC"], "consumed shared snapshots cannot resurrect human-deleted edge")

        board = fixture()
        CanvasArchiving.archive(&board, cardID: "A"); CanvasArchiving.archive(&board, cardID: "B")
        CanvasArchiving.restore(&board, cardID: "A")
        CanvasArchiving.archive(&board, cardID: "A") // Active A still has a deferred edge.
        CanvasArchiving.restore(&board, cardID: "B"); CanvasArchiving.restore(&board, cardID: "A")
        try check(Set(board.edges.map(\.id)) == ["AB", "BC"], "rearchive retains deferred relations")

        board = fixture()
        CanvasArchiving.archive(&board, cardID: "B")
        let replacement = RadarEdge(id: "AB", fromID: "A", toID: "C", label: "人工重新使用这个关系")
        board.edges.append(replacement)
        CanvasArchiving.archive(&board, cardID: "A")
        CanvasArchiving.restore(&board, cardID: "B"); CanvasArchiving.restore(&board, cardID: "A")
        try check(board.edges.contains(replacement) && board.edges.filter { $0.id == "AB" }.count == 1, "live relation supersedes deferred ID before another archive")
        try assertValid(board)

        board = archived
        board.cards.append(RadarCard(id: "AB", title: "后来新增的卡片", body: ""))
        let collision = CanvasArchiving.restore(&board, cardID: "B")
        try check(!board.edges.contains { $0.id == "AB" } && collision.message?.contains("标识") == true, "card/edge ID collision rejected")
        try assertValid(board)

        board = fixture()
        CanvasArchiving.archive(&board, cardID: "A"); CanvasArchiving.archive(&board, cardID: "B")
        if let i = board.cards[1].archiveRecord?.edges.firstIndex(where: { $0.id == "AB" }) {
            board.cards[1].archiveRecord?.edges[i].label = "不一致的旧关系"
        }
        let ambiguity = CanvasArchiving.restore(&board, cardID: "B")
        CanvasArchiving.restore(&board, cardID: "A")
        try check(!board.edges.contains { $0.id == "AB" } && ambiguity.message?.contains("记录不一致") == true, "conflicting deferred snapshots are not guessed")
        try assertValid(board)

        board = archived
        board.cards[1].archiveRecord = nil // Existing older archive never had relation snapshots.
        let legacyData = try JSONEncoder().encode(board)
        board = try JSONDecoder().decode(RadarBoard.self, from: legacyData)
        let legacy = CanvasArchiving.restore(&board, cardID: "B")
        try check(board.cards[1].status == "draft" && board.edges.isEmpty && board.groups?[0].cardIDs == ["A", "C"], "legacy restore invents no relation")
        try check(legacy.message?.contains("没有放下前") == true, "legacy metadata absence explained")

        board = fixture()
        let beforeArchive = board
        CanvasArchiving.archive(&board, cardID: "B")
        let archiveChanges = CanvasHistory.diff(beforeArchive, board)
        try check(archiveChanges.contains { $0.field == "archiveRecord" }, "archive record participates in ordinary field history")
        let beforeRestore = board
        CanvasArchiving.restore(&board, cardID: "B")
        let restoreChanges = CanvasHistory.diff(beforeRestore, board)
        for _ in 0..<3 {
            CanvasHistory.apply(restoreChanges, to: &board, backwards: true); try assertValid(board)
            CanvasHistory.apply(archiveChanges, to: &board, backwards: true); try assertValid(board)
            try check(board.cards == original.cards && board.edges.count == original.edges.count && original.edges.allSatisfy { board.edges.contains($0) }, "undo archive restores original card and graph")
            CanvasHistory.apply(archiveChanges, to: &board, backwards: false); try assertValid(board)
            CanvasHistory.apply(restoreChanges, to: &board, backwards: false); try assertValid(board)
            try check(board.cards == original.cards && board.groups == original.groups, "redo preserves attachments and membership without duplicates")
        }
        board.cards[2].title = "稍后的人工作品"
        CanvasHistory.apply(restoreChanges, to: &board, backwards: true)
        try check(board.cards[2].title == "稍后的人工作品", "undo leaves unrelated human edits intact")
        return count
    }
}

#if DEBUG && !ARCHIVE_CHECKS
extension ArchiveChecks {
    /// Uses the real exporter, importer and asset files, without inserting anything in the user's boards.
    @MainActor static func runPackageChecks() throws -> Int {
        var count = 0
        func check(_ value: @autoclosure () -> Bool, _ message: String) throws {
            guard value() else { throw Failure(message: message) }; count += 1
        }
        let files = FileManager.default
        let working = files.temporaryDirectory.appendingPathComponent("archive-package-check-" + UUID().uuidString, isDirectory: true)
        try files.createDirectory(at: working, withIntermediateDirectories: true)
        var createdAssets: [URL] = [], packageDirectories: [URL] = []
        defer {
            for url in createdAssets { try? files.removeItem(at: url) }
            for url in packageDirectories { try? files.removeItem(at: url) }
            try? files.removeItem(at: working)
        }
        let bytes = Data("归档导出测试：附件原件必须原样保留。".utf8)
        let source = working.appendingPathComponent("测试原件.txt")
        try bytes.write(to: source)
        let asset = try CanvasAssets.shared.importFile(source)
        guard let originalURL = CanvasAssets.shared.url(for: asset) else { throw Failure(message: "archive package fixture asset exists") }
        createdAssets.append(originalURL)
        var b = RadarCard(id: "B", title: "中段", body: "保留我的原稿", x: 421, y: -170, status: "kept")
        b.blocks = [CanvasBlock(id: "original-file", kind: "file", attachment: asset)]
        b.history = ["更早的原稿"]; b.sourceIDs = ["source"]
        var board = RadarBoard(title: "归档包检查", question: "", template: "blank", cards: [RadarCard(id: "A", title: "开始", body: ""), b, RadarCard(id: "C", title: "结果", body: "")], edges: [RadarEdge(id: "AB", fromID: "A", toID: "B", label: "开启"), RadarEdge(id: "BC", fromID: "B", toID: "C", label: "导向")], groups: [RadarGroup(id: "G", title: "原分组", cardIDs: ["A", "B", "C"])])
        CanvasArchiving.archive(&board, cardID: "B")
        let savedRecord = board.cards[1].archiveRecord
        let packageURL = try CanvasExport.package(board: board)
        packageDirectories.append(packageURL.deletingLastPathComponent())
        let package = try JSONDecoder().decode(CanvasExport.Package.self, from: Data(contentsOf: packageURL))
        try check(package.board.cards[1].archiveRecord == savedRecord && package.board.cards[1].status == "archived", "package includes archived graph record")
        try check(package.assets[asset.path] == bytes, "package includes archived attachment bytes")
        var imported = try CanvasExport.importPackage(packageURL)
        guard let importedAsset = imported.cards[1].blocks?.first?.attachment,
              let importedURL = CanvasAssets.shared.url(for: importedAsset) else { throw Failure(message: "imported archived attachment accessible") }
        createdAssets.append(importedURL)
        try check(imported.id != board.id && imported.cards.map(\.id) == board.cards.map(\.id), "import creates new document and keeps node identities")
        try check(imported.cards[1].archiveRecord == savedRecord && imported.edges.isEmpty, "import retains pending relations without exposing archived edges")
        let importedBytes = try Data(contentsOf: importedURL)
        try check(importedURL != originalURL && importedBytes == bytes, "imported attachment uses fresh path with unchanged bytes")
        let restored = CanvasArchiving.restore(&imported, cardID: "B")
        try check(restored.restoredEdgeCount == 2 && restored.restoredGroupID == "G" && restored.warnings.isEmpty, "package roundtrip restores graph and original membership")
        try check(imported.cards[1].status == "kept" && imported.cards[1].x == b.x && imported.cards[1].y == b.y && imported.cards[1].body == b.body && imported.cards[1].history == b.history && imported.cards[1].sourceIDs == b.sourceIDs, "package restore retains card decisions content and location")
        try check(imported.cards[1].blocks?.first?.id == "original-file" && imported.cards[1].blocks?.first?.attachment == importedAsset, "restore preserves remapped attachment reference")
        try CanvasDocument(imported).validate()
        return count
    }
}
#endif
#endif
