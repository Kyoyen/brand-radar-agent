import Foundation
import Security

/// Non-secret settings only. Persist this value separately from AgentAPIKeychain.
struct AgentConnection: Codable, Equatable {
    var provider: String
    var baseURL: String
    var model: String

    func endpointURL() throws -> URL {
        let value = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard var parts = URLComponents(string: value), let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil else {
            throw DirectAgentError.configuration("API 地址不能包含账号、密码、查询参数或片段。")
        }
        let scheme = parts.scheme?.lowercased()
        var allowed = scheme == "https"
        #if DEBUG
        allowed = allowed || (scheme == "http" && ["localhost", "127.0.0.1", "::1", "[::1]"].contains(host.lowercased()))
        #endif
        guard allowed else { throw DirectAgentError.configuration("请填写 HTTPS API 地址。") }
        guard !model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, model.count <= 200 else {
            throw DirectAgentError.configuration("请填写服务商提供的模型名称。")
        }
        var path = parts.path
        while path.hasSuffix("/") { path.removeLast() }
        if !path.hasSuffix("/chat/completions") { path += "/chat/completions" }
        parts.path = path
        guard let url = parts.url else { throw DirectAgentError.configuration("API 地址无法读取。") }
        return url
    }
}

/// An endpoint-specific account prevents a different host silently reusing a saved key.
enum AgentAPIKeychain {
    static let service = "com.keyuanshi.brandradar.direct-agent-api"
    private static func query(for configuration: AgentConnection) throws -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: try configuration.endpointURL().absoluteString]
    }
    static func read(for configuration: AgentConnection) -> String {
        guard var query = try? query(for: configuration) else { return "" }
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess, let data = result as? Data else { return "" }
        return String(data: data, encoding: .utf8) ?? ""
    }
    static func save(_ key: String, for configuration: AgentConnection) throws {
        let clean = try DirectAgent.validatedKey(key)
        let query = try query(for: configuration)
        let data = Data(clean.utf8)
        var status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecItemNotFound {
            let record = query.merging([kSecValueData as String: data,
                                        kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]) { _, new in new }
            status = SecItemAdd(record as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw DirectAgentError.configuration("无法安全保存 API Key，请解锁设备后重试。") }
    }
    static func remove(for configuration: AgentConnection) throws {
        let status = SecItemDelete(try query(for: configuration) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw DirectAgentError.configuration("暂时无法移除 API Key，请重试。")
        }
    }
}
