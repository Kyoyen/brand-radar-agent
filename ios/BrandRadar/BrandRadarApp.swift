import SwiftUI
import UniformTypeIdentifiers

@main struct BrandRadarApp: App {
    @StateObject private var store = BoardStore()
    var body: some Scene {
        WindowGroup {
            WorkspaceView().environmentObject(store)
                .tint(Color(red: 0.24, green: 0.39, blue: 0.25))
                .preferredColorScheme(.light)
                .onOpenURL { url in
                    if url.isFileURL { do { store.importCanvas(try CanvasExport.importPackage(url)) } catch { store.error = error.localizedDescription } }
                    else { Task { await store.handleURL(url) } }
                }
                .task {
                    #if DEBUG
                    CanvasUITestFixtures.install(in: store)
                    if ProcessInfo.processInfo.arguments.contains("--uitesting") && ProcessInfo.processInfo.arguments.contains("--canvas-perfcheck") {
                        var result: [String: Any] = [:]
                        do { result["passed"] = try CanvasGeometryChecks.run(); result["benchmark"] = CanvasGeometryChecks.benchmark; result["status"] = "passed" }
                        catch { result["status"] = "failed"; result["error"] = String(describing: error) }
                        let url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("canvas-performance.json")
                        try? JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
                    }
                    if ProcessInfo.processInfo.arguments.contains("--uitesting") && ProcessInfo.processInfo.arguments.contains("--canvas-capacitycheck") {
                        var result: [String: Any]
                        do { result = try CapacityChecks.run() } catch { result = ["status": "failed", "error": String(describing: error)] }
                        let url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("canvas-capacity.json")
                        try? JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
                    }
                    if ProcessInfo.processInfo.arguments.contains("--canvas-selfcheck") {
                        let result = CanvasAcceptance.run(store: store)
                        let url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("canvas-checks.json")
                        try? JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
                    }
                    #endif
                    #if DEBUG
                    if ProcessInfo.processInfo.arguments.contains("--uitesting") && ProcessInfo.processInfo.arguments.contains("--live-review-fixture") {
                        let baseline = store.current
                        _ = store.beginVoiceSession(requiresConfirmation: true)
                        let card = RadarCard(id: "beta-review-card", title: "口述生成的方向", body: "一起去户外", x: 0, y: 0)
                        _ = store.acceptTestUpdate(DirectAgentResult(cards: [card], edges: [], removeIDs: [], removeEdgeIDs: [], summary: ""), base: baseline)
                        store.sealTestSession()
                    }
                    #endif
                    await store.checkConnection()
                }
        }
    }
}

struct WorkspaceView: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.scenePhase) private var scenePhase
    @State private var sheet: WorkspaceSheet?
    @State private var editingCard: RadarCard?
    @State private var reading: ReadingTarget?
    @State private var readerAction: String?
    @State private var chatDetent: PresentationDetent = .medium
    @State private var previousCamera: CameraBookmark?
    @State private var changeIndex = 0
    @State private var sharing: ShareContent?
    @State private var renaming = false
    @State private var boardName = ""
    @State private var importingCanvas = false
    @StateObject private var dockSpeech = SpeechInput()
    @State private var dockHeight: CGFloat = 120
    @State private var voicePanelHeight: CGFloat = 0
    @State private var liveDrawing = false
    @State private var holdingVoice = false
    @State private var cancellingVoice = false
    @State private var voiceBoardID: String?
    private let ink = Color(red: 0.14, green: 0.19, blue: 0.14)
    var body: some View {
        ZStack {
            InfiniteCanvas(store: store, bottomInset: sheet == .chat && chatDetent == .medium ? max(dockHeight + voicePanelHeight + 45, UIScreen.main.bounds.height * 0.52) : dockHeight + voicePanelHeight + 45,
                           onRead: { id in reading = ReadingTarget(boardID: store.selectedID, cardID: id) },
                           onContinue: { id in store.selectedCardID = id; sheet = .chat }) { id in
                editingCard = store.current.cards.first { $0.id == id }
            }.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                HStack {
                    Text("\(store.current.visibleCards.count) 张卡片").font(.system(size: 10)).accessibilityIdentifier("cardCountLabel")
                    Spacer()
                }.foregroundStyle(.secondary).padding(.horizontal, 25).padding(.top, 10)
                Spacer()
                if store.current.visibleCards.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "scribble.variable").font(.system(size: 46, weight: .ultraLight))
                        Text("想法还没有边界").font(.system(size: 26, weight: .medium))
                        Text("写一点，或聊一聊。") .font(.subheadline).foregroundStyle(.secondary)
                        Button("选个模板") { sheet = .templates }.buttonStyle(.borderedProminent)
                    }.padding(.bottom, 50)
                    Spacer()
                }
                if let from = store.linkingFrom {
                    HStack {
                        Image(systemName: "arrow.triangle.branch")
                        Text("点另一张卡片，建立关系").font(.subheadline)
                        Button("取消") { store.linkingFrom = nil }
                    }.padding(14).background(.regularMaterial, in: Capsule()).padding(.bottom, 12)
                    .accessibilityIdentifier("linking_\(from)")
                }
                HStack {
                    HStack(spacing: 15) {
                        Button { store.fitRequest += 1 } label: { Image(systemName: "arrow.up.left.and.arrow.down.right") }
                            .accessibilityLabel("查看全貌").accessibilityIdentifier("fitButton")
                        Text(String(format: store.current.zoom < 0.1 ? "%.1f%%" : "%.0f%%", store.current.zoom * 100)).font(.system(size: 11, weight: .medium, design: .monospaced)).frame(minWidth: 35).accessibilityIdentifier("zoomLabel")
                    }.padding(.horizontal, 17).frame(height: 44).background(.regularMaterial, in: Capsule())
                    Spacer()
                    Button { store.addNote() } label: { Image(systemName: "plus").font(.system(size: 21, weight: .medium)).frame(width: 46, height: 46) }
                        .background(.regularMaterial, in: Circle()).accessibilityLabel("添加便签").accessibilityIdentifier("addNoteButton")

                }.padding(.horizontal, 22).padding(.bottom, 15)
                if let sessionID = store.splitUndoSessionID, store.current.editHistory?.last?.id == sessionID {
                    HStack {
                        Text("已保存并转为节点").font(.subheadline)
                        Spacer()
                        Button("撤销") { store.undo(); store.splitUndoSessionID = nil }
                            .disabled(!store.canUndo).accessibilityIdentifier("undoSplitButton")
                    }.padding(14).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
                        .padding(.horizontal, 22).padding(.bottom, 10)
                }
                changeBar
                voicePanel
                    .background(GeometryReader { proxy in Color.clear.preference(key: VoicePanelHeightKey.self, value: proxy.size.height) })
                chatDock
                    .background(GeometryReader { proxy in Color.clear.preference(key: DockHeightKey.self, value: proxy.size.height) })
            }
        }
        .onPreferenceChange(DockHeightKey.self) { if abs(dockHeight - $0) > 1 { dockHeight = $0 } }
        .onPreferenceChange(VoicePanelHeightKey.self) { if abs(voicePanelHeight - $0) > 1 { voicePanelHeight = $0 } }
        .foregroundStyle(ink)
        .sheet(item: $sheet) { item in
            switch item {
            case .templates: TemplateSheet().environmentObject(store)
            case .chat: ChatSheet(onViewChanges: { sheet = nil; if let result = store.latestChange { locateChange(result) } }).environmentObject(store)
                    .presentationDetents([.medium, .large], selection: $chatDetent)
                    .presentationBackgroundInteraction(.enabled(upThrough: .medium))
                    .presentationDragIndicator(.visible)
            case .settings: ConnectionSheet().environmentObject(store)
            case .boards: BoardLibrary().environmentObject(store)
            case .relations: RelationsSheet().environmentObject(store)
            case .archive: CurrentArchiveSheet().environmentObject(store)
            }
        }
        .sheet(item: $reading, onDismiss: {
            guard let action = readerAction else { return }; readerAction = nil
            if action == "chat" { sheet = .chat }
            else { editingCard = store.current.visibleCards.first { $0.id == action } }
        }) { target in
            CardReader(store: store, boardID: target.boardID, cardID: target.cardID,
                       onEdit: { id in readerAction = id; reading = nil },
                       onContinue: { id in store.selectedCardID = id; readerAction = "chat"; reading = nil })
        }
        .sheet(item: $editingCard) { card in CardEditor(card: card).environmentObject(store) }
        .sheet(item: $sharing) { content in ShareSheet(items: content.items) }
        .alert("需要留意", isPresented: Binding(get: { store.error != nil && sheet == nil && editingCard == nil && reading == nil }, set: { if !$0 { store.error = nil } })) {
            Button("知道了", role: .cancel) { store.error = nil }
        } message: { Text(store.error ?? "") }
        .alert("给画布起个名字", isPresented: $renaming) {
            TextField("画布名称", text: $boardName)
            Button("保存") { store.renameBoard(boardName) }
            Button("取消", role: .cancel) {}
        }
        .fileImporter(isPresented: $importingCanvas, allowedContentTypes: [.data, .item]) { result in
            do { let url = try result.get(); store.importCanvas(try CanvasExport.importPackage(url)) }
            catch { store.error = error.localizedDescription }
        }
        .onDisappear { interruptDockVoice() }
        .onChange(of: sheet) { _, value in if value != nil { interruptDockVoice() } }
        .onChange(of: editingCard?.id) { _, value in if value != nil { interruptDockVoice() } }
        .onChange(of: sharing?.id) { _, value in if value != nil { interruptDockVoice() } }
        .onChange(of: renaming) { _, value in if value { interruptDockVoice() } }
        .onChange(of: store.selectedID) { _, _ in interruptDockVoice(); previousCamera = nil; changeIndex = 0 }
        .onChange(of: reading?.id) { _, value in if value != nil { interruptDockVoice() } }

        .onChange(of: dockSpeech.transcript) { _, text in if voiceBoardID != nil && liveDrawing { store.receiveVoice(text) } }
        .onChange(of: dockSpeech.error) { _, value in if let value { interruptDockVoice(); store.error = value } }
        .onAppear { if store.voiceAwaitingReview { liveDrawing = true } }
        .onChange(of: store.voiceAwaitingReview) { _, value in if value { liveDrawing = true } }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background || (phase == .inactive && (dockSpeech.recording || dockSpeech.finishing)) { interruptDockVoice(); store.interruptVoiceSession(); store.persist() }
            else { Task { await store.checkConnection() } }
        }
    }
    private var header: some View {
        HStack(spacing: 12) {
            Button { sheet = .boards } label: {
                Image(systemName: "square.stack.3d.up").font(.system(size: 19)).frame(width: 44, height: 44)
            }.background(.white.opacity(0.82), in: Circle()).accessibilityLabel("我的画布").accessibilityIdentifier("boardsButton").disabled(store.voiceSession != nil)
            VStack(alignment: .leading, spacing: 3) {
                Text("BRANDAR").font(.system(size: 9, weight: .bold, design: .monospaced)).tracking(2.4)
                Text(store.current.title).font(.system(size: 16, weight: .semibold)).lineLimit(1).accessibilityIdentifier("boardTitle")
            }
            Spacer(minLength: 0)
            Menu {
                Button("重命名画布", systemImage: "pencil") { boardName = store.current.title; renaming = true }
                Button("整理画布", systemImage: "rectangle.3.group") { store.arrange() }
                Button("管理连接关系", systemImage: "arrow.triangle.branch") { sheet = .relations }
                Button("已放下", systemImage: "archivebox") { sheet = .archive }.accessibilityIdentifier("archiveButton")
                if store.mode == .practice && store.transport == .mac {
                    Button("刷新画布", systemImage: "arrow.clockwise") { Task { await store.refresh() } }
                }
                Button("撤销", systemImage: "arrow.uturn.backward") { store.undo() }.disabled(!store.canUndo)
                Button("重做", systemImage: "arrow.uturn.forward") { store.redo() }.disabled(!store.canRedo)
                Button("导出图片", systemImage: "photo") { exportCanvas("png") }
                Button("导出 PDF", systemImage: "doc") { exportCanvas("pdf") }
                Button("导出阅读稿", systemImage: "doc.text") { exportCanvas("markdown") }
                Button("分享可编辑画布", systemImage: "square.and.arrow.up") { exportCanvas("package") }
                Button("导入画布", systemImage: "square.and.arrow.down") { importingCanvas = true }
            } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }.accessibilityLabel("画布操作")
            Button { sheet = .settings } label: { Image(systemName: "antenna.radiowaves.left.and.right").font(.system(size: 18)).frame(width: 44, height: 44) }
                .accessibilityLabel("连接设置").accessibilityIdentifier("settingsButton")
        }.padding(.horizontal, 18).padding(.top, 10)
    }
    private func selectionBar(_ card: RadarCard) -> some View {
        HStack(spacing: 20) {
            Button { editingCard = card } label: { Label("编辑", systemImage: "pencil") }.accessibilityIdentifier("editCardButton")
            Button { store.linkingFrom = card.id } label: { Label("连接", systemImage: "arrow.triangle.branch") }
            Button { sheet = .chat } label: { Label("聊这张", systemImage: "sparkles") }
            Button { store.selectedCardID = nil } label: { Image(systemName: "xmark") }.accessibilityLabel("取消选择")
        }.font(.system(size: 12, weight: .medium)).padding(.horizontal, 18).frame(height: 48)
            .background(.regularMaterial, in: Capsule()).padding(.bottom, 13)
    }
    private var chatDock: some View {
        VStack(spacing: 0) {
            HStack {
                Button { liveDrawing = false } label: { Text("听写 / 打字").fontWeight(liveDrawing ? .regular : .semibold) }
                    .accessibilityIdentifier("briefModeButton")
                Button { liveDrawing = true } label: { Text("边说边画 · Beta").fontWeight(liveDrawing ? .semibold : .regular) }
                    .accessibilityIdentifier("liveDrawingModeButton")
                Spacer()
            }.font(.caption).buttonStyle(.plain).padding(.horizontal, 22).padding(.top, 14)
                .disabled(holdingVoice || dockSpeech.finishing || store.voiceSession != nil)
            if let clarification = store.clarification, store.voiceSession == nil {
                Button { sheet = .chat } label: { Text(clarification).font(.caption).multilineTextAlignment(.leading).lineLimit(3) }.padding(.horizontal, 19).padding(.top, 12)
            }
            if store.voiceSession == nil, !(store.current.pendingSpeech ?? "").isEmpty {
                Button("继续整理刚才的话") { store.resumeVoice() }.font(.caption).padding(.top, 12)
            }
            if store.isRunning && store.voiceSession == nil {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(store.activity).font(.caption).lineLimit(1)
                    Spacer()
                    Button("停止") { Task { await store.stop() } }.font(.caption)
                }.padding(.horizontal, 19).padding(.top, 13)
            }
            HStack(spacing: 12) {
                Button { sheet = .templates } label: {
                    Image(systemName: "square.grid.2x2").font(.system(size: 19)).frame(width: 42, height: 48)
                }.accessibilityLabel("画布模板").accessibilityIdentifier("templatesButton").disabled(store.voiceSession != nil)
                Rectangle().fill(ink.opacity(0.12)).frame(width: 1, height: 25)
                HoldToTalkControl(title: voiceTitle, voiceEnabled: (holdingVoice || (!store.isRunning && store.voiceSession == nil)) && !dockSpeech.finishing,
                                  active: holdingVoice || dockSpeech.finishing,
                                  liveDrawing: liveDrawing,
                                  onTap: { guard store.voiceSession == nil else { return }; interruptDockVoice(); sheet = .chat },
                                  onBegin: beginDockVoice,
                                  onCancelChange: { cancellingVoice = $0 },
                                  onEnd: endDockVoice)
                    .frame(height: 48)
                    .opacity(store.voiceAwaitingReview ? 0.48 : 1)
                    .allowsHitTesting(!store.voiceAwaitingReview)

            }.padding(.horizontal, 13).padding(.vertical, 14)
        }.background(.white.opacity(0.96), in: RoundedRectangle(cornerRadius: 28))
            .overlay(RoundedRectangle(cornerRadius: 28).strokeBorder(.black.opacity(0.04)))
            .shadow(color: .black.opacity(0.06), radius: 18, y: 4)
            .padding(.horizontal, 16).padding(.bottom, 8)
    }
    @ViewBuilder private var voicePanel: some View {
        if store.voiceAwaitingReview {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("保留这次画布变化？").font(.subheadline.weight(.semibold)).accessibilityIdentifier("liveDrawingReview")
                    Spacer()
                    Button("查看全貌") { store.fitRequest += 1 }
                        .font(.caption).frame(minHeight: 44).accessibilityIdentifier("reviewFitButton")
                }
                Text(hasVoiceChanges ? store.voiceChangeSummary : "画布没有产生变化")
                    .font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("liveChangeSummary")
                HStack(spacing: 12) {
                    Button(hasVoiceChanges ? "放弃本次变化" : "放弃口述") { store.cancelVoiceSession() }
                        .frame(minHeight: 44).accessibilityIdentifier("discardLiveDrawingButton")
                    Spacer()
                    Button(hasVoiceChanges ? "保留变化" : "保留口述") { store.keepVoiceChanges() }
                        .buttonStyle(.borderedProminent).frame(minHeight: 44)
                        .accessibilityIdentifier("keepLiveDrawingButton")
                }.font(.subheadline)
            }
            .padding(.horizontal, 16).padding(.vertical, 10)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
            .padding(.horizontal, 18).padding(.bottom, 8)
        } else if holdingVoice || dockSpeech.finishing || (liveDrawing && store.voiceSession != nil) {
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 7) {
                    Image(systemName: cancellingVoice ? "xmark.circle.fill" : "waveform")
                        .foregroundStyle(cancellingVoice ? .orange : ink)
                    Text(liveDrawing ? "边说边画 · Beta" : "听写草稿")
                        .font(.caption.weight(.semibold))
                    Spacer()
                    Text(voiceTitle).font(.caption).foregroundStyle(.secondary)
                        .accessibilityIdentifier("voiceState")
                    Button("取消") { cancelDockVoice() }.font(.caption)
                        .frame(minWidth: 44, minHeight: 44).accessibilityIdentifier("cancelVoiceButton")
                }
                Text(voiceTranscriptPreview)
                    .font(.subheadline).lineLimit(2).frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityLabel(voiceTranscript)
                    .accessibilityIdentifier("liveTranscript")
                if liveDrawing {
                    Text(voiceCanvasStatus).font(.caption2).foregroundStyle(.secondary)
                        .accessibilityIdentifier("liveChangeSummary")
                } else {
                    Text("松开后可检查和修改文字，再决定是否发送")
                        .font(.caption2).foregroundStyle(.secondary)
                }
                if let clarification = store.clarification, liveDrawing {
                    Text(clarification).font(.caption).lineLimit(2)
                }
            }
            .padding(.horizontal, 15).padding(.vertical, 7)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
            .padding(.horizontal, 18).padding(.bottom, 8)
        }
    }
    private var hasVoiceChanges: Bool { store.voiceHasVisibleChanges }
    private var voiceTranscript: String {
        let text = dockSpeech.transcript.isEmpty ? store.voiceSession?.transcript ?? "" : dockSpeech.transcript
        return text.isEmpty ? (dockSpeech.starting ? "正在准备麦克风…" : "正在聆听…") : text
    }
    private var voiceTranscriptPreview: String {
        let text = voiceTranscript
        return text.count > 100 ? "…" + String(text.suffix(100)) : text
    }
    private var voiceCanvasStatus: String {
        if hasVoiceChanges { return store.voiceChangeSummary }
        if store.isRunning { return "正在整理画布…" }
        return "画布还没有变化"
    }
    @ViewBuilder private var changeBar: some View {
        if let result = store.latestChange, result.boardID == store.selectedID {
            VStack(alignment: .leading, spacing: 5) {
                Text(result.text).font(.subheadline).accessibilityIdentifier("changeSummary")
                HStack(spacing: 14) {
                    if !result.targetIDs.isEmpty {
                        Button("查看变化") { locateChange(result) }.accessibilityIdentifier("viewChangesButton")
                    }
                    if previousCamera?.boardID == store.selectedID {
                        Button("返回原处") {
                            if let camera = previousCamera { store.setViewport(x: camera.x, y: camera.y, zoom: camera.zoom); store.selectedCardID = camera.selection }
                            previousCamera = nil
                        }.accessibilityIdentifier("returnCameraButton")
                    }
                    Spacer(minLength: 0)
                    if store.current.editHistory?.contains(where: { $0.id == result.id }) == true {
                        Button("撤回本轮") { store.undoChanges(sessionID: result.id) }.disabled(store.voiceSession != nil)
                            .accessibilityIdentifier("undoRoundButton")
                    }
                    Button { store.latestChange = nil; previousCamera = nil } label: { Image(systemName: "xmark") }
                        .accessibilityLabel("收起变化提示")
                }.font(.subheadline).buttonStyle(.borderless).frame(minHeight: 44)
            }.padding(.horizontal, 16).padding(.top, 12).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
                .padding(.horizontal, 20).padding(.bottom, 10)
        }
    }
    private func locateChange(_ result: CanvasChangeSummary) {
        let targets = result.targetIDs.filter { id in store.current.visibleCards.contains { $0.id == id } || (store.current.groups ?? []).contains { $0.id == id } }
        guard !targets.isEmpty else { return }
        if previousCamera == nil {
            previousCamera = CameraBookmark(boardID: store.selectedID, x: store.current.offsetX, y: store.current.offsetY, zoom: store.current.zoom, selection: store.selectedCardID)
        }
        store.focusNode(targets[changeIndex % targets.count]); changeIndex += 1
    }
    private var voiceTitle: String {
        if store.voiceAwaitingReview { return "请先保留或放弃" }
        if cancellingVoice { return "松开取消" }
        if dockSpeech.finishing { return liveDrawing ? "正在完成画布…" : "正在完成听写…" }
        if dockSpeech.starting { return "正在准备…" }
        if holdingVoice { return liveDrawing ? "松开后确认" : "松开查看草稿" }
        if liveDrawing && store.voiceSession != nil { return store.isRunning ? "正在整理画布…" : "正在等待画布变化…" }
        return liveDrawing ? "按住，边说边画" : "轻点打字 · 按住听写"
    }
    private func beginDockVoice() {
        guard !store.isRunning, store.voiceSession == nil, !dockSpeech.finishing else { return }
        if liveDrawing && !store.beginVoiceSession(requiresConfirmation: true) { return }
        dockSpeech.transcript = ""
        holdingVoice = true; cancellingVoice = false; voiceBoardID = store.selectedID
        Task { @MainActor in
            guard holdingVoice else { return }
            await dockSpeech.start(requireOnDevice: store.mode == .demo)
        }
    }
    private func endDockVoice(_ cancelled: Bool) {
        guard holdingVoice else { return }
        holdingVoice = false; cancellingVoice = false
        guard !cancelled, let boardID = voiceBoardID else { cancelDockVoice(); return }
        dockSpeech.finish { text in
            voiceBoardID = nil
            let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard scenePhase == .active, store.selectedID == boardID else {
                if liveDrawing { store.interruptVoiceSession() } else { store.appendDictation(text, boardID: boardID) }
                return
            }
            if liveDrawing { store.finishVoiceSession(text) }
            else if !text.isEmpty { store.appendDictation(text, boardID: boardID); sheet = .chat }
        }
    }
    private func cancelDockVoice() {
        holdingVoice = false; cancellingVoice = false; voiceBoardID = nil
        dockSpeech.stop(); store.cancelVoiceSession()
    }
    private func interruptDockVoice() {
        let interruptedBoardID = voiceBoardID
        let wasRecording = voiceBoardID != nil || holdingVoice || dockSpeech.recording || dockSpeech.finishing
        holdingVoice = false; cancellingVoice = false; voiceBoardID = nil
        dockSpeech.stop()
        if wasRecording {
            if liveDrawing { store.interruptVoiceSession() }
            else if let id = interruptedBoardID { store.appendDictation(dockSpeech.transcript, boardID: id) }
        }
    }
    private func exportCanvas(_ kind: String) {
        do {
            let url = try kind == "png" ? CanvasExport.png(board: store.current) : kind == "pdf" ? CanvasExport.pdf(board: store.current) : kind == "markdown" ? CanvasExport.markdown(board: store.current) : CanvasExport.package(board: store.current)
            sharing = ShareContent(items: [url])
        } catch { store.error = error.localizedDescription }
    }

}

enum WorkspaceSheet: String, Identifiable { case templates, chat, settings, boards, relations, archive; var id: String { rawValue } }
struct ShareContent: Identifiable { let id = UUID(); let items: [Any] }
struct ShareSheet: UIViewControllerRepresentable {
    var items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

private struct DockHeightKey: PreferenceKey {
    static var defaultValue: CGFloat = 120
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = nextValue() }
}
private struct VoicePanelHeightKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = nextValue() }
}

private struct ReadingTarget: Identifiable { let boardID: String; let cardID: String; var id: String { boardID + ":" + cardID } }
private struct CameraBookmark { let boardID: String; let x: Double; let y: Double; let zoom: Double; let selection: String? }
