# ScanSafe iOS — AI Coding Directives (v2)

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
│   ├── URLRiskScorer.swift        # 12 heuristic rules (pure function)
│   ├── ResultView.swift           # Animated GREEN/YELLOW/RED verdict screen
│   ├── HistoryView.swift          # Scan history log
│   ├── HistoryStore.swift         # UserDefaults persistence
│   └── Models.swift               # Verdict enum + RiskResult + HistoryEntry structs
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
- Package Manager: Swift Package Manager
- Combine: Required for ObservableObject in QRScanner

## Layer 4: OpenCV Pipeline (strictly classical)
Per frame, in this exact order:
1. Convert CVPixelBuffer to OpenCV Mat
2. Grayscale conversion (comment: reduces complexity, removes color noise)
3. Gaussian blur 5x5 kernel (comment: smooths edges, reduces false contours)
4. Canny edge detection thresholds 50, 150 (comment: detects QR code edges)
5. FindContours (comment: identifies rectangular regions for QR detection)
6. Pass frame to Vision for QR URL extraction only
7. Send URL to URLRiskScorer

## Layer 5: URL Risk Scoring Rules (ALL 12 rules — pure function)

### Original 6 rules:
| Rule | Points | Reason |
|------|--------|--------|
| IP address instead of domain | +3 | "Legitimate services use domain names (IP address detected)" |
| Brand substitution (paypa1, amaz0n, g00gle, faceb00k, micr0s0ft, app1e) | +3 | "Classic phishing pattern (brand name substitution)" |
| HTTP instead of HTTPS | +2 | "No transport encryption (HTTP used)" |
| Subdomain count > 3 | +2 | "Common in phishing infrastructure (too many subdomains)" |
| Path length > 50 chars | +1 | "Obfuscation indicator (long path)" |
| Consonant ratio in domain > 0.75 | +1 | "Generated domain pattern (high consonant ratio)" |

### New 6 rules:
| Rule | Points | Reason |
|------|--------|--------|
| URL shortener (bit.ly, tinyurl, t.co, goo.gl, ow.ly) | +3 | "URL shortener hides true destination" |
| Suspicious keywords in path (verify, confirm, secure, login, update, account, password, signin) | +2 | "Suspicious keywords in URL path" |
| Free hosting domains (000webhostapp, weebly, wix, firebaseapp, netlify, github.io) | +2 | "Free hosting platform (common in phishing)" |
| Punycode domain (xn--) | +3 | "Internationalized domain spoofing detected" |
| Excessive hyphens in domain (> 2) | +2 | "Hyphen abuse common in phishing domains" |
| Numeric characters in domain name | +1 | "Numbers in domain may indicate spoofing" |

### Score mapping:
- 0–2 → GREEN — SAFE
- 3–5 → YELLOW — SUSPICIOUS  
- 6+ → RED — HIGH RISK

If score is 0, reason = "Safe URL". Otherwise join all fired reasons with " • "

## Layer 6: UI Design — Professional Security App
- Background: #0A0A0A (near black)
- GREEN accent: #00FF9C
- YELLOW accent: #FFD60A
- RED accent: #FF3B30
- Text: white and light gray
- Font: clean sans-serif, bold verdicts
- Animated corner brackets on camera screen (scan target area)
- Animated verdict circle: scale from 0 → full with .spring()
- Fade in verdict text after circle animation with .easeIn

## Layer 7: Features

### Scan History
- HistoryView accessible via button on CameraView
- Each entry: verdict color dot, truncated URL, timestamp, score
- Store up to 50 entries in UserDefaults via HistoryStore
- Swipe to delete, Clear All button

### Haptic Feedback
- RED → UIImpactFeedbackGenerator(.heavy)
- YELLOW → UIImpactFeedbackGenerator(.medium)
- GREEN → UIImpactFeedbackGenerator(.light)

### Share Result
- ShareLink button on ResultView (iOS 16+)
- Format: "ScanSafe Result: [VERDICT] | Score: [X] | URL: [url] | Reason: [reason]"

### Copy URL
- Long press URL text on ResultView → copies to clipboard
- UIPasteboard.general.string = scannedURL

### Test Buttons (on CameraView)
- SIMULATE SAFE → tests https://www.google.com
- SIMULATE PHISHING → tests http://paypa1-secure.com/login/verify

## Layer 8: Orchestration Rules
- NEVER use cloud APIs for security decisions
- NEVER add pretrained ML models for URL classification
- NEVER store or log scanned URLs to any external service
- ALWAYS add import Combine to QRScanner.swift
- ALWAYS add a comment above each OpenCV step explaining what it does and why
- ALWAYS write URLRiskScorer as a pure function (input: String, output: RiskResult)
- ALWAYS ask before adding a new dependency
- Keep UI minimal: one camera view, one result view, one history view

## Layer 9: Research Constraints
Classical CV constraint is intentional and must be preserved.
Evaluation metrics: detection latency, true positive rate, false positive rate, battery impact.
The PayPal phish scoring YELLOW not RED is a research finding about conservative scoring.
Sophisticated phishing (HTTPS + clean domain) is a known false negative — document as research finding.
