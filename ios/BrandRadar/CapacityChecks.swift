#if DEBUG
import UIKit
import Darwin

/// Opt-in measurement: real BoardStore IO in fresh directories, never the user's document file.
@MainActor enum CapacityChecks {
    struct Failure: Error { let message: String }
    private struct Sample {
        var nodes: Int
        var documents: Int
        var attachmentsPerDocument: Int
        var name: String { "\(nodes)n-\(documents)d-\(attachmentsPerDocument)a" }
    }

    static func run() throws -> [String: Any] {
        var samples = [Sample]()
        for nodes in [3, 30, 120] {
            for documents in [1, 12, 50] { samples.append(Sample(nodes: nodes, documents: documents, attachmentsPerDocument: 1)) }
        }
        samples += [Sample(nodes: 30, documents: 12, attachmentsPerDocument: 24), Sample(nodes: 120, documents: 50, attachmentsPerDocument: 24)]
        let started = Date()
        var results: [[String: Any]] = []
        for sample in samples { results.append(try autoreleasepool { try measure(sample) }) }
        return [
            "status": "passed", "samples": results, "sampleCount": results.count, "repetitionsPerSample": 1,
            "elapsedSeconds": Date().timeIntervalSince(started),
            "deviceModel": UIDevice.current.model, "systemVersion": UIDevice.current.systemVersion,
            "hardware": hardwareName(), "simulator": ProcessInfo.processInfo.environment["SIMULATOR_MODEL_IDENTIFIER"] != nil,
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown", "configuration": "DEBUG",
            "limits": ["每个样本仅一次，不报告稳定分位数。", "打开、选择、移动保存与重开使用真实 BoardStore；阅读为正文及附件文件遍历，不是 UI 渲染或真人阅读。", "移动为一次 Store.moveCard 加保存，不代表触摸延迟或 FPS。", "附件是每份 32 KiB 的合成文件，不衡量大图片解码、音视频播放。", "内存是同一测试进程若干时点的 phys_footprint，不是独立文档占用或峰值。"]
        ]
    }

    private static func measure(_ sample: Sample) throws -> [String: Any] {
        let manager = FileManager.default, id = UUID().uuidString
        let directory = manager.temporaryDirectory.appendingPathComponent("radar-capacity-" + id, isDirectory: true)
        let suiteName = "com.keyuanshi.brandradar.capacity." + id
        guard let preferences = UserDefaults(suiteName: suiteName) else { throw Failure(message: "capacity preferences unavailable") }
        try manager.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { preferences.removePersistentDomain(forName: suiteName); try? manager.removeItem(at: directory) }
        preferences.set("practice", forKey: "workspaceMode")
        let assets = CanvasAssets(directory: directory.appendingPathComponent("assets", isDirectory: true))
        let payload = Data(repeating: 0x63, count: 32 * 1024)
        var boards: [RadarBoard] = []
        for document in 0..<sample.documents {
            var cards: [RadarCard] = []
            for index in 0..<sample.nodes {
                let cardID = "node-\(document)-\(index)"
                var card = RadarCard(id: cardID, title: "容量样本 \(index + 1)", body: String(repeating: "保留当前正文、分组与修改记录。", count: 8), x: Double(index % 10) * 340, y: Double(index / 10) * 320)
                card.history = ["较早的原稿仍然保留。"]
                if index < sample.attachmentsPerDocument {
                    let path = "sample-\(document)-\(index).dat"
                    try payload.write(to: assets.directory.appendingPathComponent(path), options: .atomic)
                    card.blocks = [CanvasBlock(id: "text-" + cardID, kind: "text", text: card.body), CanvasBlock(id: "file-" + cardID, kind: "file", attachment: CanvasAttachment(id: "asset-" + cardID, name: "合成容量附件.dat", contentType: "public.data", path: path, byteCount: payload.count))]
                }
                cards.append(card)
            }
            let edges = (1..<sample.nodes).map { RadarEdge(id: "edge-\(document)-\($0)", fromID: cards[$0 - 1].id, toID: cards[$0].id, label: "后续") }
            var board = RadarBoard(id: "document-\(document)", title: "隔离容量样本 \(document + 1)", question: "合成测试材料", template: "空白", cards: cards, edges: edges)
            board.workspaceMode = .practice
            board.groups = stride(from: 0, to: sample.nodes, by: 10).map { start in RadarGroup(id: "group-\(document)-\(start)", title: "方向 \(start / 10 + 1)", cardIDs: Array(cards[start..<min(start + 10, cards.count)]).map(\.id)) }
            var old = board; old.cards[0].body = "之前的内容"
            board.editHistory = [CanvasEditSession(title: "已有的修改记录", changes: CanvasHistory.diff(old, board), complete: true)]
            boards.append(board)
        }
        var seed: BoardStore? = BoardStore(testDirectory: directory, preferences: preferences)
        seed!.boards = boards; seed!.mode = .practice; seed!.selectedID = boards[0].id
        var start = CFAbsoluteTimeGetCurrent(); seed!.persist()
        let initialSave = milliseconds(since: start)
        guard seed!.error == nil else { throw Failure(message: "capacity initial save failed: " + sample.name) }
        seed = nil; boards.removeAll()
        let beforeOpen = memoryBytes()
        start = CFAbsoluteTimeGetCurrent()
        var opened: BoardStore? = BoardStore(testDirectory: directory, preferences: preferences)
        let open = milliseconds(since: start), afterOpen = memoryBytes()
        guard opened!.error == nil, opened!.boards.count == sample.documents,
              opened!.boards.allSatisfy({ $0.cards.count == sample.nodes }) else { throw Failure(message: "capacity open mismatch: " + sample.name) }
        start = CFAbsoluteTimeGetCurrent(); opened!.select(opened!.boards[sample.documents - 1])
        let selectAndSave = milliseconds(since: start)
        start = CFAbsoluteTimeGetCurrent()
        var checksum = 0, attachmentBytes = 0
        for card in opened!.current.visibleCards {
            checksum += card.title.utf8.count
            for block in card.effectiveBlocks {
                checksum += block.summary.utf8.count
                if let attachment = block.attachment {
                    guard let url = assets.url(for: attachment) else { throw Failure(message: "capacity attachment missing") }
                    let bytes = try Data(contentsOf: url); attachmentBytes += bytes.count; checksum += Int(bytes.first ?? 0)
                }
            }
        }
        let read = milliseconds(since: start), afterRead = memoryBytes()
        let cardID = opened!.current.cards[0].id
        start = CFAbsoluteTimeGetCurrent(); opened!.moveCard(cardID, x: 47, y: 63)
        let moveAndSave = milliseconds(since: start)
        start = CFAbsoluteTimeGetCurrent(); opened!.persist()
        let save = milliseconds(since: start)
        guard opened!.error == nil else { throw Failure(message: "capacity save failed: " + sample.name) }
        let selectedID = opened!.selectedID, historyCount = opened!.current.editHistory?.count
        opened = nil
        start = CFAbsoluteTimeGetCurrent()
        let reopened = BoardStore(testDirectory: directory, preferences: preferences)
        let reopen = milliseconds(since: start), afterReopen = memoryBytes()
        guard reopened.error == nil, reopened.boards.count == sample.documents,
              reopened.selectedID == selectedID, reopened.current.cards[0].x == 47, reopened.current.cards[0].y == 63,
              reopened.current.editHistory?.count == historyCount, reopened.current.cards[0].history == ["较早的原稿仍然保留。"] else { throw Failure(message: "capacity reopen did not retain saved edits/history: " + sample.name) }
        let files = (manager.enumerator(at: directory, includingPropertiesForKeys: [.fileSizeKey, .isRegularFileKey])?.allObjects as? [URL]) ?? []
        let diskBytes = try files.reduce(0) { total, url in
            let values = try url.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey]); return total + (values.isRegularFile == true ? values.fileSize ?? 0 : 0)
        }
        return ["name": sample.name, "nodesPerDocument": sample.nodes, "documents": sample.documents,
                "attachmentsPerDocument": sample.attachmentsPerDocument, "attachmentSizeBytes": payload.count,
                "initialSaveMS": initialSave, "openMS": open, "selectAndSaveMS": selectAndSave,
                "readContentAndAttachmentsMS": read, "moveAndSaveMS": moveAndSave, "saveMS": save, "reopenMS": reopen,
                "diskBytes": diskBytes, "readAttachmentBytes": attachmentBytes, "readChecksum": checksum,
                "memoryBeforeOpenBytes": memoryValue(beforeOpen), "memoryAfterOpenBytes": memoryValue(afterOpen),
                "memoryAfterReadBytes": memoryValue(afterRead), "memoryAfterReopenBytes": memoryValue(afterReopen)]
    }

    private static func milliseconds(since start: CFAbsoluteTime) -> Double { (CFAbsoluteTimeGetCurrent() - start) * 1000 }
    private static func memoryValue(_ value: UInt64?) -> Any { if let value { return value }; return NSNull() }
    private static func memoryBytes() -> UInt64? {
        var value = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let capacity = Int(count)
        let result = withUnsafeMutablePointer(to: &value) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: capacity) { task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count) }
        }
        return result == KERN_SUCCESS ? value.phys_footprint : nil
    }
    private static func hardwareName() -> String {
        var value = utsname(); uname(&value)
        let capacity = MemoryLayout.size(ofValue: value.machine)
        return withUnsafePointer(to: &value.machine) { pointer in pointer.withMemoryRebound(to: CChar.self, capacity: capacity) { String(cString: $0) } }
    }
}
#endif
