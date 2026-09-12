import SwiftUI

struct ConnectionSheet: View {
    @EnvironmentObject private var store: BoardStore
    @Environment(\.dismiss) private var dismiss
    @State private var confirmReset = false
    private var modelTitle: String {
        if store.transport == .mac { return "Mac" }
        return store.assistantName
    }
    private var connectionDetail: String {
        if store.transport == .mac { return store.connected ? store.modelName : "未连接" }
        return store.apiKeyConfigured ? store.apiConfiguration.model : "未配置"
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    HStack(spacing: 15) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 27, weight: .light)).frame(width: 48, height: 48)
                            .background(RadarPalette.sage, in: RoundedRectangle(cornerRadius: 15))
                        VStack(alignment: .leading, spacing: 6) {
                            Text(modelTitle).font(.system(size: 17, weight: .semibold)).lineLimit(2)
                            Text(connectionDetail).font(.system(size: 12)).foregroundStyle(.secondary)
                        }
                        Spacer()
                    }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                        .background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 23))
                    NavigationLink {
                        ConnectionDetails(onClose: { dismiss() })
                    } label: {
                        HStack {
                            Label("连接设置", systemImage: "slider.horizontal.3")
                            Spacer()
                            Image(systemName: "chevron.right").font(.system(size: 11, weight: .medium)).foregroundStyle(.secondary)
                        }.font(.system(size: 15)).padding(21).background(RadarPalette.paper, in: RoundedRectangle(cornerRadius: 23)).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("connectionSettingsButton")
                    VStack(spacing: 0) {
                        Button {
                            store.setMode(store.mode == .demo ? .practice : .demo)
                            dismiss()
                        } label: {
                            HStack {
                                Label(store.mode == .demo ? "我的画布" : "示例画布", systemImage: store.mode == .demo ? "square.stack" : "play.rectangle")
                                Spacer()
                                Image(systemName: "chevron.right").font(.system(size: 11, weight: .medium))
                            }.font(.system(size: 14)).foregroundStyle(.secondary).padding(20).contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("modePicker")
                            .accessibilityValue(store.mode == .demo ? "示例画布" : "我的画布")
                            .disabled(store.busyBoardID != nil || store.testingAPI)
                        if store.mode == .demo {
                            Divider().padding(.horizontal, 20)
                            Button { confirmReset = true } label: {
                                HStack { Label("重置示例", systemImage: "arrow.counterclockwise"); Spacer() }
                                    .font(.system(size: 14)).foregroundStyle(.secondary).padding(20).contentShape(Rectangle())
                            }.buttonStyle(.plain).disabled(store.busyBoardID != nil).accessibilityIdentifier("resetDemoButton")
                        }
                    }.background(RadarPalette.paper.opacity(0.7), in: RoundedRectangle(cornerRadius: 23)).padding(.top, 18)
                }.padding(20)
            }.background(RadarPalette.canvas).navigationTitle("设置").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() }.accessibilityIdentifier("closeSettingsButton") } }
                .alert("重置这个示例？", isPresented: $confirmReset) {
                    Button("重置", role: .destructive) { store.resetDemo(); dismiss() }
                    Button("取消", role: .cancel) {}
                } message: { Text("当前示例会回到初始内容。") }
        }
    }
}

private struct ConnectionDetails: View {
    @EnvironmentObject private var store: BoardStore
    let onClose: () -> Void
    @State private var baseURL = ""
    @State private var model = ""
    @State private var apiKey = ""
    @State private var showMac = false
    @State private var confirmRemove = false
    private var configuration: AgentConnection {
        AgentConnection(provider: "自定义", baseURL: baseURL.trimmingCharacters(in: .whitespacesAndNewlines), model: model.trimmingCharacters(in: .whitespacesAndNewlines))
    }
    private var canSave: Bool {
        (try? configuration.endpointURL()) != nil && !configuration.model.isEmpty &&
        (!apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || (store.apiKeyConfigured && configuration.baseURL == store.apiConfiguration.baseURL))
    }
    var body: some View {
        Form {
            Section {
                Picker("连接方式", selection: Binding(get: { store.transport }, set: { store.setTransport($0) })) {
                    ForEach(AgentTransport.allCases) { transport in Text(transport.title).tag(transport) }
                }.pickerStyle(.segmented).disabled(store.busyBoardID != nil || store.testingAPI)
            }.listRowBackground(RadarPalette.paper)
            if store.transport == .api {
                Section {
                    TextField("API 地址", text: $baseURL).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled().accessibilityIdentifier("apiBaseURLInput")
                    TextField("模型名称", text: $model).textInputAutocapitalization(.never).autocorrectionDisabled().accessibilityIdentifier("apiModelInput")
                    SecureField(store.apiKeyConfigured ? "Key 已保存 · 可替换" : "API Key", text: $apiKey)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().privacySensitive().accessibilityIdentifier("apiKeyInput")
                } footer: { Text("Key 仅保存在这台手机。") }
                    .listRowBackground(RadarPalette.paper)
                Section {
                    Button("保存配置") { if store.saveAPI(configuration, key: apiKey) { apiKey = "" } }
                        .disabled(!canSave || store.busyBoardID != nil || store.testingAPI).accessibilityIdentifier("apiSaveButton")
                    Button { store.testAPI() } label: {
                        HStack { Text(store.testingAPI ? "正在测试…" : "测试连接"); if store.testingAPI { Spacer(); ProgressView() } }
                    }.disabled(!store.apiKeyConfigured || store.testingAPI || store.busyBoardID != nil).accessibilityIdentifier("apiTestButton")
                    if let feedback = store.connectionFeedback {
                        Text(feedback).font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("apiFeedback")
                    }
                }.listRowBackground(RadarPalette.paper)
                if store.apiKeyConfigured {
                    Section {
                        Button("移除已保存的 Key", role: .destructive) { confirmRemove = true }.disabled(store.busyBoardID != nil || store.testingAPI)
                    }.listRowBackground(RadarPalette.paper)
                }
            } else {
                Section {
                    Label(store.connected ? "Mac 已连接" : "Mac 未连接", systemImage: "laptopcomputer.and.iphone")
                    if !store.serverURL.isEmpty { Text(store.serverURL).font(.caption.monospaced()).foregroundStyle(.secondary) }
                    Button("配对 Mac") { showMac = true }.accessibilityIdentifier("macPairingButton")
                }.listRowBackground(RadarPalette.paper)
            }
        }.scrollContentBackground(.hidden).background(RadarPalette.canvas)
            .navigationTitle("连接设置").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成", action: onClose).accessibilityIdentifier("closeSettingsButton") } }
            .onAppear { baseURL = store.apiConfiguration.baseURL; model = store.apiConfiguration.model }
            .alert("移除这个 Key？", isPresented: $confirmRemove) {
                Button("移除", role: .destructive) { store.removeAPIKey() }
                Button("取消", role: .cancel) {}
            } message: { Text("删除本机 Key，作品保留。") }
            .sheet(isPresented: $showMac) { MacConnectionSheet().environmentObject(store) }
    }
}
