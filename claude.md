# ScanSafe iOS — AI Coding Directives

## Layer 1: Project Identity
ScanSafe is an on-device iOS security app that detects and risk-scores QR code URLs 
in real time using classical computer vision. Runs entirely on-device — no cloud calls, 
no pretrained ML security models.

Tagline: "Look before you tap."
Research Question: Can a fully on-device classical CV pipeline provide meaningful QR 
phishing protection in low-connectivity and privacy-sensitive environments?

## Layer 2: Folder Structure
```
scansafe-ios/
├── ScanSafe/
│   ├── ScanSafeApp.swift          # App entry point
│   ├── ContentView.swift          # Root view
│   ├── CameraView.swift           # Live camera feed + test buttons
│   ├── QRScanner.swift            # OpenCV pipeline + Vision QR decode
│   ├── URLRiskScorer.swift        # 6 heuristic rules (pure function)
│   ├── ResultView.swift           # GREEN/YELLOW/RED verdict screen
│   └── Models.swift               # Verdict enum + RiskResult struct
├── claude.md
├── README.md
└── research/
    └── research_question.md
```

## Layer 3: Tech Stack
- Language: Swift
- UI: SwiftUI
- Camera: AVFoundation
- Computer Vision: OpenCV for iOS (classical pipeline only)
- QR Decode: Apple Vision framework (VNDetectBarcodesRequest) — decode only, NOT security
- Package Manager: Swift Package Manager or CocoaPods

## Layer 4: OpenCV Pipeline (strictly classical)
Per frame, in this exact order:
1. Convert CVPixelBuffer to OpenCV Mat
2. Grayscale conversion
3. Gaussian blur (5x5 kernel)
4. Canny edge detection (thresholds 50, 150)
5. FindContours
6. Pass frame to Vision for QR URL extraction only
7. Send URL to URLRiskScorer

## Layer 5: Orchestration Rules
- NEVER use cloud APIs for security decisions
- NEVER add pretrained ML models for URL classification
- NEVER store or log scanned URLs
- ALWAYS add a comment above each OpenCV step explaining what it does and why
- ALWAYS write URLRiskScorer as a pure function (input: String, output: RiskResult)
- ALWAYS ask before adding a new dependency
- Keep UI minimal: one camera view, one result view

## Layer 6: Research Constraints
Classical CV constraint is intentional and must be preserved.
Evaluation metrics: detection latency, true positive rate, false positive rate, battery impact.
