import Foundation

/// Summarises accepted document changes, never the model's promise of changes.
struct CanvasChangeSummary: Identifiable {
    let id: String
    let boardID: String
    let targetIDs: [String]
    let text: String
    init(boardID: String, session: CanvasEditSession, partial: Bool) {
        self.id = session.id; self.boardID = boardID
        let changes = session.changes
        let nodes = changes.filter { $0.object == "node" }
        let added = Set(nodes.filter { $0.field == "*" && $0.before == nil && $0.after != nil }.map(\.id))
        let removed = Set(nodes.filter { ($0.field == "*" && $0.after == nil) || ($0.field == "status" && $0.after.flatMap { try? JSONDecoder().decode(String.self, from: $0) } == "archived") }.map(\.id))
        let edited = Set(nodes.map(\.id)).subtracting(added).subtracting(removed)
        let groups = Set(changes.filter { $0.object == "group" }.map(\.id))
        let edges = Set(changes.filter { $0.object == "edge" }.map(\.id))
        let edgeTargets = Set(changes.filter { $0.object == "edge" && $0.field == "*" }.flatMap { delta -> [String] in
            guard let data = delta.after ?? delta.before, let edge = try? JSONDecoder().decode(RadarEdge.self, from: data) else { return [] }
            return [edge.fromID, edge.toID]
        })
        targetIDs = Array(added.union(edited).union(groups).union(edgeTargets)).sorted()
        var parts: [String] = []
        if !added.isEmpty { parts.append("新增 \(added.count) 张") }
        if !edited.isEmpty { parts.append("修改 \(edited.count) 张") }
        if !removed.isEmpty { parts.append("放下 \(removed.count) 张") }
        if !groups.isEmpty { parts.append("调整 \(groups.count) 个分组") }
        if !edges.isEmpty { parts.append("调整 \(edges.count) 条连线") }
        text = parts.isEmpty ? "本轮未改动画布" : (partial ? "已保留部分变化 · " : "") + parts.joined(separator: " · ")
    }
}
