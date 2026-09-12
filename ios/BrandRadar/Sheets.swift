import SwiftUI

enum RadarPalette {
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
    @State private var restoring: RadarCard?
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    ForEach(store.visibleBoards) { board in
                        Button { store.select(board); dismiss() } label: {
                            HStack(spacing: 17) {
                                ZStack {
                                    RoundedRectangle(cornerRadius: 9).fill(RadarPalette.sage).frame(width: 39, height: 49).rotationEffect(.degrees(-10)).offset(x: -3)
                                    RoundedRectangle(cornerRadius: 9).fill(Color(board.visibleCards.first?.uiColor ?? .white)).frame(width: 37, height: 47).rotationEffect(.degrees(5)).offset(x: 4)
                                    Image(systemName: "scribble").font(.system(size: 21, weight: .light)).foregroundStyle(RadarPalette.green)
                                }.frame(width: 54, height: 61)
                                VStack(alignment: .leading, spacing: 7) {
                                    Text(board.title).font(.system(size: 16, weight: .semibold)).foregroundStyle(.primary).lineLimit(2)
                                    Text("\(board.template) · \(board.visibleCards.count) 张卡片").font(.system(size: 11)).foregroundStyle(.secondary)
                                }
                                Spacer(minLength: 4)
                                Image(systemName: board.id == store.selectedID ? "checkmark.circle.fill" : "chevron.right")
                                    .font(.system(size: board.id == store.selectedID ? 19 : 11)).foregroundStyle(board.id == store.selectedID ? RadarPalette.green : .secondary)
                            }.padding(18).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 23))
                                .contentShape(Rectangle())
                        }.buttonStyle(.plain)
                    }
                    if store.current.cards.contains(where: { $0.status == "archived" }) {
                        VStack(alignment: .leading, spacing: 14) {
                            Text("已放下").font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
                            ForEach(store.current.cards.filter { $0.status == "archived" }) { card in
                                Button { restoring = card } label: {
                                    HStack { Text(card.title).lineLimit(1); Spacer(); Image(systemName: "arrow.uturn.backward") }
                                        .font(.subheadline).padding(.vertical, 6).contentShape(Rectangle())
                                }.disabled(store.isRunning)
                            }
                        }.padding(20).background(.white.opacity(0.5), in: RoundedRectangle(cornerRadius: 23)).padding(.top, 10)
                    }
                }.padding(20)
            }.background(RadarPalette.canvas)
                .navigationTitle(store.mode == .demo ? "示例画布" : "我的画布").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
        }.sheet(item: $restoring) { CardEditor(card: $0).environmentObject(store) }
    }
}

struct CardEditor: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @State var card: RadarCard
    @State private var originalCard: RadarCard
    init(card: RadarCard) { _card = State(initialValue: card); _originalCard = State(initialValue: card) }
    @State private var sharing: ShareContent?
    private let colors = [("cream", "奶油"), ("sage", "鼠尾草"), ("rose", "粉桃"), ("lavender", "丁香"), ("sand", "麦黄")]
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 16) {
                        TextField("标题", text: $card.title, axis: .vertical).font(.system(size: 26, weight: .semibold)).accessibilityIdentifier("cardTitleInput")
                        Rectangle().fill(.black.opacity(0.07)).frame(height: 1)
                        RichContentEditor(blocks: Binding(get: { card.effectiveBlocks }, set: { card.blocks = $0; card.body = $0.map(\.summary).joined(separator: "\n\n") })) { blockID in
                            store.editCard(card, baseline: originalCard)
                            store.splitBlock(cardID: card.id, blockID: blockID)
                            if let latest = store.current.cards.first(where: { $0.id == card.id }) { card = latest; originalCard = latest }
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
                                            Button("查看原素材", systemImage: "arrow.up.left.and.arrow.down.right") { store.focusNode(original.id); dismiss() }
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
                            card.status = card.status == "archived" ? "draft" : "archived"; store.editCard(card, baseline: originalCard); store.selectedCardID = nil; dismiss()
                        }.foregroundStyle(.secondary)
                    }.font(.subheadline).padding(.horizontal, 5).padding(.bottom, 10)
                }.padding(20)
            }.background(RadarPalette.canvas).navigationTitle("卡片").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("取消") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("保存") { store.editCard(card, baseline: originalCard); dismiss() }.bold().disabled(card.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty).accessibilityIdentifier("saveCardButton")
                    }
                }
                .safeAreaInset(edge: .bottom) {
                    if store.isRunning { Text("正在改稿…").font(.caption).padding(10).frame(maxWidth: .infinity).background(.regularMaterial) }
                }
        }.sheet(item: $sharing) { ShareSheet(items: $0.items) }
    }
}

struct ChatSheet: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var speech = SpeechInput()
    @State private var input = ""
    @State private var speechPrefix = ""
    @FocusState private var focused: Bool
    private let suggestions = [("想方向", "围绕当前 Brief，展开三个有差异的创意方向。"), ("写内容", "把当前想法写成一份可以分享的内容稿。"), ("理结构", "整理当前画布，连起重要的逻辑关系。")]
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if let card = store.selectedCard {
                    HStack(spacing: 9) {
                        Image(systemName: card.symbol)
                        Text(card.title).lineLimit(1)
                        Spacer()
                        Button { store.selectedCardID = nil } label: { Image(systemName: "xmark") }.accessibilityLabel("取消选择")
                    }.font(.system(size: 12)).padding(14).background(Color(card.uiColor), in: RoundedRectangle(cornerRadius: 16)).padding(.horizontal, 20).padding(.top, 8)
                }
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 20) {
                            if store.mode == .demo {
                                VStack(alignment: .leading, spacing: 16) {
                                    Text("示例画布").font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary)
                                    HStack(spacing: 9) {
                                        demoAction("展开画布", icon: "square.grid.2x2", id: "demoStartButton") { store.selectedCardID = nil; store.send(DemoCanvas.startPrompt); dismiss() }
                                        demoAction("改写这张", icon: "pencil.line", id: "demoRefineButton") { store.send(DemoCanvas.refinePrompt); dismiss() }.disabled(store.selectedCardID == nil)
                                        demoAction("写内容稿", icon: "text.alignleft", id: "demoCopyButton") { store.send(DemoCanvas.copyPrompt); dismiss() }
                                    }
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
                            }
                            if store.isRunning { HStack { ProgressView(); Text(store.activity).font(.caption) }.padding(.vertical, 8) }
                            Color.clear.frame(height: 1).id("end")
                        }.padding(20)
                    }
                    .onAppear { DispatchQueue.main.async { proxy.scrollTo("end", anchor: .bottom) } }
                    .onChange(of: store.current.messages.count) { _, _ in withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("end", anchor: .bottom) } }
                    .onChange(of: store.current.messages.last?.content) { _, _ in proxy.scrollTo("end", anchor: .bottom) }
                    .onChange(of: store.isRunning) { _, _ in proxy.scrollTo("end", anchor: .bottom) }
                }
                VStack(spacing: 10) {
                    if let error = store.error {
                        HStack(alignment: .top) {
                            Text(error).font(.caption).foregroundStyle(.orange).accessibilityIdentifier("chatError")
                            Spacer(minLength: 8)
                            Button { store.error = nil } label: { Image(systemName: "xmark.circle") }.accessibilityLabel("关闭提示")
                        }.padding(.horizontal, 9)
                    }
                    if speech.recording {
                        HStack { Image(systemName: "waveform").symbolEffect(.variableColor); Text("正在听…").font(.caption) }.foregroundStyle(.red)
                    }
                    HStack(alignment: .bottom, spacing: 12) {
                        Button {
                            if speech.recording { speech.finish { text in input = speechPrefix + text } }
                            else { speechPrefix = input.isEmpty ? "" : input + "\n"; Task { await speech.start(requireOnDevice: store.mode == .demo) } }
                        } label: { Image(systemName: speech.recording ? "stop.circle.fill" : "mic").font(.system(size: 21)).frame(width: 34, height: 42) }
                            .accessibilityLabel(speech.recording ? "结束听写" : "开始听写").disabled(speech.starting || speech.finishing)
                        TextField("说出你的想法", text: $input, axis: .vertical).lineLimit(1...6).focused($focused).padding(.vertical, 11).accessibilityIdentifier("composerInput")
                        Button {
                            speech.stop(); store.send(input)
                            if store.busyBoardID != nil { input = ""; focused = false; dismiss() }
                        } label: { Image(systemName: "arrow.up").bold().foregroundStyle(.white).frame(width: 42, height: 42).background(RadarPalette.green, in: Circle()) }
                            .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.busyBoardID != nil || speech.recording || speech.finishing).accessibilityIdentifier("sendButton")
                    }.padding(10).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 27))
                        .overlay(RoundedRectangle(cornerRadius: 27).stroke(.black.opacity(0.05)))
                }.padding(.horizontal, 16).padding(.bottom, 12)
            }.background(RadarPalette.canvas).navigationTitle(store.mode == .demo ? "示例画布" : "对话").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() }.accessibilityIdentifier("closeChatButton") } }
        }
        .onAppear { input = store.current.composerDraft ?? "" }
        .onChange(of: input) { _, text in store.update { $0.composerDraft = text } }
        .onChange(of: speech.transcript) { _, text in input = speechPrefix + text }
        .onDisappear { speech.stop() }
        .onChange(of: scenePhase) { _, phase in if phase == .background { speech.stop() } }
        .alert("语音输入", isPresented: Binding(get: { speech.error != nil }, set: { if !$0 { speech.error = nil } })) { Button("知道了") { speech.error = nil } } message: { Text(speech.error ?? "") }
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
