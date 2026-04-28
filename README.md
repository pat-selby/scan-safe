# ScanSafe — Cross-Platform QR Phishing Detector

> **"Look before you tap."**

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
scan-safe/
├── scansafe/
│   ├── app.py                      # Flask web UI + REST API (POST /scan)
│   ├── scansafe_prototype.py       # Full 22-rule engine + OpenCV QR decode (CLI)
│   ├── sensor_log.py               # Device motion logger (accel + gyro → CSV, EMA)
│   ├── generate_report_drier.py    # Dr. Iyer report generator
│   ├── generate_report_v3.py       # Full NSF report generator
│   ├── assets/
│   │   ├── screenshots/            # Live app screenshots (iOS)
│   │   └── images/                 # Test QR code images
│   ├── data/
│   │   └── phishing_corpus.txt     # 28-URL evaluation corpus
│   └── docs/
│       └── ScanSafe_Report_DrIyer.pdf   # Trimmed report (6 pages)
├── research/
│   └── research_question.md
└── README.md
```

---

## Quick Start

### Requirements

```bash
cd scansafe
pip install opencv-python flask pyopenssl cryptography
```

### Run the Flask Web UI

```bash
python app.py
```

The server prints its local IP on startup. Open **`http://<IP>:8080`** on any phone on
the same WiFi — it auto-redirects to the HTTPS camera UI. Accept the self-signed cert
warning (tap Advanced → Proceed).

The browser UI supports:
- **Manual URL entry** — paste or type any URL
- **Live QR scanning** — camera-based jsQR decode, auto-submits to the 22-rule scorer
- **Processing mode toggle** — switch between Raw / Edge Detection / Contour Overlay views
- **Real-time FPS counter** — frame rate display during live scanning

### Score a URL from the Command Line

```bash
# Score a URL directly (all 22 rules)
python scansafe_prototype.py --url "https://paypa1.com/login"

# Decode QR from an image file
python scansafe_prototype.py --image assets/images/test_qr_highrisk.png

# Live webcam mode
python scansafe_prototype.py --camera

# Score a URL from your clipboard
python scansafe_prototype.py --clipboard

# Optional: Cloudflare Radar reputation lookup (off by default)
python scansafe_prototype.py --url "https://example.com" --radar
```

### Run the Sensor Logger

Captures accelerometer and gyroscope data from a phone browser using the
DeviceMotion API. Applies EMA smoothing (α = 0.15) and writes readings to CSV.

```bash
python sensor_log.py
```

Open `https://<IP>:5001` on your phone, tap **Start Logging**, and move the device.
Data is saved to `sensor_data.csv`. Press **Download CSV** to export from the browser.

---

## How to Reproduce Results

```bash
# 1. Run the full 28-URL phishing corpus through all 22 rules
python scansafe_prototype.py --url "https://paypa1.com/login"         # SUSPICIOUS (5)
python scansafe_prototype.py --url "blob:https://outlook.office.com/abc"  # HIGH RISK (8)
python scansafe_prototype.py --url "https://www.google.com"           # SAFE (0)

# 2. Score an entire corpus file
while IFS= read -r url; do
  python scansafe_prototype.py --url "$url"
done < data/phishing_corpus.txt

# 3. Regenerate the Dr. Iyer report PDF
python generate_report_drier.py   # outputs docs/ScanSafe_Report_DrIyer.pdf
```

**Expected results against the 28-URL corpus:**

| Category | Count | Expected verdict |
|----------|-------|-----------------|
| Category A — clear phishing | 12 | 11 × HIGH RISK, 1 × SUSPICIOUS |
| Category B — evasion patterns | 8 | SUSPICIOUS |
| Category C — sophisticated phishing | 5 | SUSPICIOUS or SAFE |
| Category D — control (legitimate) | 3 | SAFE |

---

## 22-Rule Heuristic Engine

| Phase | Rules | Signal type |
|-------|-------|-------------|
| Phase 1 (1–18) | Structural | HTTP scheme, IP address, suspicious TLD, excessive subdomains, brand substitution, URL shortener, @ symbol, punycode IDN, double extension, SafeLinks wrapper, dangerous URI scheme (blob:/data:/javascript:), consonant ratio, numeric domain, phishing keywords, percent-encoded obfuscation |
| Phase 2 (19–22) | Fuzzy | LCS typosquatting (Rule 19), SimHash near-duplicate (Rule 20), urgency language (Rule 21), free hosting platform abuse (Rule 22) |

**Score thresholds:** 0–2 → SAFE &nbsp;·&nbsp; 3–5 → SUSPICIOUS &nbsp;·&nbsp; 6+ → HIGH RISK

---

## OpenCV Pipeline

Every camera frame is processed in the same fixed order:

1. **Grayscale** — ITU-R BT.601: Ig = 0.299R + 0.587G + 0.114B
2. **Gaussian blur** — 5×5 kernel, σ=0
3. **Canny edge detection** — thresholds 50 / 150
4. **FindContours** — Suzuki-Abe border following
5. **QR decode** — cv2.QRCodeDetector
6. **22-rule URL scoring**

The Flask UI replicates stages 1–4 in JavaScript (Sobel edge approximation) for the
Edge and Contour overlay processing modes.

---

## Sensor Integration

`sensor_log.py` captures DeviceMotion data (accelerometer + gyroscope) via the
browser's DeviceMotion API and applies Exponential Moving Average (EMA) filtering:

```
s_hat_t = α × s_t + (1 − α) × s_hat_{t-1}     α = 0.15
```

Output: `sensor_data.csv` with raw and EMA-smoothed readings for all 6 axes
(acc_x/y/z, gyro_alpha/beta/gamma).

---

## Privacy

- No URLs are transmitted to any external service
- No camera frames are stored or sent anywhere
- All processing is local and ephemeral
- Cloudflare Radar integration is opt-in only (`--radar` flag)
- Sensor data is written only to local CSV — never uploaded

---

## Report

**[docs/ScanSafe_Report_DrIyer.pdf](scansafe/docs/ScanSafe_Report_DrIyer.pdf)** — 6-page
research report covering problem statement, research question, system architecture,
22-rule engine, real-world case studies, evaluation results, known limitations,
live demo screenshots, next steps, and references.

---

## Author

Patrick Selby — Cybersecurity Major, Grambling State University
Research Assistant, AIoT Lab under Dr. Vasanth Iyer
