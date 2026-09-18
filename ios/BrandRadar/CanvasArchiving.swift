import Foundation

/// Kept on the card so persistence and the existing field-level undo share one source of truth.
struct RadarCardArchive: Codable, Equatable {
    var previousStatus: String
    var edges: [RadarEdge]
    var parent: RadarArchivedParent?
}

struct RadarArchivedParent: Codable, Equatable {
    var id: String
    var title: String
    var index: Int
}

struct CanvasArchiveResult {
    var changed = false
    var restoredEdgeCount = 0
    var restoredGroupID: String?
    var warnings: [String] = []
    var message: String? { warnings.isEmpty ? nil : warnings.joined(separator: "\n") }
}

enum CanvasArchiving {
    @discardableResult
    static func archive(_ board: inout RadarBoard, cardID: String) -> CanvasArchiveResult {
        guard let index = board.cards.firstIndex(where: { $0.id == cardID }),
              board.cards[index].status != "archived" else { return CanvasArchiveResult() }
        let card = board.cards[index]
        // A previously archived neighbour may already have removed the shared edge.
        let currentEdgeIDs = Set(board.edges.map(\.id))
        let pending = board.cards.flatMap { $0.archiveRecord?.edges ?? [] }.filter { !currentEdgeIDs.contains($0.id) }
        let edges = uniqueEdges((board.edges + pending).filter { $0.fromID == cardID || $0.toID == cardID })
        let parent = (board.groups ?? []).first { $0.cardIDs.contains(cardID) }.map {
            RadarArchivedParent(id: $0.id, title: $0.title, index: $0.cardIDs.firstIndex(of: cardID) ?? 0)
        }
        // A live, manually reused edge ID supersedes every older deferred version.
        for i in board.cards.indices { board.cards[i].archiveRecord?.edges.removeAll { currentEdgeIDs.contains($0.id) } }
        board.cards[index].archiveRecord = RadarCardArchive(previousStatus: card.status, edges: edges, parent: parent)
        board.cards[index].status = "archived"
        board.edges.removeAll { $0.fromID == cardID || $0.toID == cardID }
        for i in (board.groups ?? []).indices { board.groups?[i].cardIDs.removeAll { $0 == cardID } }
        return CanvasArchiveResult(changed: true)
    }

    @discardableResult
    static func restore(_ board: inout RadarBoard, cardID: String) -> CanvasArchiveResult {
        guard let index = board.cards.firstIndex(where: { $0.id == cardID }),
              board.cards[index].status == "archived" else { return CanvasArchiveResult() }
        var result = CanvasArchiveResult(changed: true)
        let record = board.cards[index].archiveRecord
        board.cards[index].status = record?.previousStatus == "kept" ? "kept" : "draft"
        if record == nil {
            result.warnings.append("这张旧卡片没有放下前的关系记录；已恢复内容，无法补回原连线和分组。")
        }

        // Read all pending incident records: either endpoint can be restored first.
        let candidates = uniqueEdges(board.cards.flatMap { $0.archiveRecord?.edges ?? [] }
            .filter { $0.fromID == cardID || $0.toID == cardID })
        let grouped = Dictionary(grouping: candidates, by: \.id)
        let nodes = Set(board.cards.map(\.id)), groups = Set((board.groups ?? []).map(\.id))
        let existing = nodes.union(groups)
        let active = Set(board.visibleCards.map(\.id)).union(groups)
        var consumed = Set<String>()
        for edgeID in grouped.keys.sorted() {
            guard let versions = grouped[edgeID], let edge = versions.first else { continue }
            let name = edge.label.isEmpty ? "原连线" : "连线「\(edge.label)」"
            if versions.count > 1 {
                result.warnings.append("\(name)的保存记录不一致，未恢复。")
            } else if let current = board.edges.first(where: { $0.id == edgeID }) {
                if current != edge { result.warnings.append("\(name)已被修改，保留当前连线。") }
            } else if edgeID.isEmpty || existing.contains(edgeID) || edge.fromID == edge.toID {
                result.warnings.append("\(name)的标识或端点冲突，未恢复。")
            } else if !existing.contains(edge.fromID) || !existing.contains(edge.toID) {
                result.warnings.append("\(name)的端点已删除，未恢复。")
            } else if !active.contains(edge.fromID) || !active.contains(edge.toID) {
                result.warnings.append("\(name)的另一端仍已放下，将在它恢复时接回。")
                continue
            } else {
                board.edges.append(edge)
                result.restoredEdgeCount += 1
            }
            consumed.insert(edgeID)
        }

        if let parent = record?.parent {
            let owners = (board.groups ?? []).filter { $0.cardIDs.contains(cardID) }
            if !owners.isEmpty {
                if owners.count != 1 || owners[0].id != parent.id {
                    result.warnings.append("卡片已有新的分组归属，未移回「\(parent.title)」。")
                }
            } else if let groupIndex = board.groups?.firstIndex(where: { $0.id == parent.id }) {
                let position = min(max(0, parent.index), board.groups?[groupIndex].cardIDs.count ?? 0)
                board.groups?[groupIndex].cardIDs.insert(cardID, at: position)
                result.restoredGroupID = parent.id
            } else {
                result.warnings.append("原分组「\(parent.title)」已删除，未恢复归属。")
            }
        }

        // Consume an attempted group once. A later restore must never move a human regrouping.
        board.cards[index].archiveRecord?.parent = nil
        for i in board.cards.indices {
            guard var remaining = board.cards[i].archiveRecord else { continue }
            remaining.edges.removeAll { consumed.contains($0.id) }
            board.cards[i].archiveRecord = board.cards[i].status != "archived" && remaining.edges.isEmpty && remaining.parent == nil ? nil : remaining
        }
        return result
    }

    private static func uniqueEdges(_ values: [RadarEdge]) -> [RadarEdge] {
        // Keep conflicting versions detectable; only collapse byte-for-byte equivalent edges.
        values.reduce(into: []) { result, edge in if !result.contains(edge) { result.append(edge) } }
    }
}
