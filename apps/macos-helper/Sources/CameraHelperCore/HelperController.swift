import Foundation

public actor HelperController {
    private let shutdownTimeoutNanoseconds: UInt64 = 2_000_000_000
    private let launchConfiguration: BackendLaunchConfiguration
    private let launcher: BackendProcessLaunching
    private let healthChecker: HealthChecking
    private let pollIntervalNanoseconds: UInt64
    private let mode = "camera"
    private let helperInstanceID: String
    private let helperLaunchedAt: Date

    private var state: HelperState = .stopped
    private var backendHealth: BackendHealth = .unreachable
    private var managedProcess: ManagedProcess?
    private var startedAt: Date?
    private var lastError: String?
    private var lastExitCode: Int32?
    private var stopRequested = false
    private var startupTask: Task<Void, Never>?

    public init(
        launchConfiguration: BackendLaunchConfiguration,
        launcher: BackendProcessLaunching,
        healthChecker: HealthChecking,
        helperInstanceID: String = UUID().uuidString,
        helperLaunchedAt: Date = Date(),
        pollIntervalNanoseconds: UInt64 = 250_000_000
    ) {
        self.launchConfiguration = launchConfiguration
        self.launcher = launcher
        self.healthChecker = healthChecker
        self.helperInstanceID = helperInstanceID
        self.helperLaunchedAt = helperLaunchedAt
        self.pollIntervalNanoseconds = pollIntervalNanoseconds
    }

    public func status() -> HelperStatus {
        currentStatus()
    }

    public func start() async -> HelperStatus {
        if state == .starting || state == .running {
            HelperLogger.log(instanceID: helperInstanceID, message: "start requested while already \(state.rawValue)")
            return currentStatus()
        }

        if await healthChecker.isHealthy(url: launchConfiguration.backendURL) {
            state = .failed
            backendHealth = .healthy
            lastError = "Backend port 8000 is already healthy outside helper control."
            HelperLogger.log(instanceID: helperInstanceID, message: "backend already healthy outside helper control")
            return currentStatus()
        }

        do {
            HelperLogger.log(instanceID: helperInstanceID, message: "launching backend")
            let process = try launcher.launchBackend(configuration: launchConfiguration)
            stopRequested = false
            managedProcess = process
            startedAt = Date()
            lastError = nil
            lastExitCode = nil
            state = .starting
            backendHealth = .starting

            process.onExit = { [weak self] exit in
                Task {
                    await self?.handleProcessExit(exit)
                }
            }

            startupTask?.cancel()
            startupTask = Task {
                await self.monitorStartup(expectedPID: process.processIdentifier)
            }

            return currentStatus()
        } catch {
            state = .failed
            backendHealth = .unreachable
            lastError = error.localizedDescription
            HelperLogger.log(instanceID: helperInstanceID, message: "backend launch failed: \(error.localizedDescription)")
            return currentStatus()
        }
    }

    public func stop() async -> HelperStatus {
        HelperLogger.log(instanceID: helperInstanceID, message: "stop requested")
        startupTask?.cancel()
        startupTask = nil
        stopRequested = true

        guard let managedProcess else {
            state = .stopped
            backendHealth = .unreachable
            lastError = nil
            HelperLogger.log(instanceID: helperInstanceID, message: "stop requested with no managed backend")
            return currentStatus()
        }

        managedProcess.stop()
        await waitForBackendShutdown(expectedPID: managedProcess.processIdentifier)
        self.managedProcess = nil
        state = .stopped
        backendHealth = .unreachable
        lastError = nil
        HelperLogger.log(instanceID: helperInstanceID, message: "backend stopped")
        return currentStatus()
    }

    public func restart() async -> HelperStatus {
        HelperLogger.log(instanceID: helperInstanceID, message: "restart requested")
        _ = await stop()
        return await start()
    }

    private func monitorStartup(expectedPID: Int32) async {
        while !Task.isCancelled {
            guard managedProcess?.processIdentifier == expectedPID else {
                return
            }

            if await healthChecker.isHealthy(url: launchConfiguration.backendURL) {
                if state == .starting && managedProcess?.processIdentifier == expectedPID {
                    state = .running
                    backendHealth = .healthy
                    HelperLogger.log(instanceID: helperInstanceID, message: "backend became healthy pid=\(expectedPID)")
                }
                return
            }

            if managedProcess?.isRunning != true {
                return
            }

            do {
                try await Task.sleep(nanoseconds: pollIntervalNanoseconds)
            } catch {
                return
            }
        }
    }

    private func waitForBackendShutdown(expectedPID: Int32) async {
        let deadline = DispatchTime.now().uptimeNanoseconds + shutdownTimeoutNanoseconds

        while DispatchTime.now().uptimeNanoseconds < deadline {
            let processStillOwned = managedProcess?.processIdentifier == expectedPID
            let processRunning = managedProcess?.isRunning == true
            let backendStillHealthy = await healthChecker.isHealthy(url: launchConfiguration.backendURL)

            if (!processStillOwned || !processRunning) && !backendStillHealthy {
                return
            }

            do {
                try await Task.sleep(nanoseconds: pollIntervalNanoseconds)
            } catch {
                return
            }
        }
    }

    private func handleProcessExit(_ exit: ManagedProcessExit) {
        startupTask?.cancel()
        startupTask = nil
        managedProcess = nil
        lastExitCode = exit.exitCode
        backendHealth = .unreachable
        HelperLogger.log(
            instanceID: helperInstanceID,
            message: "backend exited code=\(exit.exitCode) stderr=\(exit.stderrTail ?? "none")"
        )

        if stopRequested {
            state = .stopped
            return
        }

        state = .failed
        lastError = exit.stderrTail ?? "Backend exited before becoming healthy."
    }

    private func currentStatus() -> HelperStatus {
        HelperStatus(
            helperInstanceID: helperInstanceID,
            helperLaunchedAt: helperLaunchedAt,
            state: state,
            backendHealth: backendHealth,
            mode: mode,
            backendURL: launchConfiguration.backendURL.absoluteString,
            managedPID: managedProcess?.processIdentifier,
            startedAt: startedAt,
            lastError: lastError,
            lastExitCode: lastExitCode
        )
    }
}
