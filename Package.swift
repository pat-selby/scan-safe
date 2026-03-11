// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "ScanSafe",
    platforms: [
        .iOS(.v15)
    ],
    products: [
        .library(
            name: "ScanSafe",
            targets: ["ScanSafe"]
        )
    ],
    dependencies: [
        // Using a reliable distribution of OpenCV for Swift Package Manager
        .package(url: "https://github.com/yeatse/opencv-spm.git", branch: "main")
    ],
    targets: [
        .target(
            name: "ScanSafe",
            dependencies: [
                .product(name: "OpenCV", package: "opencv-spm")
            ],
            path: "ScanSafe"
        )
    ]
)
