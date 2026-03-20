import Foundation
import XCTest
@testable import CameraHelperCore

final class HelperRuntimeConfigurationTests: XCTestCase {
    func testPackagedConfigUsesEmbeddedRepoRootWhenPresent() throws {
        let fixture = try makeFixture()
        defer { try? fixture.cleanup() }

        let configuration = try HelperRuntimeConfiguration.live(
            resourceDirectoryURL: fixture.resourcesDirectory,
            fileManager: .default,
            environment: [:],
            executablePath: "/tmp/not-used/LearnToDrawCameraHelper"
        )

        XCTAssertEqual(
            configuration.launchConfiguration.workingDirectoryURL.path,
            fixture.repoRoot.appending(path: "apps/api").path
        )
        XCTAssertEqual(configuration.launchConfiguration.backendURL.absoluteString, "http://127.0.0.1:8000")
        XCTAssertEqual(configuration.helperHost, "127.0.0.1")
        XCTAssertEqual(configuration.helperPort, 8001)
        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_CAMERA_DRIVER"],
            "opencv"
        )
        XCTAssertNil(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_PLOTTER_DRIVER"]
        )
    }

    func testFallsBackToRepoDiscoveryForSwiftRunExecution() throws {
        let fixture = try makeFixture(includePackagedConfig: false)
        defer { try? fixture.cleanup() }

        let executablePath = fixture.repoRoot
            .appending(path: "apps/macos-helper/.build/debug/LearnToDrawCameraHelper")
            .path

        let configuration = try HelperRuntimeConfiguration.live(
            resourceDirectoryURL: nil,
            fileManager: .default,
            environment: [:],
            executablePath: executablePath
        )

        XCTAssertEqual(
            configuration.launchConfiguration.workingDirectoryURL.path,
            fixture.repoRoot.appending(path: "apps/api").path
        )
        XCTAssertEqual(configuration.helperHost, "127.0.0.1")
        XCTAssertEqual(configuration.helperPort, 8001)
        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_CAMERA_DRIVER"],
            "opencv"
        )
        XCTAssertNil(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_PLOTTER_DRIVER"]
        )
    }

    func testInvalidPackagedRepoRootFailsClearly() throws {
        let fixture = try makeFixture(includeRepositoryShape: false)
        defer { try? fixture.cleanup() }

        XCTAssertThrowsError(
            try HelperRuntimeConfiguration.live(
                resourceDirectoryURL: fixture.resourcesDirectory,
                fileManager: .default,
                environment: [:],
                executablePath: "/tmp/not-used/LearnToDrawCameraHelper"
            )
        ) { error in
            let message = (error as NSError).localizedDescription
            XCTAssertTrue(message.contains("invalid LearnToDraw repository root"))
        }
    }

    func testHelperPreservesUnrelatedEnvironmentWithoutInjectingPlotterConfig() throws {
        let fixture = try makeFixture()
        defer { try? fixture.cleanup() }

        let configuration = try HelperRuntimeConfiguration.live(
            resourceDirectoryURL: fixture.resourcesDirectory,
            fileManager: .default,
            environment: [
                "LEARN_TO_DRAW_PLOTTER_DRIVER": "axidraw",
                "UNRELATED_ENV": "keep-me",
            ],
            executablePath: "/tmp/not-used/LearnToDrawCameraHelper"
        )

        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_CAMERA_DRIVER"],
            "opencv"
        )
        XCTAssertEqual(
            configuration.launchConfiguration.environment["UNRELATED_ENV"],
            "keep-me"
        )
        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_PLOTTER_DRIVER"],
            "axidraw"
        )
    }

    func testHelperForwardsCameraSettingsOnly() throws {
        let fixture = try makeFixture()
        defer { try? fixture.cleanup() }

        let configuration = try HelperRuntimeConfiguration.live(
            resourceDirectoryURL: fixture.resourcesDirectory,
            fileManager: .default,
            environment: [
                "LEARN_TO_DRAW_OPENCV_CAMERA_INDEX": "2",
                "LEARN_TO_DRAW_CAMERA_WARMUP_MS": "500",
                "LEARN_TO_DRAW_CAMERA_DISCARD_FRAMES": "4",
                "LEARN_TO_DRAW_AXIDRAW_MODEL": "1",
            ],
            executablePath: "/tmp/not-used/LearnToDrawCameraHelper"
        )

        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_OPENCV_CAMERA_INDEX"],
            "2"
        )
        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_CAMERA_WARMUP_MS"],
            "500"
        )
        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_CAMERA_DISCARD_FRAMES"],
            "4"
        )
        XCTAssertEqual(
            configuration.launchConfiguration.environment["LEARN_TO_DRAW_AXIDRAW_MODEL"],
            "1"
        )
    }

    private func makeFixture(
        includeRepositoryShape: Bool = true,
        includePackagedConfig: Bool = true
    ) throws -> Fixture {
        let fileManager = FileManager.default
        let root = fileManager.temporaryDirectory.appending(path: UUID().uuidString, directoryHint: .isDirectory)
        let repoRoot = root.appending(path: "LearnToDraw", directoryHint: .isDirectory)
        let resourcesDirectory = root.appending(path: "Resources", directoryHint: .isDirectory)

        try fileManager.createDirectory(at: repoRoot, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: resourcesDirectory, withIntermediateDirectories: true)

        if includeRepositoryShape {
            let apiProject = repoRoot.appending(path: "apps/api/pyproject.toml")
            let webProject = repoRoot.appending(path: "apps/web/package.json")
            try fileManager.createDirectory(
                at: apiProject.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try fileManager.createDirectory(
                at: webProject.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try Data("".utf8).write(to: apiProject)
            try Data("{}".utf8).write(to: webProject)
        }

        if includePackagedConfig {
            let config = PackagedHelperConfiguration(
                repoRoot: repoRoot.path,
                backendHost: "127.0.0.1",
                backendPort: 8000,
                helperHost: "127.0.0.1",
                helperPort: 8001
            )
            let configURL = resourcesDirectory.appending(path: "LearnToDrawHelperConfig.json")
            let data = try JSONEncoder().encode(config)
            try data.write(to: configURL)
        }

        return Fixture(root: root, repoRoot: repoRoot, resourcesDirectory: resourcesDirectory)
    }
}

private struct Fixture {
    let root: URL
    let repoRoot: URL
    let resourcesDirectory: URL

    func cleanup() throws {
        try FileManager.default.removeItem(at: root)
    }
}
