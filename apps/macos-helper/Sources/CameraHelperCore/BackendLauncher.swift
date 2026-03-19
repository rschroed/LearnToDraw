import Foundation

public struct PackagedHelperConfiguration: Codable, Equatable, Sendable {
    public let repoRoot: String
    public let backendHost: String
    public let backendPort: UInt16
    public let helperHost: String
    public let helperPort: UInt16

    public init(
        repoRoot: String,
        backendHost: String,
        backendPort: UInt16,
        helperHost: String,
        helperPort: UInt16
    ) {
        self.repoRoot = repoRoot
        self.backendHost = backendHost
        self.backendPort = backendPort
        self.helperHost = helperHost
        self.helperPort = helperPort
    }
}

public enum PackagedHelperConfigurationLoader {
    public static let fileName = "LearnToDrawHelperConfig"
    public static let fileExtension = "json"

    public static func load(
        bundle: Bundle = .main,
        fileManager: FileManager = .default
    ) throws -> PackagedHelperConfiguration? {
        try load(resourceDirectoryURL: bundle.resourceURL, fileManager: fileManager)
    }

    static func load(
        resourceDirectoryURL: URL?,
        fileManager: FileManager = .default
    ) throws -> PackagedHelperConfiguration? {
        guard let resourceDirectoryURL else {
            return nil
        }

        let configURL = resourceDirectoryURL.appending(
            path: "\(fileName).\(fileExtension)",
            directoryHint: .notDirectory
        )
        guard fileManager.fileExists(atPath: configURL.path) else {
            return nil
        }

        let data = try Data(contentsOf: configURL)
        let configuration = try JSONDecoder().decode(PackagedHelperConfiguration.self, from: data)
        let repoRootURL = URL(fileURLWithPath: configuration.repoRoot, isDirectory: true)

        guard RepoRootLocator.isRepositoryRoot(at: repoRootURL, fileManager: fileManager) else {
            throw NSError(
                domain: "LearnToDrawCameraHelper",
                code: 2,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "Packaged helper config points to an invalid LearnToDraw repository root: \(configuration.repoRoot)",
                ]
            )
        }

        return configuration
    }
}

public struct HelperRuntimeConfiguration: Sendable {
    public let launchConfiguration: BackendLaunchConfiguration
    public let helperHost: String
    public let helperPort: UInt16

    public init(
        launchConfiguration: BackendLaunchConfiguration,
        helperHost: String,
        helperPort: UInt16
    ) {
        self.launchConfiguration = launchConfiguration
        self.helperHost = helperHost
        self.helperPort = helperPort
    }

    public static func live(
        bundle: Bundle = .main,
        fileManager: FileManager = .default,
        environment: [String: String] = ProcessInfo.processInfo.environment,
        executablePath: String = CommandLine.arguments[0]
    ) throws -> HelperRuntimeConfiguration {
        try live(
            resourceDirectoryURL: bundle.resourceURL,
            fileManager: fileManager,
            environment: environment,
            executablePath: executablePath
        )
    }

    static func live(
        resourceDirectoryURL: URL?,
        fileManager: FileManager = .default,
        environment: [String: String] = ProcessInfo.processInfo.environment,
        executablePath: String = CommandLine.arguments[0]
    ) throws -> HelperRuntimeConfiguration {
        if let packagedConfiguration = try PackagedHelperConfigurationLoader.load(
            resourceDirectoryURL: resourceDirectoryURL,
            fileManager: fileManager
        ) {
            return try make(
                repoRoot: URL(fileURLWithPath: packagedConfiguration.repoRoot, isDirectory: true),
                backendHost: packagedConfiguration.backendHost,
                backendPort: packagedConfiguration.backendPort,
                helperHost: packagedConfiguration.helperHost,
                helperPort: packagedConfiguration.helperPort,
                environment: environment,
                fileManager: fileManager
            )
        }

        let repoRoot = try RepoRootLocator.locate(
            fileManager: fileManager,
            executablePath: executablePath
        )
        return try make(
            repoRoot: repoRoot,
            backendHost: "127.0.0.1",
            backendPort: 8000,
            helperHost: "127.0.0.1",
            helperPort: 8001,
            environment: environment,
            fileManager: fileManager
        )
    }

    private static func make(
        repoRoot: URL,
        backendHost: String,
        backendPort: UInt16,
        helperHost: String,
        helperPort: UInt16,
        environment: [String: String],
        fileManager: FileManager
    ) throws -> HelperRuntimeConfiguration {
        guard RepoRootLocator.isRepositoryRoot(at: repoRoot, fileManager: fileManager) else {
            throw NSError(
                domain: "LearnToDrawCameraHelper",
                code: 3,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "Could not find the LearnToDraw repository at \(repoRoot.path).",
                ]
            )
        }

        let apiDirectory = repoRoot.appending(path: "apps/api", directoryHint: .isDirectory)
        let backendURL = URL(string: "http://\(backendHost):\(backendPort)")!
        var launchEnvironment = environment
        launchEnvironment["PYTHONPATH"] = "src"
        launchEnvironment["LEARN_TO_DRAW_PLOTTER_DRIVER"] = "mock"
        launchEnvironment["LEARN_TO_DRAW_CAMERA_DRIVER"] = "opencv"

        let forwardedKeys = [
            "LEARN_TO_DRAW_OPENCV_CAMERA_INDEX",
            "LEARN_TO_DRAW_CAMERA_WARMUP_MS",
            "LEARN_TO_DRAW_CAMERA_DISCARD_FRAMES",
        ]
        for key in forwardedKeys where environment[key] == nil {
            launchEnvironment.removeValue(forKey: key)
        }

        return HelperRuntimeConfiguration(
            launchConfiguration: BackendLaunchConfiguration(
                executableURL: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: [
                    "python3",
                    "-m",
                    "uvicorn",
                    "learn_to_draw_api.main:app",
                    "--host",
                    backendHost,
                    "--port",
                    String(backendPort),
                ],
                workingDirectoryURL: apiDirectory,
                environment: launchEnvironment,
                backendURL: backendURL
            ),
            helperHost: helperHost,
            helperPort: helperPort
        )
    }
}

public struct BackendLaunchConfiguration: Sendable {
    public let executableURL: URL
    public let arguments: [String]
    public let workingDirectoryURL: URL
    public let environment: [String: String]
    public let backendURL: URL

    public init(
        executableURL: URL,
        arguments: [String],
        workingDirectoryURL: URL,
        environment: [String: String],
        backendURL: URL
    ) {
        self.executableURL = executableURL
        self.arguments = arguments
        self.workingDirectoryURL = workingDirectoryURL
        self.environment = environment
        self.backendURL = backendURL
    }

    public static func live(
        bundle: Bundle = .main,
        fileManager: FileManager = .default,
        environment: [String: String] = ProcessInfo.processInfo.environment,
        executablePath: String = CommandLine.arguments[0]
    ) throws -> BackendLaunchConfiguration {
        try HelperRuntimeConfiguration.live(
            bundle: bundle,
            fileManager: fileManager,
            environment: environment,
            executablePath: executablePath
        ).launchConfiguration
    }
}

public enum RepoRootLocator {
    public static func locate(
        fileManager: FileManager = .default,
        executablePath: String = CommandLine.arguments[0]
    ) throws -> URL {
        let candidates = [
            URL(fileURLWithPath: executablePath).resolvingSymlinksInPath(),
            URL(fileURLWithPath: fileManager.currentDirectoryPath, isDirectory: true),
        ]

        for candidate in candidates {
            for directory in ancestorDirectories(of: candidate) {
                if isRepositoryRoot(at: directory, fileManager: fileManager) {
                    return directory
                }
            }
        }

        throw NSError(
            domain: "LearnToDrawCameraHelper",
            code: 1,
            userInfo: [
                NSLocalizedDescriptionKey:
                    "Could not locate the LearnToDraw repository root from the helper executable.",
            ]
        )
    }

    private static func ancestorDirectories(of url: URL) -> [URL] {
        var result: [URL] = []
        let seed = url.hasDirectoryPath ? url : url.deletingLastPathComponent()
        var current = seed.standardizedFileURL

        while true {
            result.append(current)
            let parent = current.deletingLastPathComponent()
            if parent.path == current.path {
                break
            }
            current = parent
        }

        return result
    }

    static func isRepositoryRoot(at url: URL, fileManager: FileManager) -> Bool {
        let apiProject = url.appending(path: "apps/api/pyproject.toml")
        let webProject = url.appending(path: "apps/web/package.json")
        return fileManager.fileExists(atPath: apiProject.path)
            && fileManager.fileExists(atPath: webProject.path)
    }
}

public struct ManagedProcessExit: Sendable, Equatable {
    public let exitCode: Int32
    public let stderrTail: String?

    public init(exitCode: Int32, stderrTail: String?) {
        self.exitCode = exitCode
        self.stderrTail = stderrTail
    }
}

public protocol ManagedProcess: AnyObject, Sendable {
    var processIdentifier: Int32 { get }
    var isRunning: Bool { get }
    var onExit: (@Sendable (ManagedProcessExit) -> Void)? { get set }
    func stop()
}

public protocol BackendProcessLaunching: Sendable {
    func launchBackend(configuration: BackendLaunchConfiguration) throws -> ManagedProcess
}

public final class FoundationBackendProcessLauncher: BackendProcessLaunching {
    public init() {}

    public func launchBackend(configuration: BackendLaunchConfiguration) throws -> ManagedProcess {
        let process = Process()
        process.executableURL = configuration.executableURL
        process.arguments = configuration.arguments
        process.currentDirectoryURL = configuration.workingDirectoryURL
        process.environment = configuration.environment

        let stderr = Pipe()
        process.standardOutput = FileHandle.nullDevice
        process.standardError = stderr

        let managed = FoundationManagedProcess(process: process, stderrHandle: stderr.fileHandleForReading)
        try process.run()
        managed.bindTerminationHandler()
        return managed
    }
}

public protocol HealthChecking: Sendable {
    func isHealthy(url: URL) async -> Bool
}

public final class URLSessionHealthChecker: HealthChecking {
    private let session: URLSession

    public init() {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 0.5
        configuration.timeoutIntervalForResource = 0.5
        self.session = URLSession(configuration: configuration)
    }

    public func isHealthy(url: URL) async -> Bool {
        let healthURL = url.appending(path: "/api/health")
        var request = URLRequest(url: healthURL)
        request.httpMethod = "GET"

        do {
            let (_, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                return false
            }
            return httpResponse.statusCode == 200
        } catch {
            return false
        }
    }
}

final class FoundationManagedProcess: ManagedProcess, @unchecked Sendable {
    private let process: Process
    private let stderrHandle: FileHandle
    private let bufferQueue = DispatchQueue(label: "learn-to-draw.camera-helper.stderr")
    private let maxTailBytes = 8192
    private var stderrBuffer = Data()

    var onExit: (@Sendable (ManagedProcessExit) -> Void)?

    init(process: Process, stderrHandle: FileHandle) {
        self.process = process
        self.stderrHandle = stderrHandle
        self.stderrHandle.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else {
                return
            }
            self?.appendStderr(data)
        }
    }

    var processIdentifier: Int32 {
        process.processIdentifier
    }

    var isRunning: Bool {
        process.isRunning
    }

    func bindTerminationHandler() {
        process.terminationHandler = { [weak self] _ in
            guard let self else {
                return
            }
            self.stderrHandle.readabilityHandler = nil
            let exit = ManagedProcessExit(
                exitCode: self.process.terminationStatus,
                stderrTail: self.stderrTail()
            )
            self.onExit?(exit)
        }
    }

    func stop() {
        guard process.isRunning else {
            return
        }
        process.terminate()
    }

    private func appendStderr(_ data: Data) {
        bufferQueue.sync {
            stderrBuffer.append(data)
            if stderrBuffer.count > maxTailBytes {
                stderrBuffer.removeFirst(stderrBuffer.count - maxTailBytes)
            }
        }
    }

    private func stderrTail() -> String? {
        bufferQueue.sync {
            guard !stderrBuffer.isEmpty else {
                return nil
            }
            let text = String(decoding: stderrBuffer, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            return text.isEmpty ? nil : text
        }
    }
}
