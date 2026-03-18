import Foundation
import XCTest
@testable import CameraHelperCore

final class HelperControllerTests: XCTestCase {
    func testStatusIsStoppedBeforeStart() async {
        let controller = makeController()

        let status = await controller.status()

        XCTAssertEqual(status.state, .stopped)
        XCTAssertEqual(status.backendHealth, .unreachable)
        XCTAssertNil(status.managedPID)
    }

    func testStartMovesToStartingImmediately() async {
        let launcher = MockLauncher()
        let controller = makeController(launcher: launcher, healthChecker: MockHealthChecker(results: [false]))

        let status = await controller.start()

        XCTAssertEqual(status.state, .starting)
        XCTAssertEqual(status.backendHealth, .starting)
        XCTAssertEqual(status.managedPID, 4242)
    }

    func testHealthyBackendTransitionsToRunning() async {
        let launcher = MockLauncher()
        let healthChecker = MockHealthChecker(results: [false, false, true])
        let controller = makeController(
            launcher: launcher,
            healthChecker: healthChecker,
            pollIntervalNanoseconds: 1_000_000
        )

        _ = await controller.start()
        try? await Task.sleep(nanoseconds: 20_000_000)
        let status = await controller.status()

        XCTAssertEqual(status.state, .running)
        XCTAssertEqual(status.backendHealth, .healthy)
    }

    func testFailedStartupTransitionsToFailedWithStderr() async {
        let launcher = MockLauncher()
        let healthChecker = MockHealthChecker(results: [false, false, false, false])
        let controller = makeController(
            launcher: launcher,
            healthChecker: healthChecker,
            pollIntervalNanoseconds: 1_000_000
        )

        _ = await controller.start()
        launcher.process.emitExit(code: 1, stderr: "camera init failed")
        try? await Task.sleep(nanoseconds: 10_000_000)
        let status = await controller.status()

        XCTAssertEqual(status.state, .failed)
        XCTAssertEqual(status.backendHealth, .unreachable)
        XCTAssertEqual(status.lastExitCode, 1)
        XCTAssertEqual(status.lastError, "camera init failed")
    }

    func testRepeatedStartIsIdempotent() async {
        let launcher = MockLauncher()
        let controller = makeController(
            launcher: launcher,
            healthChecker: MockHealthChecker(results: [false, false])
        )

        let first = await controller.start()
        let second = await controller.start()

        XCTAssertEqual(first.managedPID, second.managedPID)
        XCTAssertEqual(launcher.launchCount, 1)
    }

    func testStopReturnsToStoppedAndStopsManagedProcess() async {
        let launcher = MockLauncher()
        let controller = makeController(
            launcher: launcher,
            healthChecker: MockHealthChecker(results: [false, false])
        )

        _ = await controller.start()
        let status = await controller.stop()

        XCTAssertEqual(status.state, .stopped)
        XCTAssertEqual(status.backendHealth, .unreachable)
        XCTAssertTrue(launcher.process.stopCalled)
    }

    private func makeController(
        launcher: MockLauncher = MockLauncher(),
        healthChecker: MockHealthChecker = MockHealthChecker(results: []),
        pollIntervalNanoseconds: UInt64 = 1_000_000
    ) -> HelperController {
        HelperController(
            launchConfiguration: BackendLaunchConfiguration(
                executableURL: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: ["python3"],
                workingDirectoryURL: URL(fileURLWithPath: "/tmp", isDirectory: true),
                environment: [:],
                backendURL: URL(string: "http://127.0.0.1:8000")!
            ),
            launcher: launcher,
            healthChecker: healthChecker,
            pollIntervalNanoseconds: pollIntervalNanoseconds
        )
    }
}

private final class MockLauncher: BackendProcessLaunching, @unchecked Sendable {
    let process = MockManagedProcess()
    private let queue = DispatchQueue(label: "mock-launcher")
    private var _launchCount = 0

    var launchCount: Int {
        queue.sync { _launchCount }
    }

    func launchBackend(configuration: BackendLaunchConfiguration) throws -> ManagedProcess {
        queue.sync {
            _launchCount += 1
        }
        return process
    }
}

private final class MockHealthChecker: HealthChecking, @unchecked Sendable {
    private let queue = DispatchQueue(label: "mock-health-checker")
    private var results: [Bool]

    init(results: [Bool]) {
        self.results = results
    }

    func isHealthy(url: URL) async -> Bool {
        queue.sync {
            if results.isEmpty {
                return false
            }
            return results.removeFirst()
        }
    }
}

private final class MockManagedProcess: ManagedProcess, @unchecked Sendable {
    var processIdentifier: Int32 = 4242
    var isRunning: Bool = true
    var onExit: (@Sendable (ManagedProcessExit) -> Void)?
    private(set) var stopCalled = false

    func stop() {
        stopCalled = true
        isRunning = false
    }

    func emitExit(code: Int32, stderr: String?) {
        isRunning = false
        onExit?(ManagedProcessExit(exitCode: code, stderrTail: stderr))
    }
}
