// Explicit real-provider check; key arrives via stdin and is never logged or persisted.
#if DIRECT_AGENT_STREAM_LIVE_CHECK
import Foundation
import AppKit

@main struct AgentStreamLiveCheck {
    enum Failed: Error { case check }
    @MainActor static func main() async {
        do {
            let renderOnly = CommandLine.arguments.contains("--render-fixture-only")
            guard renderOnly || CommandLine.arguments.contains("--run-deepseek") else { throw Failed.check }
            var key = ""
            if !renderOnly {
                guard let input = try JSONSerialization.jsonObject(with: FileHandle.standardInput.readDataToEndOfFile()) as? [String: String],
                      let value = input["key"], !value.isEmpty else { throw Failed.check }
                key = value
            }
            let image = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1100, pixelsHigh: 500, bitsPerSample: 8,
                                         samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
            NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: image)
            NSColor.white.setFill(); NSRect(x: 0, y: 0, width: 1100, height: 500).fill()
            let nodes: [(String, NSRect)] = [("START", NSRect(x: 20, y: 210, width: 180, height: 70)),
                ("PACK", NSRect(x: 320, y: 360, width: 170, height: 70)), ("CHECK", NSRect(x: 320, y: 60, width: 170, height: 70)),
                ("READY", NSRect(x: 620, y: 210, width: 180, height: 70)), ("GO", NSRect(x: 910, y: 210, width: 130, height: 70))]
            NSColor.black.setStroke()
            for (from, to) in [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)] {
                let a = NSPoint(x: nodes[from].1.maxX, y: nodes[from].1.midY)
                let b = NSPoint(x: nodes[to].1.minX, y: nodes[to].1.midY)
                let path = NSBezierPath(); path.lineWidth = 4; path.move(to: a); path.line(to: b)
                path.move(to: NSPoint(x: b.x - 14, y: b.y + 10)); path.line(to: b); path.line(to: NSPoint(x: b.x - 14, y: b.y - 10)); path.stroke()
            }
            for (title, rect) in nodes {
                let path = NSBezierPath(rect: rect); path.lineWidth = 3; path.stroke()
                (title as NSString).draw(at: NSPoint(x: rect.minX + 10, y: rect.minY + 15), withAttributes: [.font: NSFont.systemFont(ofSize: 35, weight: .medium), .foregroundColor: NSColor.black])
            }
            NSGraphicsContext.restoreGraphicsState()
            let png = image.representation(using: .png, properties: [:])!
            let folder = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("outputs/ios/stream-vision-live")
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            try png.write(to: folder.appendingPathComponent("input.png"), options: .atomic)
            if renderOnly { print("FIXTURE PASS: 5 labeled boxes, 5 directed arrows; no network or key read."); return }
            let connection = AgentConnection(provider: "DeepSeek", baseURL: "https://api.deepseek.com/v1", model: "deepseek-flash")
            var board = RadarBoard(title: "图片逻辑整理", question: "只整理图片原有内容", template: "", cards: [], edges: [],
                                   sources: [RadarSource(id: "drawing", title: "本地测试逻辑图", url: nil, excerpt: "用户提供的测试图像，正文见图片。")])
            let start = Date(); var firstSeconds: Double?; var batches = 0
            print("LIVE START provider=DeepSeek model=deepseek-flash streaming=true vision=true hasKey=true"); fflush(stdout)
            try await DirectAgent().generateStream(board: board,
                prompt: "忠实将图片里的全部文字框与箭头整理成可编辑节点和连线，节点标题保留图中原文。只转写，不添加图中不存在的建议。小批增量更新，先返回可成立的部分，再继续补完图。",
                selectedID: nil, configuration: connection, apiKey: key,
                images: [DirectAgentImage(data: png, mimeType: "image/png", sourceID: "drawing")]) { update in
                    batches += 1
                    if firstSeconds == nil { firstSeconds = Date().timeIntervalSince(start) }
                    board = DirectAgent.accumulating(update, into: board)
                    // This fixture contains no user material. Keep exact graph evidence for a
                    // future explicit live run; redact defensively before logging any content.
                    let evidence: [String: Any] = ["batch": batches, "elapsed": Date().timeIntervalSince(start),
                        "cards": board.cards.map { ["id": $0.id, "title": $0.title, "kind": $0.kind, "source_ids": $0.sourceIDs] },
                        "edges": board.edges.map(\.json)]
                    if let data = try? JSONSerialization.data(withJSONObject: evidence, options: [.sortedKeys]),
                       let text = String(data: data, encoding: .utf8) {
                        let sanitized = text.replacingOccurrences(of: key, with: "[redacted]")
                        print("LIVE GRAPH " + sanitized)
                        try? Data(sanitized.utf8).write(to: folder.appendingPathComponent("batch-\(batches).json"), options: .atomic)
                    }
                    print(String(format: "LIVE UPDATE batch=%d elapsed=%.2f cards=%d edges=%d", batches, Date().timeIntervalSince(start), board.cards.count, board.edges.count)); fflush(stdout)
                }
            let titles = Set(board.cards.map { $0.title.uppercased().trimmingCharacters(in: .whitespacesAndNewlines) })
            guard titles == Set(nodes.map(\.0)), batches >= 2, board.edges.count == 5 else { throw Failed.check }
            let byID = Dictionary(uniqueKeysWithValues: board.cards.map { ($0.id, $0.title.uppercased()) })
            let links = Set(board.edges.map { (byID[$0.fromID] ?? "?") + ">" + (byID[$0.toID] ?? "?") })
            guard links == Set(["START>PACK", "START>CHECK", "PACK>READY", "CHECK>READY", "READY>GO"]) else { throw Failed.check }
            print(String(format: "LIVE PASS batches=%d first_valid_seconds=%.2f total_seconds=%.2f vision_labels=5 valid_branch_edges=5", batches, firstSeconds ?? -1, Date().timeIntervalSince(start))); fflush(stdout)
        } catch {
            // Never echo the response, request, key or arbitrary error descriptions.
            print("LIVE FAIL reason=" + ((error as? DirectAgentError)?.localizedDescription ?? "local assertion or cancellation")); fflush(stdout)
            exit(1)
        }
    }
}
#endif
