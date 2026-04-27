# ScanSafe — Cross-Platform QR Phishing Detector

> "Look before you tap."

ScanSafe detects and risk-scores URLs hidden inside QR codes in real time using a
classical OpenCV computer vision pipeline and a 22-rule heuristic URL scoring engine.
No cloud dependency. No pretrained ML models. Zero URL transmission.

---

## Research Question

Can a fully on-device classical CV pipeline provide meaningful QR phishing protection
in low-connectivity and privacy-sensitive environments — and what are the measurable
tradeoffs in detection rates?

---

## Repository Layout

```
scansafe-ios/
├── ios/                        # Original iOS implementation (Swift + SwiftUI + OpenCV)
│   ├── ScanSafe/               # Swift source files
│   │   ├── ScanSafeApp.swift
│   │   ├── CameraView.swift
│   │   ├── QRScanner.swift     # OpenCV classical pipeline
│   │   ├── URLRiskScorer.swift # 22-rule heuristic engine
│   │   ├── ResultView.swift
│   │   ├── HistoryView.swift
│   │   ├── HistoryStore.swift
│   │   ├── ContentView.swift
│   │   └── Models.swift
│   ├── ScanSafe.xcodeproj
│   └── Package.swift
├── scansafe (1)/               # Cross-platform Python prototype
│   ├── scansafe_prototype.py   # Full 22-rule engine + OpenCV QR decode
│   ├── app.py                  # Flask web API (POST /scan + browser UI)
│   ├── generate_report_v3.py   # NSF research report generator
│   ├── phishing_corpus.txt     # 28-URL test corpus
│   └── ScanSafe_NSF_Research_Report_v3.pdf
├── research/
│   └── research_question.md
└── README.md
```

---

## iOS App (`ios/`)

The original implementation runs fully on-device on iPhone using:

- **Swift + SwiftUI** — native UI
- **OpenCV 4.13** (Swift Package Manager) — grayscale → blur → Canny → FindContours
- **cv2.QRCodeDetector** (via OpenCV SPM) — QR decode, replacing Apple Vision
- **CoreMotion EMA** — accelerometer/gyroscope sensor fusion for scan stabilisation

Open `ios/ScanSafe.xcodeproj` in Xcode, select your device or simulator, and run.

---

## Python Prototype (`scansafe (1)/`)

A complete cross-platform reimplementation of the full pipeline using pure Python
and OpenCV. No platform-specific dependencies — runs on Windows, macOS, Linux,
and Android (via OpenCV for Android).

### Requirements

```bash
pip install opencv-python flask
```

### Usage

```bash
# Score a URL directly (all 22 rules)
python scansafe_prototype.py --url "https://paypa1.com/login"

# Decode a QR code from an image file
python scansafe_prototype.py --image path/to/qr.png

# Live webcam mode
python scansafe_prototype.py --camera

# Score a URL copied to your clipboard
python scansafe_prototype.py --clipboard

# Optional: Cloudflare Radar reputation lookup (off by default)
python scansafe_prototype.py --url "https://example.com" --radar
```

### Flask Web API

Start the API server to test URLs from any device on the same network (iOS, Android,
desktop browser — no app install required):

```bash
python app.py
```

The server prints its local IP on startup. Open `http://<IP>:5000` on any device on
your WiFi network. The browser UI accepts a URL, submits it, and displays the verdict.

**API endpoint:**

```
POST /scan
Content-Type: application/json
{"url": "https://example.com"}

→ {"risk_level": "HIGH RISK", "score": 9, "findings": [...], "technical": [...]}
```

---

## 22-Rule Heuristic Engine

| Phase | Rules | Signal |
|-------|-------|--------|
| Phase 1 (1–18) | Structural | HTTP, IP address, suspicious TLD, excessive subdomains, brand substitution, URL shortener, @ symbol, punycode, double extension, SafeLinks, dangerous schemes, consonant ratio, numeric domain, phishing keywords, encoded obfuscation |
| Phase 2 (19–22) | Fuzzy | LCS typosquatting (Rule 19), SimHash near-duplicate (Rule 20), urgency language (Rule 21), free hosting platform abuse (Rule 22) |

**Score thresholds:** 0–2 → SAFE · 3–5 → SUSPICIOUS · 6+ → HIGH RISK

---

## Privacy

- No URLs are transmitted to any external service
- No camera frames are stored or sent
- All processing is local and ephemeral
- Cloudflare Radar integration is opt-in only (`--radar` flag)

---

## Author

Patrick Selby — Cybersecurity Major, Grambling State University
Research Assistant, AIoT Lab under Dr. Vasanth Iyer
