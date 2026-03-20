import AppKit
import Darwin
import Foundation

public struct RunningHelperApp: Equatable, Sendable {
    public let processIdentifier: Int32

    public init(processIdentifier: Int32) {
        self.processIdentifier = processIdentifier
    }
}

public protocol RunningHelperAppQuerying: Sendable {
    func runningApplications(bundleIdentifier: String) -> [RunningHelperApp]
    @discardableResult
    func activate(processIdentifier: Int32) -> Bool
}

public protocol HelperInstanceLocking: Sendable {
    func tryAcquire() throws -> Bool
}

public struct AppKitRunningHelperApps: RunningHelperAppQuerying {
    public init() {}

    public func runningApplications(bundleIdentifier: String) -> [RunningHelperApp] {
        NSRunningApplication.runningApplications(withBundleIdentifier: bundleIdentifier).map {
            RunningHelperApp(processIdentifier: $0.processIdentifier)
        }
    }

    @discardableResult
    public func activate(processIdentifier: Int32) -> Bool {
        guard
            let application = NSRunningApplication.runningApplications(
                withBundleIdentifier: Bundle.main.bundleIdentifier ?? ""
            ).first(where: { $0.processIdentifier == processIdentifier })
        else {
            return false
        }

        return application.activate(options: [.activateIgnoringOtherApps])
    }
}

public final class HelperInstanceLock: HelperInstanceLocking, @unchecked Sendable {
    private let lockFileURL: URL
    private var fileDescriptor: Int32 = -1

    public init(lockFileURL: URL) {
        self.lockFileURL = lockFileURL
    }

    deinit {
        if fileDescriptor >= 0 {
            close(fileDescriptor)
        }
    }

    public func tryAcquire() throws -> Bool {
        if fileDescriptor >= 0 {
            return true
        }

        let descriptor = open(lockFileURL.path, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else {
            throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
        }

        if flock(descriptor, LOCK_EX | LOCK_NB) != 0 {
            let lockError = errno
            close(descriptor)
            if lockError == EWOULDBLOCK {
                return false
            }
            throw POSIXError(POSIXErrorCode(rawValue: lockError) ?? .EIO)
        }

        fileDescriptor = descriptor
        return true
    }
}

public struct HelperSingleInstanceCoordinator: Sendable {
    private let bundleIdentifier: String
    private let runningApplications: RunningHelperAppQuerying
    private let instanceLock: HelperInstanceLocking

    public init(
        bundleIdentifier: String,
        runningApplications: RunningHelperAppQuerying = AppKitRunningHelperApps(),
        instanceLock: HelperInstanceLocking? = nil
    ) {
        self.bundleIdentifier = bundleIdentifier
        self.runningApplications = runningApplications
        self.instanceLock = instanceLock ?? HelperInstanceLock(
            lockFileURL: FileManager.default.temporaryDirectory
                .appendingPathComponent("\(bundleIdentifier).lock")
        )
    }

    public func existingInstanceProcessIdentifier(currentProcessIdentifier: Int32) -> Int32? {
        runningApplications
            .runningApplications(bundleIdentifier: bundleIdentifier)
            .map(\.processIdentifier)
            .sorted()
            .first(where: { $0 != currentProcessIdentifier })
    }

    @discardableResult
    public func activateExistingInstanceIfNeeded(currentProcessIdentifier: Int32) -> Bool {
        guard let existingPID = existingInstanceProcessIdentifier(
            currentProcessIdentifier: currentProcessIdentifier
        ) else {
            return false
        }

        _ = runningApplications.activate(processIdentifier: existingPID)
        return true
    }

    @discardableResult
    public func handOffToExistingInstanceIfNeeded(currentProcessIdentifier: Int32) throws -> Bool {
        guard try !instanceLock.tryAcquire() else {
            return false
        }

        _ = activateExistingInstanceIfNeeded(currentProcessIdentifier: currentProcessIdentifier)
        return true
    }
}
