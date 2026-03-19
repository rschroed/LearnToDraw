import Foundation

public actor HelperController {
    private let shutdownTimeoutNanoseconds: UInt64 = 2_000_000_000
    private let launchConfiguration: BackendLaunchConfiguration
    private let launcher: BackendProcessLaunching
    private let healthChecker: HealthChecking
    private let pollIntervalNanoseconds: UInt64
    private let mode = "camera"

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
        pollIntervalNanoseconds: UInt64 = 250_000_000
    ) {
        self.launchConfiguration = launchConfiguration
        self.launcher = launcher
        self.healthChecker = healthChecker
        self.pollIntervalNanoseconds = pollIntervalNanoseconds
    }

    public func status() -> HelperStatus {
        currentStatus()
    }

    public func start() async -> HelperStatus {
        if state == .starting || state == .running {
            return currentStatus()
        }

        if await healthChecker.isHealthy(url: launchConfiguration.backendURL) {
            state = .failed
            backendHealth = .healthy
            lastError = "Backend port 8000 is already healthy outside helper control."
            return currentStatus()
        }

        do {
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
            return currentStatus()
        }
    }

    public func stop() async -> HelperStatus {
        startupTask?.cancel()
        startupTask = nil
        stopRequested = true

        guard let managedProcess else {
            state = .stopped
            backendHealth = .unreachable
            lastError = nil
            return currentStatus()
        }

        managedProcess.stop()
        await waitForBackendShutdown(expectedPID: managedProcess.processIdentifier)
        self.managedProcess = nil
        state = .stopped
        backendHealth = .unreachable
        lastError = nil
        return currentStatus()
    }

    public func restart() async -> HelperStatus {
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

        if stopRequested {
            state = .stopped
            return
        }

        state = .failed
        lastError = exit.stderrTail ?? "Backend exited before becoming healthy."
    }

    private func currentStatus() -> HelperStatus {
        HelperStatus(
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
