#if DEBUG
import UIKit

@MainActor enum CanvasGeometryChecks {
    private(set) static var benchmark: [String: Double] = [:]
    static func run() throws -> [String] {
        var passed: [String] = []
        func check(_ condition: Bool, _ label: String) throws {
            guard condition else { throw CanvasContentChecks.Failure(message: label) }; passed.append(label)
        }
        let bigTable = CanvasBlock(kind: "table", rows: Array(repeating: Array(repeating: "格", count: 10), count: 1000))
        if let segment = CanvasRichPreview.prepare(blocks: [bigTable]).segments.first, case let .table(rows, totalRows, _) = segment {
            try check(rows.count == 4 && rows[0].count == 3 && totalRows == 1000, "large table preview prepares only bounded visible cells")
        } else { try check(false, "table preview retains its structure") }
        let unevenTable = CanvasBlock(kind: "table", rows: [["A", "B"], ["1", "2"], ["3", "4"], ["5", "6"], ["later", "has", "five", "columns", "here"]])
        if let segment = CanvasRichPreview.prepare(blocks: [unevenTable]).segments.first, case let .table(_, _, columns) = segment {
            try check(columns == 5, "table preview reports columns beyond the first four rows")
        } else { try check(false, "uneven table preview exists") }
        let bigList = CanvasBlock(kind: "checklist", items: (0..<1000).map { CanvasChecklistItem(id: "list_\($0)", text: "准备", isChecked: false) })
        if let segment = CanvasRichPreview.prepare(blocks: [bigList]).segments.first, case let .checklist(items, total) = segment {
            try check(items.count == 4 && total == 1000, "large checklist preview prepares only bounded visible rows")
        } else { try check(false, "checklist preview retains its structure") }
        var board = BoardTemplate.blank.make()
        board.cards = (0..<120).map { i in
            let text = String(repeating: "边说边成图，保留结构与素材。", count: i % 4 + 1)
            var card = RadarCard(id: "perf_\(i)", title: "节点 \(i)", body: text)
            card.x = Double(i % 12) * 350; card.y = Double(i / 12) * 360
            card.width = i % 9 == 0 ? 440 : 280
            return card
        }
        board.groups = (0..<12).map { i in RadarGroup(id: "group_\(i)", title: "方向 \(i)", cardIDs: (0..<10).map { "perf_\(i * 10 + $0)" }) }
        board.edges = (1..<120).map { RadarEdge(id: "e\($0)", fromID: "perf_\($0-1)", toID: "perf_\($0)", label: "继续") }
        var nested = RadarGroup(id: "parent", title: "整体", cardIDs: []); nested.groupIDs = ["group_0", "group_1"]
        board.groups?.append(nested)
        let cache = CanvasGeometryCache(); cache.update(board)
        try check(board.visibleCards.allSatisfy { cache.rects[$0.id] == CanvasGeometry.cardRect($0) }, "cached node geometry matches rendering dimensions")
        try check((board.groups ?? []).allSatisfy { cache.rects[$0.id] == CanvasGeometry.groupRect($0, in: board) }, "cached nested frames equal recursive geometry")
        let measured = cache.measurements
        let initial = board.cards[0], delta = CGPoint(x: 55, y: 70)
        cache.move(origins: [initial.id: CGPoint(x: initial.x,y: initial.y)], delta: delta)
        board.cards[0].x += delta.x; board.cards[0].y += delta.y
        try check(cache.measurements == measured, "drag reuses measured text sizes")
        try check(cache.rects["parent"] == CanvasGeometry.groupRect(nested, in: board), "drag updates all ancestor frames")
        cache.update(board)
        try check(cache.measurements == measured, "viewport persistence does not remeasure text")
        let enlarged = CGSize(width: 620, height: 510)
        cache.resize(id: "perf_0", size: enlarged)
        var resized = board; resized.cards[0].width = enlarged.width; resized.cards[0].height = enlarged.height
        try check(cache.rects["perf_0"] == CanvasGeometry.cardRect(resized.cards[0]) && cache.rects["parent"] == CanvasGeometry.groupRect(nested,in:resized), "resizing keeps hit bounds and ancestor frames consistent")
        let expectedCurve = CanvasGeometry.curve(from: cache.rects["perf_0"]!, to: cache.rects["perf_1"]!)
        try check(cache.curves["e1"]?.1 == expectedCurve.1 && cache.curves["e1"]?.2 == expectedCurve.2, "resizing refreshes connector anchors")
        cache.update(board)
        board.groups?[0].collapsed = true; cache.update(board)
        try check(cache.visibleEndpoint("perf_1") == "group_0" && cache.curves["e1"] == nil, "collapsed subtree routes external edges and hides internal edges")
        board.groups?[0].collapsed = false
        CanvasLayout.arrange(&board); cache.update(board)
        try CanvasDocument(board).validate()
        let owned = Set((board.groups ?? []).flatMap { $0.cardIDs + ($0.groupIDs ?? []) })
        let rootIDs = board.visibleCards.map(\.id).filter { !owned.contains($0) } + (board.groups ?? []).map(\.id).filter { !owned.contains($0) }
        let roots = rootIDs.compactMap { cache.rects[$0] }
        var overlaps = false
        for i in roots.indices { for j in roots.indices where j > i { if roots[i].intersects(roots[j]) { overlaps = true } } }
        try check(!overlaps, "arrange respects variable sizes and nested root boundaries")
        let content = cache.contentBounds!
        try check(cache.rects.filter { !cache.hiddenIDs.contains($0.key) }.values.allSatisfy { content.contains($0) }, "fit includes every visible group and node")
        try check(cache.curveBounds.values.allSatisfy { content.contains($0) }, "fit includes connector arrows and label bounds")
        let frames = 8
        var sink: CGFloat = 0
        let legacyStart = CFAbsoluteTimeGetCurrent()
        for _ in 0..<frames {
            for group in (board.groups ?? []).sorted(by: { (CanvasGeometry.groupRect($0,in:board)?.width ?? 0) > (CanvasGeometry.groupRect($1,in:board)?.width ?? 0) }) { sink += CanvasGeometry.groupRect(group,in:board)?.width ?? 0 }
            for edge in board.edges {
                if let a = CanvasGeometry.rect(edge.fromID,in:board), let b = CanvasGeometry.rect(edge.toID,in:board) { sink += CanvasGeometry.curve(from:a,to:b).0.bounds.width }
            }
            for card in board.visibleCards { sink += CanvasGeometry.cardRect(card).height }
        }
        let legacy = CFAbsoluteTimeGetCurrent() - legacyStart
        let cachedStart = CFAbsoluteTimeGetCurrent()
        for _ in 0..<frames {
            for group in cache.orderedGroups { sink += cache.rects[group.id]?.width ?? 0 }
            for edge in cache.edges { sink += cache.curveBounds[edge.id]?.width ?? 0 }
            for card in cache.cards { sink += cache.rects[card.id]?.height ?? 0 }
        }
        let cached = CFAbsoluteTimeGetCurrent() - cachedStart
        benchmark = ["nodes":120,"frames":Double(frames),"legacyGeometryMilliseconds":legacy*1000,"cachedGeometryMilliseconds":cached*1000,"geometrySpeedup":legacy/max(cached,0.000001),"checksum":Double(sink)]
        var viewportBoard = board
        viewportBoard.offsetX = 25; viewportBoard.offsetY = 180; viewportBoard.zoom = 0.52
        // Center the first root in the phone viewport, keeping the remaining canvas offscreen.
        if let first = board.cards.first { viewportBoard.offsetX = 35 - first.x * viewportBoard.zoom; viewportBoard.offsetY = 220 - first.y * viewportBoard.zoom }
        let nearDraw = RadarCanvasView.measureDraw(board: viewportBoard)
        benchmark.merge(nearDraw.map { ("viewport_" + $0.key, $0.value) }, uniquingKeysWith: { _, b in b })
        try check((nearDraw["drawnNodes"] ?? 120) < 120 && (nearDraw["drawnEdges"] ?? 119) < 119, "actual renderer culls offscreen nodes and edges")
        viewportBoard.offsetX = 1_000_000; viewportBoard.offsetY = 1_000_000
        let emptyDraw = RadarCanvasView.measureDraw(board: viewportBoard)
        benchmark.merge(emptyDraw.map { ("offscreen_" + $0.key, $0.value) }, uniquingKeysWith: { _, b in b })
        try check(emptyDraw["drawnNodes"] == 0 && emptyDraw["drawnEdges"] == 0 && emptyDraw["drawnGroups"] == 0, "actual renderer skips all offscreen object types")
        for nodeCount in [30, 120] {
            var zoomBoard = viewportBoard
            zoomBoard.cards = Array(board.cards.prefix(nodeCount))
            zoomBoard.groups = Array((board.groups ?? []).prefix(nodeCount / 10))
            zoomBoard.edges = Array(board.edges.prefix(nodeCount - 1))
            let zoom = RadarCanvasView.measureZoom(board: zoomBoard)
            benchmark.merge(zoom.map { ("zoom_\(nodeCount)_" + $0.key, $0.value) }, uniquingKeysWith: { _, b in b })
        }
        return passed
    }
}
#endif
