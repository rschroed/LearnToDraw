import AppKit
import CameraHelperCore
import Darwin

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var helperServer: LocalHTTPServer?
    private var statusItem: NSStatusItem?
    private let controller: HelperController
    private let runtimeConfiguration: HelperRuntimeConfiguration
    private let helperInstanceID: String
    private let singleInstanceCoordinator: HelperSingleInstanceCoordinator

    override init() {
        let runtimeConfiguration: HelperRuntimeConfiguration
        do {
            runtimeConfiguration = try HelperRuntimeConfiguration.live()
        } catch {
            fatalError(error.localizedDescription)
        }

        self.runtimeConfiguration = runtimeConfiguration
        self.helperInstanceID = UUID().uuidString
        self.singleInstanceCoordinator = HelperSingleInstanceCoordinator(
            bundleIdentifier: Bundle.main.bundleIdentifier ?? "com.learntodraw.CameraHelper"
        )
        self.controller = HelperController(
            launchConfiguration: runtimeConfiguration.launchConfiguration,
            launcher: FoundationBackendProcessLauncher(),
            healthChecker: URLSessionHealthChecker(),
            helperInstanceID: helperInstanceID
        )
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if handOffToExistingInstanceIfNeeded(reason: "launch") {
            return
        }
        installStatusItem()
        ensureHelperServerStarted()
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        let shouldHandle = urls.contains { $0.scheme == "learntodraw-helper" }
        guard shouldHandle else {
            return
        }

        if handOffToExistingInstanceIfNeeded(reason: "url-open") {
            return
        }

        NSApp.activate(ignoringOtherApps: true)
        ensureHelperServerStarted()
    }

    private func handOffToExistingInstanceIfNeeded(reason: String) -> Bool {
        let currentPID = Int32(ProcessInfo.processInfo.processIdentifier)
        let shouldExit: Bool
        do {
            shouldExit = try singleInstanceCoordinator.handOffToExistingInstanceIfNeeded(
                currentProcessIdentifier: currentPID
            )
        } catch {
            HelperLogger.log(
                instanceID: helperInstanceID,
                message: "failed to evaluate single-instance handoff during \(reason): \(error.localizedDescription)"
            )
            return false
        }

        guard shouldExit else {
            return false
        }

        HelperLogger.log(
            instanceID: helperInstanceID,
            message: "detected existing helper instance during \(reason); handing off and exiting"
        )
        fflush(stderr)
        exit(EXIT_SUCCESS)
    }

    private func ensureHelperServerStarted() {
        guard helperServer == nil else {
            return
        }

        let server = LocalHTTPServer(
            controller: controller,
            helperInstanceID: helperInstanceID,
            host: runtimeConfiguration.helperHost,
            port: runtimeConfiguration.helperPort
        )
        do {
            try server.start()
            helperServer = server
            HelperLogger.log(instanceID: helperInstanceID, message: "helper app ready")
        } catch {
            HelperLogger.log(instanceID: helperInstanceID, message: "helper app failed to start: \(error.localizedDescription)")
            let alert = NSAlert()
            alert.messageText = "LearnToDraw helper failed to start"
            alert.informativeText = error.localizedDescription
            alert.runModal()
            NSApp.terminate(nil)
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        helperServer?.stop()
        let semaphore = DispatchSemaphore(value: 0)
        Task {
            _ = await controller.stop()
            semaphore.signal()
        }
        _ = semaphore.wait(timeout: .now() + 1)
    }

    @objc private func startBackend() {
        Task {
            _ = await controller.start()
        }
    }

    @objc private func stopBackend() {
        Task {
            _ = await controller.stop()
        }
    }

    @objc private func terminateApp() {
        NSApp.terminate(nil)
    }

    private func installStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "LTD Helper"

        let menu = NSMenu()
        let startItem = NSMenuItem(
            title: "Start Backend",
            action: #selector(startBackend),
            keyEquivalent: ""
        )
        startItem.target = self
        menu.addItem(startItem)

        let stopItem = NSMenuItem(
            title: "Stop Backend",
            action: #selector(stopBackend),
            keyEquivalent: ""
        )
        stopItem.target = self
        menu.addItem(stopItem)

        menu.addItem(.separator())

        let quitItem = NSMenuItem(
            title: "Quit",
            action: #selector(terminateApp),
            keyEquivalent: "q"
        )
        quitItem.target = self
        menu.addItem(quitItem)

        item.menu = menu
        statusItem = item
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
