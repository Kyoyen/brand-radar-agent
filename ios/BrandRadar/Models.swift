import SwiftUI
import Security

enum WorkspaceMode: String, Codable, CaseIterable, Identifiable {
    case demo, practice
    var id: String { rawValue }
    var title: String { self == .demo ? "演示" : "实操" }
}

enum AgentTransport: String, CaseIterable, Identifiable {
    case api, mac
    var id: String { rawValue }
    var title: String { self == .api ? "API 直连" : "Mac 中间层" }
}

struct RadarCard: Codable, Identifiable, Equatable {
    var id = UUID().uuidString
    var kind = "note"
    var title: String
    var body: String
    var color = "cream"
    var x: Double = 0
    var y: Double = 0
    var width: Double = 280
    var status = "draft"
    var sourceIDs: [String] = []
    var history: [String] = []
    var blocks: [CanvasBlock]? = nil
    var height: Double? = nil
    var effectiveBlocks: [CanvasBlock] { blocks ?? [CanvasBlock(id: "legacy_\(id)", kind: "text", text: body)] }
    func hasSameContent(as other: RadarCard) -> Bool {
        kind == other.kind && title == other.title && body == other.body && color == other.color
            && width == other.width && height == other.height && blocks == other.blocks && status == other.status && sourceIDs == other.sourceIDs && history == other.history
    }
    var label: String {
        ["note": "便签", "idea": "想法", "observation": "观察", "source": "来源", "question": "问题", "calendar": "计划"][kind] ?? "便签"
    }
    var symbol: String {
        ["note": "text.alignleft", "idea": "sparkles", "observation": "eye", "source": "link", "question": "questionmark", "calendar": "checklist"][kind] ?? "text.alignleft"
    }
    var uiColor: UIColor {
        switch color {
        case "sage": return UIColor(red: 0.81, green: 0.9, blue: 0.78, alpha: 1)
        case "rose": return UIColor(red: 0.98, green: 0.81, blue: 0.8, alpha: 1)
        case "lavender": return UIColor(red: 0.86, green: 0.84, blue: 0.96, alpha: 1)
        case "sand": return UIColor(red: 0.98, green: 0.88, blue: 0.63, alpha: 1)
        default: return UIColor(red: 0.99, green: 0.98, blue: 0.93, alpha: 1)
        }
    }
    var json: [String: Any] {
        ["id": id, "kind": kind, "title": title, "body": body, "color": color,
         "x": x, "y": y, "width": width, "status": status, "source_ids": sourceIDs]
    }
}

struct RadarEdge: Codable, Identifiable, Equatable {
    var id = UUID().uuidString
    var fromID: String
    var toID: String
    var label: String
    var directed: Bool? = nil
    var json: [String: Any] { ["id": id, "from_id": fromID, "to_id": toID, "label": label, "directed": directed ?? true] }
}

struct RadarMessage: Codable, Identifiable {
    var id = UUID().uuidString
    var role: String
    var content: String
    // Nil means a message received from the Mac. Local messages remain until acknowledged.
    var delivery: String? = nil
}

struct RadarGroup: Codable, Identifiable, Equatable {
    var id = UUID().uuidString
    var title: String
    var cardIDs: [String]
    var color = "sage"
    var groupIDs: [String]? = nil
    var collapsed: Bool? = nil
    var width: Double? = nil
    var height: Double? = nil
    var json: [String: Any] { ["id": id, "title": title, "card_ids": cardIDs, "color": color, "group_ids": groupIDs ?? [], "collapsed": collapsed ?? false] }
}

struct RadarSource: Codable, Identifiable {
    var id: String
    var title: String
    var url: String?
    var excerpt: String
}

struct RadarBoard: Codable, Identifiable {
    var id = UUID().uuidString
    var remoteID: String?
    var title: String
    var question: String
    var template: String
    var cards: [RadarCard]
    var edges: [RadarEdge]
    var messages: [RadarMessage] = []
    var offsetX: Double = 28
    var offsetY: Double = 180
    var zoom: Double = 0.54
    var updated = Date()
    // Optional fields keep existing on-device saves readable.
    var dirtyCardIDs: Set<String>? = nil
    var dirtyEdgeIDs: Set<String>? = nil
    var removedEdgeIDs: Set<String>? = nil
    var sources: [RadarSource]? = nil
    var workspaceMode: WorkspaceMode? = nil
    var demoStage: Int? = nil
    var composerDraft: String? = nil
    var groups: [RadarGroup]? = nil
    var editHistory: [CanvasEditSession]? = nil
    var redoHistory: [CanvasEditSession]? = nil
    var pendingSpeech: String? = nil
    var activeEditSession: CanvasEditSession? = nil
    var mode: WorkspaceMode { workspaceMode ?? .practice }
    var visibleCards: [RadarCard] { cards.filter { $0.status != "archived" } }
    var markdown: String {
        var text = "# \(title)\n\n" + (mode == .demo ? "示例画布\n\n" : "") + "\(question)\n\n"
        for card in visibleCards {
            text += "## \(card.title)\n\n\(card.status == "kept" ? "已采用\n\n" : "")\(card.body)\n\n"
            for source in (sources ?? []).filter({ card.sourceIDs.contains($0.id) }) {
                text += "来源：\(source.title)\(source.url.map { " — " + $0 } ?? "")\n\n"
            }
        }
        let ids = Set(visibleCards.map(\.id))
        let links = edges.filter { ids.contains($0.fromID) && ids.contains($0.toID) }
        if !links.isEmpty {
            text += "## 关系\n\n"
            for edge in links {
                let from = cards.first { $0.id == edge.fromID }?.title ?? ""
                let to = cards.first { $0.id == edge.toID }?.title ?? ""
                text += "- \(from) → \(edge.label) → \(to)\n"
            }
        }
        return text
    }
}

enum BoardTemplate: String, CaseIterable, Identifiable {
    case campaign = "营销企划", mindmap = "灵感发散", journey = "用户旅程", content = "内容排期", experiment = "实验设计", blank = "空白画布"
    var id: String { rawValue }
    var symbol: String {
        switch self { case .campaign: return "sparkles"; case .mindmap: return "point.3.connected.trianglepath.dotted"; case .journey: return "figure.walk"; case .content: return "calendar"; case .experiment: return "flask"; case .blank: return "plus" }
    }
    var detail: String {
        switch self {
        case .campaign: return "从一句 Brief，到一个能做的创意"
        case .mindmap: return "围绕一个念头，让不同方向长出来"
        case .journey: return "看见、心动、行动，每一步都有理由"
        case .content: return "把表达变成一周的内容节奏"
        case .experiment: return "写下假设，设计一次小规模验证"
        case .blank: return "留一点空间，给还没成形的想法"
        }
    }
    func make() -> RadarBoard {
        var cards: [RadarCard] = []
        var edges: [RadarEdge] = []
        func add(_ title: String, _ body: String, _ kind: String, _ color: String, _ x: Double, _ y: Double) -> String {
            let card = RadarCard(kind: kind, title: title, body: body, color: color, x: x, y: y)
            cards.append(card); return card.id
        }
        func link(_ from: String, _ to: String, _ label: String) { edges.append(RadarEdge(fromID: from, toID: to, label: label)) }
        switch self {
        case .campaign:
            let a = add("让咖啡，加入周末", "为上海周末的咖啡场景，想一个轻量内容方向。不上新品，不靠打折。", "note", "sand", 0, 0)
            let b = add("一杯，走进下一站", "把自提咖啡当作出门的开始，记录从拿到咖啡到抵达下一站的片段。", "idea", "sage", 350, 0)
            let c = add("先把真实条件问清", "哪些门店适合这个场景？\n谁会在周末出门前自提？\n现有材料能支持哪些判断？", "question", "lavender", 0, 300)
            let d = add("做成一条手机内容", "选定场景 → 写三段镜头 → 补齐真实依据 → 人工审核 → 分享内容稿。", "calendar", "rose", 350, 300)
            link(a, b, "启发"); link(c, b, "需要验证"); link(b, d, "落成行动")
        case .mindmap:
            let a = add("一个值得继续的念头", "把脑海里的那句话写在这里。\n从这里向三个不同方向展开。", "note", "sand", 0, 260)
            for (i, name) in ["换个场景", "换个对象", "反过来想"].enumerated() {
                let b = add(name, "这个方向有什么独特的理由？\n先保留可能性，再寻找依据。", "idea", ["sage", "lavender", "rose"][i], 360, Double(i) * 280)
                link(a, b, "展开")
            }
        case .journey:
            var last: String?
            for (i, name) in ["看见", "产生兴趣", "采取行动", "愿意再来"].enumerated() {
                let id = add(name, "用户此刻在什么场景？\n阻力是什么？\n我们能给出什么具体帮助？", "question", ["sand", "sage", "lavender", "rose"][i], Double(i) * 350, 0)
                if let last { link(last, id, "下一步") }; last = id
            }
        case .content:
            for (i, name) in ["周一 · 一个观察", "周三 · 一个创意", "周五 · 一次邀请", "周末 · 看看反馈"].enumerated() {
                let id = add(name, "表达主题：待补充\n渠道与形式：待选择\n正文与行动：待补充\n发布前由人确认", "calendar", ["sand", "sage", "rose", "lavender"][i], Double(i % 2) * 350, Double(i / 2) * 300)
                if i > 0 { link(cards[i - 1].id, id, "接续") }
            }
        case .experiment:
            let a = add("我们的假设", "如果改变什么，谁的什么行为会变化？\n这是待验证的假设。", "idea", "sage", 0, 0)
            let b = add("最小的一次尝试", "对象、场景、动作。\n控制成本和范围，提前约定停止条件。", "calendar", "sand", 350, 0)
            let c = add("看什么结果", "记录真实反馈与行为。\n什么证据会让我们放下这个方向？", "question", "lavender", 350, 300)
            link(a, b, "通过实验验证"); link(b, c, "观察结果"); link(c, a, "修正假设")
        case .blank: break
        }
        return RadarBoard(title: self == .campaign ? "周末，带上一个好想法" : rawValue, question: detail,
                          template: rawValue, cards: cards, edges: edges)
    }
}

enum PairingKeychain {
    static let service = "com.keyuanshi.brandradar.pairing"
    static func read() -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                  kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess, let data = result as? Data else { return "" }
        return String(data: data, encoding: .utf8) ?? ""
    }
    static func save(_ token: String) throws {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service]
        let data = Data(token.utf8)
        var status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecItemNotFound {
            status = SecItemAdd(query.merging([kSecValueData as String: data, kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]) { _, new in new } as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw NSError(domain: "Keychain", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "无法安全保存配对，请重试。"] ) }
    }
}
