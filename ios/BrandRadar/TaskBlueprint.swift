import Foundation

/// A small, local task specification derived only from the current user instruction.
/// It adds no agent, tool, document store or network request.
struct TaskBlueprint {
    var sectionNames: [String] = []
    var newCardCount: Int?
    var canvasWordMeansNodes = false

    static func from(prompt: String) -> TaskBlueprint {
        // The caller may append extracted material. It is context, never a command.
        let command = prompt.components(separatedBy: "\n选中素材内容").first ?? prompt
        var result = TaskBlueprint()
        let numeral = "([0-9０-９零〇一二两三四五六七八九十百千]+)"
        let quantity = "(?:生成|创建|新增|新建|添加|增加|加上|加|补充|做出|制作|做|给我|给出|想要|来)\\s*" + numeral + "\\s*(?:张|个)\\s*(?:内容)?(卡片|卡|画布)"
        for match in matches(quantity, in: command) where !negated(match.range, in: command) {
            guard let count = number(capture(1, match, command)) else { continue }
            result.newCardCount = count
            result.canvasWordMeansNodes = capture(2, match, command) == "画布"
        }
        let focusedRevision = !matches("只(?:修改|改|调整|重写|润色).*?第[一二三四五六七八九十0-9]+幕", in: command).isEmpty
        if focusedRevision { return result }
        let explicitStructure = numeral + "\\s*(幕|段式)"
        if let match = matches(explicitStructure, in: command).last(where: { !negated($0.range, in: command) }),
           let count = number(capture(1, match, command)), (2...8).contains(count) {
            let unit = capture(2, match, command) == "幕" ? "幕" : "段"
            result.sectionNames = (1...count).map { "第" + chinese($0) + unit }
        } else if (command.contains("电影") && (command.contains("剧本") || command.contains("脚本") || command.contains("几段式"))),
                  matches("(?:写|生成|创作|编写|制作|做).*?(?:电影|剧本|脚本)", in: command).contains(where: { !negated($0.range, in: command) }) {
            if !command.contains("不要三幕") && !command.contains("不用三幕") {
                result.sectionNames = ["第一幕", "第二幕", "第三幕"]
            }
        }
        return result
    }

    var instructions: String {
        var lines: [String] = []
        if !sectionNames.isEmpty {
            lines += ["本次使用轻量剧本/分段规范：按「" + sectionNames.joined(separator: "、") + "」顺序组织，每段必须有这个明确标题前缀，不能写成无结构的长便签。",
                "短内容可每幕/段一张卡；多场景用同名分组包含场景卡。明确总卡数不足以逐段一张时，在卡内用heading文本块保留每个幕/段标题。顺序连线表达剧情推进，并行支线仅在内容实际需要时出现。",
                "正文块kind=text，emphasis省略或填plain，不能把text写进emphasis。用户要求写/生成剧本时，就写具体场景、角色行动和必要对白；三幕对应建立处境与目标、冲突推进、选择与结果。用户只要求整理已有电影材料时，忠实归位，不擅自补剧情。不附营销建议、模板说明卡或来源总结卡。"]
        }
        if let count = newCardCount {
            lines.append("本次明确数量：在当前同一画布内新增恰好\(count)个内容节点。只按新card.id计数，已有卡的改稿、分组和连线不计数。分批生成，复用已创建id，不为了补数复制同一内容。")
            if canvasWordMeansNodes {
                lines.append("用户口语中的\(count)张画布在此解释为当前文档里的\(count)张内容卡；summary明确说在当前画布内生成内容卡。此工具不能新建多个独立文档，禁止宣称已创建多个独立画布。")
            }
        }
        return lines.isEmpty ? "" : "本次任务规范（只落实当前指令，不改变其他任务）：\n" + lines.joined(separator: "\n")
    }

    func checkCapacity(maximum: Int) throws {
        if let count = newCardCount, count < 1 || count > maximum {
            throw DirectAgentError.configuration("这次请求新增\(count)张卡；单次最多支持\(maximum)张，请分次生成。")
        }
    }

    /// Check before delivery so an oversized batch never partially enters the canvas.
    func validateProgress(initial: RadarBoard, candidate: RadarBoard) throws {
        if let count = newCardCount, addedCards(initial: initial, candidate: candidate).count > count {
            throw DirectAgentError.invalidResult("模型生成的卡片超过要求的\(count)张，本批未保存；先前完成的内容仍保留。")
        }
    }
    func isComplete(initial: RadarBoard, candidate: RadarBoard) -> Bool {
        if let count = newCardCount, addedCards(initial: initial, candidate: candidate).count != count { return false }
        let touched = candidate.cards.filter { card in
            guard card.status != "archived" else { return false }
            guard let old = initial.cards.first(where: { $0.id == card.id }) else { return true }
            return old.title != card.title || old.body != card.body || old.blocks != card.blocks || old.kind != card.kind
        }
        let groups = (candidate.groups ?? []).filter { group in
            !(initial.groups ?? []).contains(group)
        }
        let headings = touched.map(\.title) + groups.map(\.title) + touched.flatMap { $0.effectiveBlocks.filter { $0.emphasis == "heading" }.map(\.text) }
        return sectionNames.allSatisfy { section in headings.contains { $0.trimmingCharacters(in: .whitespacesAndNewlines).hasPrefix(section) } }
    }
    func continuation(initial: RadarBoard, candidate: RadarBoard) -> String {
        var parts: [String] = []
        if let count = newCardCount { parts.append("已新增\(addedCards(initial: initial, candidate: candidate).count)/\(count)张卡，只补足剩余数量，禁止超数。") }
        if !sectionNames.isEmpty { parts.append("落实\(sectionNames.joined(separator: "、"))的明确标题；修改已存在的相关卡/组，不额外造说明卡。") }
        return parts.joined()
    }
    func presented(_ result: DirectAgentResult, initial: RadarBoard, candidate: RadarBoard) -> DirectAgentResult {
        guard canvasWordMeansNodes else { return result }
        return DirectAgentResult(cards: result.cards, edges: result.edges, removeIDs: result.removeIDs,
            removeEdgeIDs: result.removeEdgeIDs,
            summary: "已在当前画布内新增\(addedCards(initial: initial, candidate: candidate).count)张内容卡。",
            groups: result.groups, removeGroupIDs: result.removeGroupIDs)
    }
    private func addedCards(initial: RadarBoard, candidate: RadarBoard) -> [RadarCard] {
        let ids = Set(initial.cards.map(\.id))
        return candidate.cards.filter { !ids.contains($0.id) && $0.status != "archived" }
    }
    private static func matches(_ pattern: String, in text: String) -> [NSTextCheckingResult] {
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
        return regex.matches(in: text, range: NSRange(text.startIndex..., in: text))
    }
    private static func capture(_ index: Int, _ match: NSTextCheckingResult, _ text: String) -> String {
        guard let range = Range(match.range(at: index), in: text) else { return "" }
        return String(text[range])
    }
    private static func negated(_ range: NSRange, in text: String) -> Bool {
        guard let range = Range(range, in: text) else { return true }
        let prefix = String(text[..<range.lowerBound].suffix(8))
        return prefix.range(of: "(?:不要|不用|无需|别|不必|不是)(?:按|采用|使用|写成|做成)?\\s*$", options: .regularExpression) != nil
    }
    private static func chinese(_ n: Int) -> String { ["零", "一", "二", "三", "四", "五", "六", "七", "八"][n] }
    private static func number(_ value: String) -> Int? {
        let normalized = value.applyingTransform(.fullwidthToHalfwidth, reverse: false) ?? value
        if let number = Int(normalized) { return number }
        let digits: [Character: Int] = ["零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9]
        let units: [Character: Int] = ["十": 10, "百": 100, "千": 1000]
        var total = 0, digit = 0
        for character in value {
            if let value = digits[character] { digit = value }
            else if let unit = units[character] { total += max(1, digit) * unit; digit = 0 }
            else { return nil }
        }
        return value.isEmpty ? nil : total + digit
    }
}
