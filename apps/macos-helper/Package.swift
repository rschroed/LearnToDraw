// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "LearnToDrawCameraHelper",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .library(
            name: "CameraHelperCore",
            targets: ["CameraHelperCore"]
        ),
        .executable(
            name: "LearnToDrawCameraHelper",
            targets: ["LearnToDrawCameraHelper"]
        ),
    ],
    targets: [
        .target(
            name: "CameraHelperCore"
        ),
        .executableTarget(
            name: "LearnToDrawCameraHelper",
            dependencies: ["CameraHelperCore"]
        ),
        .testTarget(
            name: "CameraHelperCoreTests",
            dependencies: ["CameraHelperCore"]
        ),
    ]
)
