import SwiftUI

enum RadarPalette {
    static let textPrimary = Color(red: 0.12, green: 0.18, blue: 0.14)
    static let textSecondary = Color(red: 0.29, green: 0.34, blue: 0.29)
    static let borderSubtle = textPrimary.opacity(0.15)
    static let minimumHitSize: CGFloat = 44
    static let canvas = Color(red: 0.965, green: 0.96, blue: 0.935)
    static let paper = Color(red: 0.995, green: 0.99, blue: 0.975)
    static let green = Color(red: 0.24, green: 0.39, blue: 0.25)
    static let sage = Color(red: 0.89, green: 0.93, blue: 0.84)
}

struct TemplateSheet: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    private func caption(_ template: BoardTemplate) -> String {
        switch template {
        case .campaign: return "展开一个想法"
        case .mindmap: return "让方向长出来"
        case .journey: return "串起每一步"
        case .content: return "安排下一周"
        case .experiment: return "试试一个假设"
        case .blank: return "从零开始"
        }
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                    ForEach(BoardTemplate.allCases) { template in
                        Button { store.create(template); dismiss() } label: {
                            VStack(alignment: .leading, spacing: 22) {
                                Image(systemName: template.symbol).font(.system(size: 29, weight: .light)).frame(height: 42)
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(template.rawValue).font(.system(size: 17, weight: .semibold))
                                    Text(caption(template)).font(.system(size: 12)).foregroundStyle(.secondary)
                                }
                            }.frame(maxWidth: .infinity, alignment: .leading).padding(21)
                                .background(Color(template.make().cards.first?.uiColor ?? .white), in: RoundedRectangle(cornerRadius: 24))
                                .overlay(RoundedRectangle(cornerRadius: 24).stroke(.black.opacity(0.04)))
                                .contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("template_\(template.id)")
                    }
                }.padding(20)
            }.background(RadarPalette.canvas)
                .navigationTitle("新画布").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
        }
    }
}

struct BoardLibrary: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @State private var search = ""
    private var matches: [RadarBoard] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        return store.visibleBoards.filter { board in
            query.isEmpty || board.title.localizedStandardContains(query) || board.question.localizedStandardContains(query)
                || board.cards.contains { $0.title.localizedStandardContains(query) || $0.body.localizedStandardContains(query) || $0.effectiveBlocks.contains { $0.summary.localizedStandardContains(query) } }
        }.sorted { $0.updated == $1.updated ? $0.id < $1.id : $0.updated > $1.updated }
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 12) {
                    if matches.isEmpty {
                        ContentUnavailableView(search.isEmpty ? "还没有画布" : "没有找到画布", systemImage: search.isEmpty ? "square.stack" : "magnifyingglass", description: Text(search.isEmpty ? "从一个想法开始。" : "试试标题或正文中的其他词。"))
                            .accessibilityIdentifier("boardSearchEmpty")
                    }
                    ForEach(matches) { board in
                        Button { store.select(board); dismiss() } label: {
                            HStack(spacing: 17) {
                                Image(systemName: "square.stack").font(.title2).foregroundStyle(RadarPalette.green).frame(width: 44, height: 52)
                                VStack(alignment: .leading, spacing: 7) {
                                    Text(board.title).font(.headline).foregroundStyle(.primary).lineLimit(2)
                                    Text(board.visibleCards.first?.effectiveBlocks.first?.summary ?? board.question)
                                        .font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
                                    HStack {
                                        Text("\(board.visibleCards.count) 张卡片")
                                        Text(board.updated, format: .dateTime.month().day().hour().minute())
                                    }.font(.caption).foregroundStyle(.secondary)
                                }.frame(maxWidth: .infinity, alignment: .leading)
                                Image(systemName: board.id == store.selectedID ? "checkmark.circle.fill" : "chevron.right")
                                    .foregroundStyle(RadarPalette.green)
                            }.padding(18).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 23)).contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("board_\(board.id)")
                    }
                }.padding(20)
            }.background(RadarPalette.canvas)
                .searchable(text: $search, prompt: "搜索标题或正文")
                .navigationTitle(store.mode == .demo ? "示例画布" : "我的画布").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() }.accessibilityIdentifier("closeLibraryButton") } }
        }
    }
}

struct CardEditor: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @State var card: RadarCard
    @State private var originalCard: RadarCard
    init(card: RadarCard) { _card = State(initialValue: card); _originalCard = State(initialValue: card) }
    @State private var sharing: ShareContent?
    @State private var confirmExit = false
    @State private var pendingFocusID: String?
    @State private var pendingSplit: String?
    @State private var confirmSplit = false
    private var isDirty: Bool { card != originalCard }
    private var canSave: Bool { !card.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    private func finishExit() {
        if let id = pendingFocusID { store.focusNode(id) }
        dismiss()
    }
    private func requestExit() { if isDirty { confirmExit = true } else { finishExit() } }
    private func save() { if store.editCard(card, baseline: originalCard) { finishExit() } }
    private func split(_ id: String) {
        if store.saveAndSplitBlock(card, baseline: originalCard, blockID: id) { dismiss() }
    }
    private let colors = [("cream", "奶油"), ("sage", "鼠尾草"), ("rose", "粉桃"), ("lavender", "丁香"), ("sand", "麦黄")]
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 16) {
                        TextField("标题", text: $card.title, axis: .vertical).font(.system(size: 26, weight: .semibold)).accessibilityIdentifier("cardTitleInput")
                        Rectangle().fill(.black.opacity(0.07)).frame(height: 1)
                        RichContentEditor(blocks: Binding(get: { card.effectiveBlocks }, set: { card.blocks = $0; card.body = $0.map(\.summary).joined(separator: "\n\n") })) { blockID in
                            if isDirty { pendingSplit = blockID; confirmSplit = true } else { split(blockID) }
                        }
                    }.padding(23).background(Color(card.uiColor), in: RoundedRectangle(cornerRadius: 25))
                    HStack(spacing: 11) {
                        ForEach(colors, id: \.0) { value, name in
                            Button { card.color = value } label: {
                                Circle().fill(Color(RadarCard(title: "", body: "", color: value).uiColor)).frame(width: 32, height: 32)
                                    .overlay(Circle().strokeBorder(card.color == value ? RadarPalette.green : .black.opacity(0.09), lineWidth: card.color == value ? 2 : 1))
                                    .overlay { if card.color == value { Image(systemName: "checkmark").font(.system(size: 11, weight: .semibold)).foregroundStyle(RadarPalette.green) } }
                            }.buttonStyle(.plain).accessibilityLabel(name).accessibilityIdentifier("cardColor_\(value)")
                        }
                        Spacer(minLength: 8)
                        Button { card.status = card.status == "kept" ? "draft" : "kept" } label: {
                            Label("采用", systemImage: card.status == "kept" ? "checkmark.circle.fill" : "checkmark.circle")
                                .font(.system(size: 13, weight: .medium)).foregroundStyle(card.status == "kept" ? RadarPalette.green : .secondary)
                        }.accessibilityIdentifier("keepCardButton")
                    }.padding(.horizontal, 4)
                    if let sources = store.current.sources?.filter({ card.sourceIDs.contains($0.id) }), !sources.isEmpty {
                        DisclosureGroup("来源 · \(sources.count)") {
                            VStack(alignment: .leading, spacing: 18) {
                                ForEach(sources) { source in
                                    VStack(alignment: .leading, spacing: 8) {
                                        if let value = source.url, let url = URL(string: value), ["https", "http"].contains(url.scheme ?? "") {
                                            Link(source.title, destination: url).font(.subheadline.weight(.medium))
                                        } else { Text(source.title).font(.subheadline.weight(.medium)) }
                                        if let original = store.current.cards.first(where: { $0.effectiveBlocks.contains(where: { $0.id == source.id }) }) {
                                            Button("查看原素材", systemImage: "arrow.up.left.and.arrow.down.right") { pendingFocusID = original.id; requestExit() }
                                                .font(.caption).accessibilityIdentifier("viewSource_\(source.id)")
                                        }
                                        Text(source.excerpt).font(.caption).foregroundStyle(.secondary)
                                    }
                                }
                            }.padding(.top, 12)
                        }.font(.subheadline).padding(19).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 20))
                    }
                    if !card.history.isEmpty {
                        DisclosureGroup("修改记录 · \(card.history.count)") {
                            VStack(alignment: .leading, spacing: 16) {
                                ForEach(Array(card.history.reversed().enumerated()), id: \.offset) { i, text in
                                    DisclosureGroup("稿子 \(card.history.count - i)") { Text(text).font(.subheadline).textSelection(.enabled).padding(.top, 8) }
                                }
                            }.padding(.top, 12)
                        }.font(.subheadline).padding(19).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 20))
                    }
                    HStack {
                        Button("分享", systemImage: "square.and.arrow.up") { sharing = ShareContent(items: [(store.mode == .demo ? "示例画布\n\n" : "") + card.title + "\n\n" + card.body]) }
                        Spacer()
                        Button(card.status == "archived" ? "恢复" : "放下", systemImage: "archivebox") {
                            let status = card.status
                            card.status = status == "archived" ? "draft" : "archived"
                            if store.editCard(card, baseline: originalCard) { store.selectedCardID = nil; if store.restorationNotice == nil { dismiss() } }
                            else { card.status = status }
                        }.foregroundStyle(.secondary)
                    }.font(.subheadline).padding(.horizontal, 5).padding(.bottom, 10)
                }.padding(20)
            }.background(RadarPalette.canvas).navigationTitle("卡片").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("取消") { requestExit() }.accessibilityIdentifier("cancelCardButton") }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("保存") { save() }.bold().disabled(!canSave).accessibilityIdentifier("saveCardButton")
                    }
                }
                .safeAreaInset(edge: .bottom) {
                    if store.isRunning { Text("正在改稿…").font(.caption).padding(10).frame(maxWidth: .infinity).background(.regularMaterial) }
                }
        }
        .interactiveDismissDisabled(isDirty)
        .background(EditorDismissGuard(isDirty: isDirty, onAttempt: requestExit))
        .confirmationDialog("要保存更改吗？", isPresented: $confirmExit, titleVisibility: .visible) {
            Button("保存") { save() }.disabled(!canSave).accessibilityIdentifier("saveEditorChangesButton")
            Button("放弃更改", role: .destructive) { finishExit() }.accessibilityIdentifier("discardEditorChangesButton")
            Button("继续编辑") { pendingFocusID = nil }.accessibilityIdentifier("continueEditingButton")
        }
        .confirmationDialog("保存并转为节点", isPresented: $confirmSplit, titleVisibility: .visible) {
            Button("保存并转为节点") { if let id = pendingSplit { split(id) }; pendingSplit = nil }
                .disabled(!canSave).accessibilityIdentifier("confirmSaveAndSplitButton")
            Button("继续编辑", role: .cancel) { pendingSplit = nil }
        } message: { Text("将保存当前更改，并把这项内容转为独立节点。") }
        .alert("未能保存", isPresented: Binding(get: { store.editorFeedback != nil }, set: { if !$0 { store.editorFeedback = nil } })) {
            Button("继续编辑", role: .cancel) { store.editorFeedback = nil }
        } message: { Text(store.editorFeedback ?? "") }
        .alert("已恢复可用内容", isPresented: Binding(get: { store.restorationNotice != nil }, set: { if !$0 { store.restorationNotice = nil } })) {
            Button("知道了") { store.restorationNotice = nil; dismiss() }
        } message: { Text(store.restorationNotice ?? "") }
        .onAppear { store.editorFeedback = nil; store.restorationNotice = nil }
        .sheet(item: $sharing) { ShareSheet(items: $0.items) }
    }
}

struct ChatSheet: View {
    var onViewChanges: (() -> Void)? = nil
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var speech = SpeechInput()
    @State private var input = ""
    @State private var speechPrefix = ""
    @State private var followsLatest = true
    @State private var userScrolling = false
    @State private var hasNewReply = false
    @State private var readAnchor: String?
    @State private var viewportHeight: CGFloat = 0
    @State private var measuredBottom: CGFloat = 0
    private struct BottomPosition: PreferenceKey {
        static var defaultValue: CGFloat = 0
        static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = nextValue() }
    }
    private struct MessagePositions: PreferenceKey {
        static var defaultValue: [String: CGFloat] = [:]
        static func reduce(value: inout [String: CGFloat], nextValue: () -> [String: CGFloat]) { value.merge(nextValue(), uniquingKeysWith: { _, new in new }) }
    }
    @SceneStorage("chatReadingPositions") private var savedReadingPositions = "{}"
    @State private var draftBoardID = ""
    @FocusState private var focused: Bool
    private let suggestions = [("想方向", "围绕当前 Brief，展开三个有差异的创意方向。"), ("写内容", "把当前想法写成一份可以分享的内容稿。"), ("理结构", "整理当前画布，连起重要的逻辑关系。")]
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                HStack(spacing: 9) {
                    Image(systemName: store.selectedCardID == nil ? "square.stack" : "scope")
                    Text(store.chatTargetLabel).lineLimit(2).accessibilityIdentifier("chatTargetLabel")
                    Spacer(minLength: 4)
                    if store.selectedCardID != nil {
                        Button { store.clearChatTarget() } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                            .accessibilityLabel("取消选择").disabled(store.isRunning)
                    }
                }.font(.subheadline).padding(.horizontal, 16).padding(.vertical, 4)
                    .background(RadarPalette.sage, in: RoundedRectangle(cornerRadius: 16)).padding(.horizontal, 16).padding(.top, 8)
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 20) {
                            if store.mode == .demo {
                                VStack(alignment: .leading, spacing: 16) {
                                    Text("示例画布").font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary)
                                    HStack(spacing: 9) {
                                        demoAction("展开画布", icon: "square.grid.2x2", id: "demoStartButton") { store.clearChatTarget(); submit(DemoCanvas.startPrompt) }
                                        demoAction("改写这张", icon: "pencil.line", id: "demoRefineButton") { submit(DemoCanvas.refinePrompt) }.disabled(store.selectedCardID == nil)
                                        demoAction("写内容稿", icon: "text.alignleft", id: "demoCopyButton") { submit(DemoCanvas.copyPrompt) }
                                    }
                                    Button {
                                        if store.copyCurrentDemoToMyBoard(draft: input) { focused = true }
                                    } label: {
                                        Label("在我的画布中继续", systemImage: "arrow.up.right.square")
                                            .font(.subheadline).frame(minHeight: 44)
                                    }.accessibilityIdentifier("copyDemoToMyBoardButton")
                                }.padding(.vertical, 12).disabled(store.busyBoardID != nil)
                            } else if store.current.messages.isEmpty {
                                VStack(alignment: .leading, spacing: 24) {
                                    Text("今天想做什么？").font(.system(size: 28, weight: .medium)).padding(.top, 25)
                                    HStack(spacing: 10) {
                                        ForEach(suggestions, id: \.0) { title, prompt in
                                            Button { input = prompt; focused = true } label: {
                                                Text(title).font(.system(size: 13)).padding(.horizontal, 15).padding(.vertical, 12)
                                                    .background(RadarPalette.paper, in: Capsule()).contentShape(Capsule())
                                            }.buttonStyle(.plain)
                                        }
                                    }
                                }.padding(.bottom, 25)
                            }
                            ForEach(store.current.messages) { message in
                                messageBubble(message)
                                    .id(message.id).accessibilityIdentifier("message_\(message.id)")
                                    .background(GeometryReader { geometry in
                                        Color.clear.preference(key: MessagePositions.self, value: [message.id: geometry.frame(in: .named("chatScroll")).minY])
                                    })
                            }
                            if store.isRunning { HStack { ProgressView(); Text(store.activity).font(.caption) }.padding(.vertical, 8) }
                            Color.clear.frame(height: 1).id("end").background(GeometryReader { geometry in
                                Color.clear.preference(key: BottomPosition.self, value: geometry.frame(in: .named("chatScroll")).maxY)
                            })
                        }.padding(20)
                    }
                    .accessibilityIdentifier("chatHistory")
                    #if DEBUG
                    .accessibilityValue("follow=\(followsLatest) drag=\(userScrolling) height=\(viewportHeight) bottom=\(measuredBottom) anchor=\(readAnchor ?? "nil")")
                    #endif
                    .onPreferenceChange(MessagePositions.self) { positions in
                        readAnchor = positions.filter { $0.value >= -20 }.min(by: { $0.value < $1.value })?.key
                    }
                    .coordinateSpace(name: "chatScroll")
                    .background(GeometryReader { geometry in
                        Color.clear.onAppear { viewportHeight = geometry.size.height }.onChange(of: geometry.size.height) { _, height in
                            viewportHeight = height
                            if followsLatest && !userScrolling { DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) } }
                        }
                    })
                    .simultaneousGesture(DragGesture().onChanged { _ in userScrolling = true })
                    .onPreferenceChange(BottomPosition.self) { bottom in
                        measuredBottom = bottom
                        if userScrolling {
                            followsLatest = bottom <= viewportHeight + 64 && bottom >= 0
                            if followsLatest { hasNewReply = false }
                        } else if followsLatest && bottom > viewportHeight + 8 && viewportHeight > 0 {
                            // Follow after the new bubble and result bar have actually laid out.
                            DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) }
                        }
                    }
                    .onAppear {
                        let positions = (try? JSONDecoder().decode([String: String].self, from: Data(savedReadingPositions.utf8))) ?? [:]
                        if let saved = positions[store.selectedID], store.current.messages.contains(where: { $0.id == saved }) {
                            followsLatest = false
                            DispatchQueue.main.async { proxy.scrollTo(saved, anchor: .top) }
                        } else { DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) } }
                    }
                    .onChange(of: store.current.messages.last?.content) { _, _ in
                        if followsLatest { userScrolling = false; DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) } }
                        else { hasNewReply = true }
                    }
                    .onChange(of: store.current.messages.count) { _, _ in
                        if followsLatest { userScrolling = false; DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) } }
                        else { hasNewReply = true }
                    }
                    .onChange(of: store.isRunning) { _, _ in
                        if followsLatest { userScrolling = false; DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) } }
                    }
                    .overlay(alignment: .bottom) {
                        if hasNewReply {
                            Button { userScrolling = false; followsLatest = true; hasNewReply = false; withAnimation { proxy.scrollTo("end", anchor: .bottom) } } label: {
                                Label("有新回复", systemImage: "arrow.down").font(.subheadline).padding(12).background(RadarPalette.paper, in: Capsule()).shadow(color: .black.opacity(0.1), radius: 6)
                            }.accessibilityIdentifier("newReplyButton").padding(.bottom, 6)
                        }
                    }
                }

                VStack(spacing: 10) {
                    if let result = store.latestChange, result.boardID == store.selectedID {
                        Button { onViewChanges?() } label: {
                            HStack { Text(result.text).font(.subheadline).multilineTextAlignment(.leading); Spacer(); Image(systemName: "arrow.up.right") }.frame(minHeight: 44)
                        }.accessibilityLabel("查看变化，" + result.text).accessibilityIdentifier("chatViewChangesButton")
                    }
                    if let error = store.error {
                        HStack(alignment: .top) {
                            Text(error).font(.caption).foregroundStyle(.orange).accessibilityIdentifier("chatError")
                            Spacer(minLength: 8)
                            Button { store.error = nil } label: { Image(systemName: "xmark.circle") }.accessibilityLabel("关闭提示")
                        }.padding(.horizontal, 9)
                    }
                    if speech.starting || speech.recording || speech.finishing {
                        HStack(spacing: 8) {
                            Image(systemName: "waveform")
                            Text(speech.finishing ? "正在完成听写…" : speech.starting ? "正在准备麦克风…" : "正在听写，可先检查文字")
                                .font(.caption)
                        }.foregroundStyle(.secondary).accessibilityIdentifier("chatDictationState")
                    }
                    if store.isRunning {
                        Button { Task { await store.stop() } } label: { Label("停止整理", systemImage: "stop.circle").frame(minHeight: 44) }
                            .accessibilityIdentifier("stopChatButton")
                    }
                    HStack(alignment: .bottom, spacing: 12) {
                        Button {
                            if speech.recording { speech.finish { text in if !text.isEmpty { input = speechPrefix + text }; focused = true } }
                            else {
                                focused = false
                                speechPrefix = input.isEmpty ? "" : input + "\n"
                                Task { await speech.start(requireOnDevice: store.mode == .demo) }
                            }
                        } label: { Image(systemName: speech.recording ? "stop.circle.fill" : "mic").font(.system(size: 21)).frame(width: 44, height: 44) }
                            .accessibilityLabel(speech.recording ? "结束听写，编辑草稿" : "开始听写草稿")
                            .disabled(speech.starting || speech.finishing || store.busyBoardID != nil)
                        TextField("说出你的想法", text: $input, axis: .vertical).lineLimit(1...6).focused($focused).padding(.vertical, 11).accessibilityIdentifier("composerInput")
                        Button {
                            submit(input)
                        } label: { Image(systemName: "arrow.up").bold().foregroundStyle(.white).frame(width: 44, height: 44).background(RadarPalette.green, in: Circle()) }
                            .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.busyBoardID != nil || speech.recording || speech.finishing || !store.chatTargetIsValid).accessibilityIdentifier("sendButton")
                    }.padding(10).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 27))
                        .overlay(RoundedRectangle(cornerRadius: 27).stroke(.black.opacity(0.05)))
                }.padding(.horizontal, 16).padding(.bottom, 12)
            }.background(RadarPalette.canvas).navigationTitle(store.mode == .demo ? "示例画布" : "对话").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) { Button("收起") { dismiss() }.accessibilityIdentifier("closeChatButton") }
                    ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("完成输入") { focused = false }.accessibilityIdentifier("hideChatKeyboardButton") }
                }
        }
        .onAppear {
            draftBoardID = store.selectedID; input = store.current.composerDraft ?? ""
            #if DEBUG
            CanvasUITestFixtures.scheduleHistoryReply(in: store)
            #endif
        }
        .onChange(of: store.selectedID) { _, boardID in
            speech.stop(); saveReadingPosition(); draftBoardID = boardID
            input = store.current.composerDraft ?? ""; readAnchor = nil
            followsLatest = true; userScrolling = false; hasNewReply = false
        }
        .onChange(of: input) { _, text in if draftBoardID == store.selectedID { store.setComposerDraft(text) } }
        .onChange(of: speech.transcript) { _, text in if !text.isEmpty, draftBoardID == store.selectedID { input = speechPrefix + text } }
        .onDisappear {
            speech.stop()
            if draftBoardID == store.selectedID { store.setComposerDraft(input) }
            saveReadingPosition()
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background || (phase == .inactive && (speech.recording || speech.finishing)) { speech.stop() }
        }
        .alert("语音输入", isPresented: Binding(get: { speech.error != nil }, set: { if !$0 { speech.error = nil } })) { Button("知道了") { speech.error = nil } } message: { Text(speech.error ?? "") }
    }
    private func saveReadingPosition() {
        guard !draftBoardID.isEmpty else { return }
        var positions = (try? JSONDecoder().decode([String: String].self, from: Data(savedReadingPositions.utf8))) ?? [:]
        positions[draftBoardID] = followsLatest ? nil : readAnchor
        if let data = try? JSONEncoder().encode(positions), let text = String(data: data, encoding: .utf8) { savedReadingPositions = text }
    }
    private func submit(_ text: String) {
        speech.stop(); userScrolling = false; followsLatest = true; hasNewReply = false
        store.send(text)
        // A rejected submission keeps its editable draft. An accepted request remains in this panel.
        if store.busyBoardID != nil { input = ""; focused = false }
    }
    private func messageBubble(_ message: RadarMessage) -> some View {
        let fromUser = message.role == "user"
        return HStack(alignment: .top, spacing: 0) {
            if fromUser { Spacer(minLength: 42) }
            VStack(alignment: fromUser ? .trailing : .leading, spacing: 7) {
                HStack(spacing: 6) {
                    Image(systemName: fromUser ? "person.crop.circle.fill" : "sparkles")
                    Text(fromUser ? "你" : (store.mode == .demo ? "示例" : store.assistantName))
                }.font(.system(size: 11, weight: .medium)).foregroundStyle(RadarPalette.green.opacity(0.85)).padding(.horizontal, 5)
                VStack(alignment: .leading, spacing: 12) {
                    Text(message.content).font(.system(size: 15)).lineSpacing(5).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if message.delivery == "failed" {
                        Button { input = message.content; focused = true } label: {
                            Label("重新编辑", systemImage: "arrow.clockwise").font(.system(size: 12, weight: .medium))
                        }.foregroundStyle(fromUser ? Color.white : RadarPalette.green)
                    } else if message.delivery == "pending" {
                        Text("正在发送…").font(.system(size: 11)).opacity(0.7)
                    }
                }.padding(.horizontal, 18).padding(.vertical, 16)
                    .foregroundStyle(fromUser ? Color.white : Color.primary)
                    .background(fromUser ? RadarPalette.green : RadarPalette.paper, in: RoundedRectangle(cornerRadius: 22))
            }
            if !fromUser { Spacer(minLength: 42) }
        }
    }
    private func demoAction(_ title: String, icon: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 11) { Image(systemName: icon).font(.system(size: 21, weight: .light)); Text(title).font(.system(size: 12, weight: .medium)) }
                .frame(maxWidth: .infinity).padding(.vertical, 20).background(RadarPalette.sage, in: RoundedRectangle(cornerRadius: 20))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier(id)
    }
}

struct MacConnectionSheet: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @State private var address = ""
    @State private var token = ""
    @State private var checking = false
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Label(store.connected ? "Mac 已连接" : "连接 Mac", systemImage: "laptopcomputer.and.iphone").font(.headline)
                    if store.connected { Text(store.modelName).font(.caption).foregroundStyle(.secondary) }
                }.listRowBackground(RadarPalette.paper)
                Section {
                    TextField("Mac 地址", text: $address).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled().accessibilityIdentifier("serverAddressInput")
                    SecureField("配对码", text: $token).textInputAutocapitalization(.never).autocorrectionDisabled().accessibilityIdentifier("pairingTokenInput")
                    Button {
                        checking = true
                        Task {
                            if await store.pair(url: address, token: token) { dismiss() }
                            checking = false
                        }
                    } label: { HStack { Text(checking ? "正在连接…" : "连接"); if checking { Spacer(); ProgressView() } } }
                        .disabled(checking || token.isEmpty || store.busyBoardID != nil)
                    if let error = store.error { Text(error).font(.caption).foregroundStyle(.orange) }
                } footer: { Text("与 Mac 连接同一网络，或用相机扫描配对码。") }
                    .listRowBackground(RadarPalette.paper)
            }.scrollContentBackground(.hidden).background(RadarPalette.canvas)
                .navigationTitle("Mac 配对").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
                .onAppear { address = store.serverURL }
        }
    }
}

struct RelationsSheet: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(store.current.edges) { edge in
                        VStack(alignment: .leading, spacing: 8) {
                            Text((store.current.cards.first { $0.id == edge.fromID }?.title ?? "") + " → " + (store.current.cards.first { $0.id == edge.toID }?.title ?? "")).font(.subheadline)
                            TextField("关系名称", text: Binding(get: { store.current.edges.first(where: { $0.id == edge.id })?.label ?? "" }, set: { label in
                                store.update { board in if let i = board.edges.firstIndex(where: { $0.id == edge.id }) { board.edges[i].label = label } }
                            })).font(.caption).foregroundStyle(.secondary).disabled(store.isRunning)
                        }.padding(.vertical, 6)
                    }.onDelete { indices in
                        let ids = indices.map { store.current.edges[$0].id }
                        for id in ids { store.removeEdge(id) }
                    }.deleteDisabled(store.isRunning)
                }.listRowBackground(RadarPalette.paper)
            }.scrollContentBackground(.hidden).background(RadarPalette.canvas)
                .navigationTitle("连接关系").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
        }
    }
}
