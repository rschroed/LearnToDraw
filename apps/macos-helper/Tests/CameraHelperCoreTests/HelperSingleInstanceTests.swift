import XCTest
@testable import CameraHelperCore

final class HelperSingleInstanceTests: XCTestCase {
    func testReturnsNilWhenNoOtherHelperInstanceExists() {
        let coordinator = HelperSingleInstanceCoordinator(
            bundleIdentifier: "com.learntodraw.CameraHelper",
            runningApplications: MockRunningHelperApps(processIdentifiers: [101]),
            instanceLock: MockHelperInstanceLock(acquireResult: true)
        )

        let existingPID = coordinator.existingInstanceProcessIdentifier(
            currentProcessIdentifier: 101
        )

        XCTAssertNil(existingPID)
    }

    func testActivatesExistingHelperInstanceWhenAnotherProcessIsRunning() {
        let runningApps = MockRunningHelperApps(processIdentifiers: [101, 303])
        let coordinator = HelperSingleInstanceCoordinator(
            bundleIdentifier: "com.learntodraw.CameraHelper",
            runningApplications: runningApps,
            instanceLock: MockHelperInstanceLock(acquireResult: false)
        )

        let activated = coordinator.activateExistingInstanceIfNeeded(
            currentProcessIdentifier: 303
        )

        XCTAssertTrue(activated)
        XCTAssertEqual(runningApps.activatedProcessIdentifier, 101)
    }

    func testIgnoresCurrentProcessAndChoosesExistingHelperOwner() {
        let runningApps = MockRunningHelperApps(processIdentifiers: [450, 900, 1200])
        let coordinator = HelperSingleInstanceCoordinator(
            bundleIdentifier: "com.learntodraw.CameraHelper",
            runningApplications: runningApps,
            instanceLock: MockHelperInstanceLock(acquireResult: true)
        )

        let existingPID = coordinator.existingInstanceProcessIdentifier(
            currentProcessIdentifier: 900
        )

        XCTAssertEqual(existingPID, 450)
    }

    func testPrimaryInstanceAcquiresLockAndDoesNotHandOff() throws {
        let runningApps = MockRunningHelperApps(processIdentifiers: [101])
        let coordinator = HelperSingleInstanceCoordinator(
            bundleIdentifier: "com.learntodraw.CameraHelper",
            runningApplications: runningApps,
            instanceLock: MockHelperInstanceLock(acquireResult: true)
        )

        let handedOff = try coordinator.handOffToExistingInstanceIfNeeded(
            currentProcessIdentifier: 101
        )

        XCTAssertFalse(handedOff)
        XCTAssertNil(runningApps.activatedProcessIdentifier)
    }

    func testSecondaryInstanceHandsOffWhenLockIsAlreadyHeld() throws {
        let runningApps = MockRunningHelperApps(processIdentifiers: [101, 303])
        let coordinator = HelperSingleInstanceCoordinator(
            bundleIdentifier: "com.learntodraw.CameraHelper",
            runningApplications: runningApps,
            instanceLock: MockHelperInstanceLock(acquireResult: false)
        )

        let handedOff = try coordinator.handOffToExistingInstanceIfNeeded(
            currentProcessIdentifier: 303
        )

        XCTAssertTrue(handedOff)
        XCTAssertEqual(runningApps.activatedProcessIdentifier, 101)
    }
}

private final class MockRunningHelperApps: RunningHelperAppQuerying, @unchecked Sendable {
    let processIdentifiers: [Int32]
    private(set) var activatedProcessIdentifier: Int32?

    init(processIdentifiers: [Int32]) {
        self.processIdentifiers = processIdentifiers
    }

    func runningApplications(bundleIdentifier: String) -> [RunningHelperApp] {
        processIdentifiers.map(RunningHelperApp.init(processIdentifier:))
    }

    func activate(processIdentifier: Int32) -> Bool {
        activatedProcessIdentifier = processIdentifier
        return true
    }
}

private struct MockHelperInstanceLock: HelperInstanceLocking {
    let acquireResult: Bool

    func tryAcquire() throws -> Bool {
        acquireResult
    }
}
