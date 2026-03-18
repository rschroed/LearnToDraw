import AppKit
import CameraHelperCore

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var helperServer: LocalHTTPServer?
    private var statusItem: NSStatusItem?
    private let controller: HelperController

    override init() {
        let launchConfiguration: BackendLaunchConfiguration
        do {
            launchConfiguration = try BackendLaunchConfiguration.live()
        } catch {
            fatalError(error.localizedDescription)
        }

        self.controller = HelperController(
            launchConfiguration: launchConfiguration,
            launcher: FoundationBackendProcessLauncher(),
            healthChecker: URLSessionHealthChecker()
        )
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        installStatusItem()

        let server = LocalHTTPServer(controller: controller)
        do {
            try server.start()
            helperServer = server
        } catch {
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
