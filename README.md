# ScanSafe iOS

> "Look before you tap."

ScanSafe is an on-device iOS security app that detects and risk-scores QR code URLs in real time using classical computer vision. No cloud dependency. No pretrained ML security models.

---

## Research Question

Can a fully on-device, classical CV pipeline provide meaningful QR phishing protection in low-connectivity and privacy-sensitive environments — and what are the tradeoffs in false positive and false negative rates?

---

## How It Works

1. Camera opens and captures live frames
2. Each frame passes through an OpenCV classical CV pipeline:
   - Grayscale conversion
   - Gaussian blur (5x5 kernel)
   - Canny edge detection
   - FindContours
3. Apple Vision framework decodes the URL string from the QR code (decode only — not a security model)
4. URL is passed to `URLRiskScorer`
5. `URLRiskScorer` returns a `RiskResult` (score, verdict, plain-English reason)
6. Verdict screen displays a colored circle (GREEN / YELLOW / RED) with reason and URL
7. "Scan Again" button returns to the camera

---

## Risk Scoring Rules

| Rule | Points | Reason Shown |
|------|--------|--------------|
| IP address instead of domain | +3 | Legitimate services use domain names (IP address detected) |
| Brand name + character substitution | +3 | Classic phishing pattern (brand name substitution) |
| HTTP instead of HTTPS | +2 | No transport encryption (HTTP used) |
| Subdomain count > 3 | +2 | Common in phishing infrastructure (too many subdomains) |
| Path length > 50 characters | +1 | Obfuscation indicator (long path) |
| High consonant ratio in domain (> 0.75) | +1 | Generated domain pattern (high consonant ratio) |

**Score mapping:**
- 0–2 → 🟢 GREEN — SAFE
- 3–5 → 🟡 YELLOW — SUSPICIOUS
- 6+ → 🔴 RED — HIGH RISK

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Swift |
| UI | SwiftUI |
| Camera | AVFoundation |
| Computer Vision | OpenCV for iOS (classical pipeline only) |
| QR Decode | Apple Vision (VNDetectBarcodesRequest) |
| Package Manager | Swift Package Manager |

---

## Project Structure

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
├── claude.md                      # AI coding directives
├── README.md
└── research/
    └── research_question.md
```

---

## Testing

Since the iPhone simulator cannot scan real QR codes, two test buttons are available on the camera screen:

- **SIMULATE GOOGLE (SAFE)** → tests `https://www.google.com`
- **SIMULATE PAYPAL PHISH (MALICIOUS)** → tests `http://paypa1-secure.com/login/verify`

To test on a real iPhone, connect via USB to your Mac and select your device in Xcode (free Apple Developer account required).

---

## Privacy

- No URLs are stored or logged
- All processing happens on-device
- No network requests are made

---

## Author

Patrick Selby — Cybersecurity Major, Grambling State University  
Research Assistant, AIoT Lab under Dr. Vasanth Iyer  
GitHub: [github.com/pat-selby](https://github.com/pat-selby)
