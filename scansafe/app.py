"""
ScanSafe Flask API
==================
Wraps the 22-rule URL risk scorer as a web service.

Routes:
  GET  /        Browser UI — text input, submits to /scan, displays verdict
  POST /scan    JSON API: {"url": "..."} → {"risk_level", "score", "findings", "technical"}

Start:
  python app.py

The server prints its local IP on startup so any device on the same WiFi network
can open the browser UI without installing an app (iOS Safari, Android Chrome, etc.).
"""

import socket
import sys
import threading
import logging
from flask import Flask, request, jsonify, render_template_string, redirect
from scansafe_prototype import score_url, RiskLevel

app = Flask(__name__)

# ── HTTP → HTTPS redirect (port 8080) ────────────────────────────────────────
# navigator.mediaDevices.getUserMedia requires a secure context (HTTPS).
# Browsers hitting the HTTPS port over plain HTTP get ERR_CONNECTION_CLOSED.
# This redirect shim catches http://IP:8080 and bounces it to https://IP:5000
# so users never have to type https:// manually.

_redirect_app = Flask("_redirect")

@_redirect_app.route("/", defaults={"path": ""})
@_redirect_app.route("/<path:path>")
def _http_to_https(path):
    host_ip = request.host.split(":")[0]
    target = f"https://{host_ip}:5000"
    if path:
        target += "/" + path
    if request.query_string:
        target += "?" + request.query_string.decode()
    return redirect(target, 301)


def _start_redirect_server() -> None:
    # Silence werkzeug access logs for the redirect shim
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    _redirect_app.run(host="0.0.0.0", port=8080, debug=False)

# ── Browser UI ────────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ScanSafe</title>
  <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0a0a0a; color: #f0f0f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; justify-content: flex-start; padding: 32px 16px;
    }
    h1 { font-size: 1.8rem; font-weight: 700; letter-spacing: 0.04em;
         color: #00ff9c; margin-bottom: 4px; }
    .tagline { font-size: 0.85rem; color: #888; margin-bottom: 24px; }

    /* ── URL form ── */
    form { width: 100%; max-width: 520px; display: flex; gap: 10px; }
    input[type=text] {
      flex: 1; padding: 12px 16px; border-radius: 8px;
      border: 1px solid #333; background: #1a1a1a; color: #f0f0f0;
      font-size: 0.95rem; outline: none;
    }
    input[type=text]:focus { border-color: #00ff9c; }
    button {
      padding: 12px 20px; border-radius: 8px; border: none;
      background: #00ff9c; color: #0a0a0a; font-weight: 700;
      font-size: 0.95rem; cursor: pointer; white-space: nowrap;
    }
    button:active { opacity: 0.85; }
    button:disabled { opacity: 0.45; cursor: default; }

    /* ── QR camera button ── */
    #qrBtn {
      width: 100%; max-width: 520px; margin-top: 12px;
      padding: 12px; border-radius: 8px;
      border: 1px dashed #333; background: transparent;
      color: #00ff9c; font-weight: 700; font-size: 0.95rem; cursor: pointer;
      transition: border-color 0.2s, background 0.2s;
    }
    #qrBtn:hover  { border-color: #00ff9c; background: #0a1f14; }
    #qrBtn.active { border-color: #00ff9c; background: #0a1f14;
                    border-style: solid; }

    /* ── Camera section ── */
    #cameraSection {
      display: none; width: 100%; max-width: 520px; margin-top: 16px;
    }
    #video {
      width: 100%; border-radius: 12px; display: block;
      border: 2px solid #333; background: #111;
    }
    @keyframes pulse-border {
      0%, 100% { border-color: #00ff9c; }
      50%       { border-color: #004d2e; }
    }
    #video.scanning { animation: pulse-border 1.4s ease-in-out infinite; }
    #video.detected { border-color: #00ff9c; animation: none; }
    #canvas { display: none; }
    #qrStatus {
      text-align: center; font-size: 0.82rem; color: #555;
      margin-top: 8px; min-height: 1.2em;
    }
    #stopBtn {
      width: 100%; margin-top: 10px; padding: 10px 16px;
      border-radius: 8px; border: 1px solid #2a2a2a;
      background: #141414; color: #888;
      font-size: 0.88rem; cursor: pointer;
    }
    #stopBtn:hover { background: #1e1e1e; color: #f0f0f0; }

    /* ── Results ── */
    #result { margin-top: 28px; width: 100%; max-width: 520px; }
    .card {
      border-radius: 12px; padding: 20px 24px; margin-bottom: 16px;
      background: #141414; border: 1px solid #222;
    }
    .verdict { font-size: 1.4rem; font-weight: 800; letter-spacing: 0.05em; }
    .scanned-url {
      font-size: 0.75rem; color: #555; font-family: monospace;
      margin-top: 6px; word-break: break-all;
    }
    .score { font-size: 0.85rem; color: #888; margin-top: 4px; }
    .SAFE       { color: #00ff9c; }
    .SUSPICIOUS { color: #ffd60a; }
    .HIGH_RISK  { color: #ff3b30; }
    .section-label {
      font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
      color: #555; text-transform: uppercase; margin-bottom: 8px;
    }
    ul { list-style: none; padding: 0; }
    ul li { font-size: 0.9rem; line-height: 1.5; padding: 3px 0;
            border-bottom: 1px solid #222; }
    ul li:last-child { border-bottom: none; }
    .tech { font-size: 0.78rem; color: #888; font-family: monospace; }
    .error  { color: #ff3b30; font-size: 0.9rem; margin-top: 16px; }
    .spinner { display: none; color: #555; margin-top: 16px; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>ScanSafe</h1>
  <p class="tagline">Look before you tap &mdash; 22-rule on-device phishing detector</p>

  <!-- URL text input (fallback / manual) -->
  <form id="scanForm">
    <input type="text" id="urlInput" placeholder="Paste a URL to scan&hellip;"
           autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false">
    <button type="submit">Scan</button>
  </form>

  <!-- Live QR camera toggle -->
  <button id="qrBtn">&#128247;&nbsp; Scan QR Code</button>

  <div id="cameraSection">
    <video id="video" playsinline muted></video>
    <canvas id="canvas"></canvas>
    <p id="qrStatus">Align a QR code within the frame&hellip;</p>
    <button id="stopBtn">&#10005;&nbsp; Stop scanning</button>
  </div>

  <p class="spinner" id="spinner">Scanning&hellip;</p>
  <div id="result"></div>

  <script>
    // ── Utility ───────────────────────────────────────────────────────────────
    function escHtml(s) {
      return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ── Shared URL scorer (used by form AND QR path) ──────────────────────────
    async function scoreUrl(url) {
      const resultEl  = document.getElementById('result');
      const spinnerEl = document.getElementById('spinner');
      resultEl.innerHTML = '';
      spinnerEl.style.display = 'block';

      try {
        const resp = await fetch('/scan', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({url})
        });
        const data = await resp.json();
        spinnerEl.style.display = 'none';

        if (data.error) {
          resultEl.innerHTML = `<p class="error">Error: ${escHtml(data.error)}</p>`;
          return;
        }

        const levelClass = data.risk_level.replace(' ', '_');
        const findings  = data.findings.map( f => `<li>${escHtml(f)}</li>`).join('');
        const technical = data.technical.map(t => `<li class="tech">${escHtml(t)}</li>`).join('');

        resultEl.innerHTML = `
          <div class="card">
            <div class="verdict ${levelClass}">${escHtml(data.risk_level)}</div>
            <div class="scanned-url">${escHtml(url)}</div>
            <div class="score">Score: ${data.score} / 22 rules</div>
          </div>
          <div class="card">
            <div class="section-label">Plain-English Summary</div>
            <ul>${findings}</ul>
          </div>
          <div class="card">
            <div class="section-label">Technical Detail</div>
            <ul>${technical}</ul>
          </div>`;
      } catch (err) {
        spinnerEl.style.display = 'none';
        resultEl.innerHTML = `<p class="error">Request failed: ${escHtml(err.message)}</p>`;
      }
    }

    // ── URL form submit ───────────────────────────────────────────────────────
    document.getElementById('scanForm').addEventListener('submit', function(e) {
      e.preventDefault();
      const url = document.getElementById('urlInput').value.trim();
      if (url) scoreUrl(url);
    });

    // ── QR camera scanner ─────────────────────────────────────────────────────
    let stream         = null;   // MediaStream when camera is active
    let animFrame      = null;   // requestAnimationFrame handle
    let detected       = false;  // true once a QR is found (prevents double-fire)

    const qrBtn          = document.getElementById('qrBtn');
    const cameraSection  = document.getElementById('cameraSection');
    const video          = document.getElementById('video');
    const canvas         = document.getElementById('canvas');
    const qrStatus       = document.getElementById('qrStatus');
    const stopBtn        = document.getElementById('stopBtn');

    qrBtn.addEventListener('click', async function() {
      if (stream) { stopCamera(); return; }

      qrBtn.textContent = 'Requesting camera…';
      qrBtn.disabled = true;

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } }
        });
        video.srcObject = stream;
        await video.play();

        detected = false;
        cameraSection.style.display = 'block';
        video.classList.add('scanning');
        qrStatus.textContent = 'Align a QR code within the frame…';
        qrBtn.innerHTML = '&#128247;&nbsp; Camera active — tap to stop';
        qrBtn.classList.add('active');
        qrBtn.disabled = false;

        tick();
      } catch (err) {
        stream = null;
        qrBtn.innerHTML = '&#128247;&nbsp; Scan QR Code';
        qrBtn.disabled = false;
        document.getElementById('result').innerHTML =
          `<p class="error">Camera error: ${escHtml(err.message)}</p>`;
      }
    });

    stopBtn.addEventListener('click', stopCamera);

    function stopCamera() {
      if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
      if (stream)    { stream.getTracks().forEach(t => t.stop()); stream = null; }
      video.srcObject = null;
      video.classList.remove('scanning', 'detected');
      cameraSection.style.display = 'none';
      qrBtn.innerHTML  = '&#128247;&nbsp; Scan QR Code';
      qrBtn.classList.remove('active');
      qrBtn.disabled = false;
      detected = false;
    }

    function tick() {
      if (!stream) return;
      animFrame = requestAnimationFrame(tick);

      // Wait until video has enough data
      if (video.readyState < video.HAVE_ENOUGH_DATA) return;

      // Draw current frame to hidden canvas at native resolution
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(video, 0, 0);

      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height,
                        { inversionAttempts: 'dontInvert' });

      if (!code || !code.data || detected) return;

      // QR detected — cancel scan loop immediately to prevent double-fire
      detected = true;
      cancelAnimationFrame(animFrame);
      animFrame = null;

      video.classList.remove('scanning');
      video.classList.add('detected');
      qrStatus.textContent = '✓ QR detected — scoring URL…';

      // Brief hold (300 ms) so the user sees the detection flash, then submit
      setTimeout(async function() {
        const url = code.data;
        stopCamera();
        document.getElementById('urlInput').value = url;
        await scoreUrl(url);
        document.getElementById('result').scrollIntoView(
          { behavior: 'smooth', block: 'nearest' }
        );
      }, 300);
    }
  </script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(_HTML)


@app.route("/scan", methods=["POST"])
def scan():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "JSON body with 'url' field required"}), 400

    url = str(data["url"]).strip()
    if not url:
        return jsonify({"error": "url field must not be empty"}), 400

    result = score_url(url)
    return jsonify({
        "risk_level": result.level,
        "score":      result.score,
        "findings":   result.user_findings,
        "technical":  result.tech_findings,
    })


# ── Startup ───────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = _local_ip()
    threading.Thread(target=_start_redirect_server, daemon=True).start()
    print(f"\n  ScanSafe API running.")
    print(f"  Local:   https://127.0.0.1:5000")
    print(f"  Network: http://{ip}:8080  ← open this on any phone (auto-redirects to HTTPS)")
    print(f"           https://{ip}:5000  ← direct HTTPS link")
    print(f"\n  Phone will show a certificate warning (self-signed cert).")
    print(f"  Tap 'Advanced' → 'Proceed to {ip}' to continue.\n")
    app.run(host="0.0.0.0", port=5000, debug=False, ssl_context="adhoc")
