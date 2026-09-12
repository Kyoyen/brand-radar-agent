import Foundation

/// Deployment-only handoff inside this app's sandbox. The key never enters the
/// application binary, a URL, launch arguments, or a shared configuration file.
struct PersonalConnection: Decodable {
    let configuration: AgentConnection
    let apiKey: String

    static var inbox: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("AgentSetup.json")
    }

    static func read() throws -> PersonalConnection? {
        let url = inbox
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        var protected = url
        var values = URLResourceValues(); values.isExcludedFromBackup = true
        try protected.setResourceValues(values)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: url.path)
        let data = try Data(contentsOf: url)
        guard data.count < 16000 else { throw DirectAgentError.configuration("连接配置无法读取。") }
        let setup = try JSONDecoder().decode(Self.self, from: data)
        let endpoint = try setup.configuration.endpointURL()
        guard endpoint.scheme == "https", endpoint.host == "api.deepseek.com",
              endpoint.path == "/v1/chat/completions" else {
            throw DirectAgentError.configuration("这份个人配置不是 DeepSeek 连接。")
        }
        _ = try DirectAgent.validatedKey(setup.apiKey)
        return setup
    }

    static func finish(configuration: AgentConnection) throws {
        try FileManager.default.removeItem(at: inbox)
        let receipt: [String: Any] = ["configured": true, "provider": "DeepSeek", "model": configuration.model,
                                     "keyStoredInKeychain": true, "inboxRemoved": true]
        try JSONSerialization.data(withJSONObject: receipt).write(
            to: inbox.deletingLastPathComponent().appendingPathComponent("AgentSetupReceipt.json"), options: .atomic)
    }
}
