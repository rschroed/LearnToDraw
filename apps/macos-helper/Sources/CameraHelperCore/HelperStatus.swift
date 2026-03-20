import Foundation

public enum HelperState: String, Codable, Equatable, Sendable {
    case stopped
    case starting
    case running
    case failed
}

public enum BackendHealth: String, Codable, Equatable, Sendable {
    case unreachable
    case starting
    case healthy
}

public struct HelperStatus: Equatable, Sendable {
    public let helperInstanceID: String
    public let helperLaunchedAt: Date
    public let state: HelperState
    public let backendHealth: BackendHealth
    public let mode: String
    public let backendURL: String
    public let managedPID: Int32?
    public let startedAt: Date?
    public let lastError: String?
    public let lastExitCode: Int32?

    public init(
        helperInstanceID: String,
        helperLaunchedAt: Date,
        state: HelperState,
        backendHealth: BackendHealth,
        mode: String,
        backendURL: String,
        managedPID: Int32?,
        startedAt: Date?,
        lastError: String?,
        lastExitCode: Int32?
    ) {
        self.helperInstanceID = helperInstanceID
        self.helperLaunchedAt = helperLaunchedAt
        self.state = state
        self.backendHealth = backendHealth
        self.mode = mode
        self.backendURL = backendURL
        self.managedPID = managedPID
        self.startedAt = startedAt
        self.lastError = lastError
        self.lastExitCode = lastExitCode
    }

    enum CodingKeys: String, CodingKey {
        case helperInstanceID = "helper_instance_id"
        case helperLaunchedAt = "helper_launched_at"
        case state
        case backendHealth = "backend_health"
        case mode
        case backendURL = "backend_url"
        case managedPID = "managed_pid"
        case startedAt = "started_at"
        case lastError = "last_error"
        case lastExitCode = "last_exit_code"
    }
}

extension HelperStatus: Encodable {
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(helperInstanceID, forKey: .helperInstanceID)
        try container.encode(helperLaunchedAt, forKey: .helperLaunchedAt)
        try container.encode(state, forKey: .state)
        try container.encode(backendHealth, forKey: .backendHealth)
        try container.encode(mode, forKey: .mode)
        try container.encode(backendURL, forKey: .backendURL)
        try container.encode(managedPID, forKey: .managedPID)
        try container.encode(startedAt, forKey: .startedAt)
        try container.encode(lastError, forKey: .lastError)
        try container.encode(lastExitCode, forKey: .lastExitCode)
    }
}

extension HelperStatus: Decodable {}
