"""
ScanSafe Flask API
==================
Wraps the 22-rule URL risk scorer as a web service.

Routes:
  GET  /        Browser UI — URL input, live QR camera, processing mode toggle, FPS counter
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
    #qrBtn.active { border-color: #00ff9c; background: #0a1f14; border-style: solid; }

    /* ── Processing mode toggle ── */
    #modeBar {
      display: none; width: 100%; max-width: 520px;
      margin-top: 10px; border-radius: 8px;
      overflow: hidden; border: 1px solid #2a2a2a;
      flex-direction: row;
    }
    .modeBtn {
      flex: 1; padding: 8px 0; background: #141414; color: #666;
      border: none; border-right: 1px solid #2a2a2a;
      font-size: 0.80rem; font-weight: 600; cursor: pointer;
      transition: background 0.15s, color 0.15s; letter-spacing: 0.03em;
    }
    .modeBtn:last-child { border-right: none; }
    .modeBtn.active { background: #0a1f14; color: #00ff9c; }
    .modeBtn:hover:not(.active) { background: #1c1c1c; color: #ccc; }

    /* ── Camera section ── */
    #cameraSection {
      display: none; width: 100%; max-width: 520px; margin-top: 16px;
    }
    .video-wrap { position: relative; width: 100%; }
    #video {
      width: 100%; border-radius: 12px; display: block;
      border: 2px solid #333; background: #111;
    }
    #overlay {
      position: absolute; top: 0; left: 0;
      width: 100%; height: 100%;
      border-radius: 12px; display: none;
      pointer-events: none;
    }
    @keyframes pulse-border {
      0%, 100% { border-color: #00ff9c; }
      50%       { border-color: #004d2e; }
    }
    #video.scanning { animation: pulse-border 1.4s ease-in-out infinite; }
    #video.detected { border-color: #00ff9c; animation: none; }
    #canvas { display: none; }

    /* ── FPS + status bar ── */
    #statusBar {
      display: none; width: 100%; max-width: 520px;
      margin-top: 7px; padding: 0 2px;
      display: none; justify-content: space-between; align-items: center;
    }
    #qrStatus { font-size: 0.82rem; color: #555; min-height: 1.2em; }
    #fpsDisplay {
      font-size: 0.75rem; color: #444; font-family: monospace;
      white-space: nowrap; padding: 2px 8px;
      background: #141414; border-radius: 4px; border: 1px solid #222;
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

  <!-- URL text input -->
  <form id="scanForm">
    <input type="text" id="urlInput" placeholder="Paste a URL to scan&hellip;"
           autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false">
    <button type="submit">Scan</button>
  </form>

  <!-- Live QR camera toggle -->
  <button id="qrBtn">&#128247;&nbsp; Scan QR Code</button>

  <!-- Processing mode toggle (shown when camera is active) -->
  <div id="modeBar" style="display:none">
    <button class="modeBtn active" data-mode="raw">Raw</button>
    <button class="modeBtn"       data-mode="edges">Edges</button>
    <button class="modeBtn"       data-mode="contours">Contours</button>
  </div>

  <!-- Camera section -->
  <div id="cameraSection">
    <div class="video-wrap">
      <video id="video" playsinline muted></video>
      <canvas id="overlay"></canvas>
    </div>
    <!-- Status + FPS bar -->
    <div id="statusBar" style="display:none">
      <span id="qrStatus">Align a QR code within the frame&hellip;</span>
      <span id="fpsDisplay">-- fps</span>
    </div>
    <button id="stopBtn">&#10005;&nbsp; Stop scanning</button>
  </div>

  <!-- Hidden canvas for jsQR processing -->
  <canvas id="canvas"></canvas>

  <p class="spinner" id="spinner">Scanning&hellip;</p>
  <div id="result"></div>

  <script>
    // ── Utility ───────────────────────────────────────────────────────────────
    function escHtml(s) {
      return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ── Shared URL scorer ─────────────────────────────────────────────────────
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
        const findings  = data.findings.map(f => `<li>${escHtml(f)}</li>`).join('');
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

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const qrBtn         = document.getElementById('qrBtn');
    const cameraSection = document.getElementById('cameraSection');
    const video         = document.getElementById('video');
    const canvas        = document.getElementById('canvas');
    const overlay       = document.getElementById('overlay');
    const qrStatus      = document.getElementById('qrStatus');
    const statusBar     = document.getElementById('statusBar');
    const fpsDisplay    = document.getElementById('fpsDisplay');
    const modeBar       = document.getElementById('modeBar');
    const stopBtn       = document.getElementById('stopBtn');

    // ── State ─────────────────────────────────────────────────────────────────
    let stream     = null;
    let animFrame  = null;
    let detected   = false;
    let viewMode   = 'raw';          // 'raw' | 'edges' | 'contours'

    // FPS rolling average (last 10 frame deltas)
    const FPS_BUF = new Float32Array(10);
    let   fpsBufIdx  = 0;
    let   lastTickMs = 0;

    // Off-screen canvas for edge processing (reused across frames)
    const procCanvas = document.createElement('canvas');
    const procCtx    = procCanvas.getContext('2d', { willReadFrequently: true });

    // ── Mode toggle ───────────────────────────────────────────────────────────
    document.querySelectorAll('.modeBtn').forEach(btn => {
      btn.addEventListener('click', function() {
        viewMode = this.dataset.mode;
        document.querySelectorAll('.modeBtn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        // In raw mode hide overlay; others will draw on next tick
        if (viewMode === 'raw') {
          overlay.style.display = 'none';
          video.style.display   = 'block';
        }
      });
    });

    // ── Edge detection (Sobel, processed at 50% resolution) ──────────────────
    function drawEdges() {
      const vw = video.videoWidth, vh = video.videoHeight;
      if (!vw || !vh) return;
      // Process at half resolution for performance
      const pw = Math.floor(vw / 2), ph = Math.floor(vh / 2);
      procCanvas.width = pw; procCanvas.height = ph;
      procCtx.drawImage(video, 0, 0, pw, ph);
      const id  = procCtx.getImageData(0, 0, pw, ph);
      const src = id.data;
      const out = new ImageData(pw, ph);
      const dst = out.data;

      // ITU-R BT.601 grayscale
      const gray = new Uint8Array(pw * ph);
      for (let i = 0; i < pw * ph; i++) {
        gray[i] = (0.299 * src[i*4] + 0.587 * src[i*4+1] + 0.114 * src[i*4+2]) | 0;
      }

      // 3×3 Sobel kernel
      for (let y = 1; y < ph - 1; y++) {
        for (let x = 1; x < pw - 1; x++) {
          const tl=gray[(y-1)*pw+(x-1)], tc=gray[(y-1)*pw+x], tr=gray[(y-1)*pw+(x+1)];
          const ml=gray[y*pw+(x-1)],                           mr=gray[y*pw+(x+1)];
          const bl=gray[(y+1)*pw+(x-1)], bc=gray[(y+1)*pw+x], br=gray[(y+1)*pw+(x+1)];
          const gx = -tl + tr - 2*ml + 2*mr - bl + br;
          const gy = -tl - 2*tc - tr + bl + 2*bc + br;
          const mag = Math.min(255, (Math.sqrt(gx*gx + gy*gy)) | 0);
          const p = (y*pw+x)*4;
          dst[p]=dst[p+1]=dst[p+2]=mag; dst[p+3]=255;
        }
      }
      procCtx.putImageData(out, 0, 0);

      // Scale up to overlay at native video resolution
      overlay.width  = vw; overlay.height = vh;
      const octx = overlay.getContext('2d');
      octx.imageSmoothingEnabled = false;
      octx.drawImage(procCanvas, 0, 0, pw, ph, 0, 0, vw, vh);
    }

    // ── Contour overlay (bounding box of detected QR quad) ───────────────────
    function drawContours(code) {
      const vw = video.videoWidth, vh = video.videoHeight;
      if (!vw || !vh) return;
      overlay.width = vw; overlay.height = vh;
      const octx = overlay.getContext('2d');
      octx.clearRect(0, 0, vw, vh);
      if (!code) return;
      const loc = code.location;
      // Draw QR quadrilateral
      octx.strokeStyle = '#00ff9c';
      octx.lineWidth   = Math.max(2, vw / 200);
      octx.shadowColor = '#00ff9c';
      octx.shadowBlur  = 8;
      octx.beginPath();
      octx.moveTo(loc.topLeftCorner.x,     loc.topLeftCorner.y);
      octx.lineTo(loc.topRightCorner.x,    loc.topRightCorner.y);
      octx.lineTo(loc.bottomRightCorner.x, loc.bottomRightCorner.y);
      octx.lineTo(loc.bottomLeftCorner.x,  loc.bottomLeftCorner.y);
      octx.closePath();
      octx.stroke();
      // Corner dots
      [loc.topLeftCorner, loc.topRightCorner,
       loc.bottomRightCorner, loc.bottomLeftCorner].forEach(pt => {
        octx.fillStyle = '#00ff9c';
        octx.beginPath();
        octx.arc(pt.x, pt.y, Math.max(4, vw / 120), 0, Math.PI * 2);
        octx.fill();
      });
    }

    // ── Camera start / stop ───────────────────────────────────────────────────
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
        lastTickMs = performance.now();
        cameraSection.style.display = 'block';
        statusBar.style.display     = 'flex';
        modeBar.style.display       = 'flex';
        video.classList.add('scanning');
        qrStatus.textContent = 'Align a QR code within the frame…';
        qrBtn.innerHTML = '&#128247;&nbsp; Camera active — tap to stop';
        qrBtn.classList.add('active');
        qrBtn.disabled = false;
        // Reset to raw mode on each camera start
        viewMode = 'raw';
        document.querySelectorAll('.modeBtn').forEach(b => {
          b.classList.toggle('active', b.dataset.mode === 'raw');
        });
        overlay.style.display = 'none';
        tick();
      } catch (err) {
        stream = null;
        qrBtn.innerHTML = '&#128247;&nbsp; Scan QR Code';
        qrBtn.disabled  = false;
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
      statusBar.style.display     = 'none';
      modeBar.style.display       = 'none';
      overlay.style.display       = 'none';
      qrBtn.innerHTML = '&#128247;&nbsp; Scan QR Code';
      qrBtn.classList.remove('active');
      qrBtn.disabled = false;
      detected = false;
      fpsDisplay.textContent = '-- fps';
    }

    // ── Main processing loop ──────────────────────────────────────────────────
    function tick() {
      if (!stream) return;
      animFrame = requestAnimationFrame(tick);
      if (video.readyState < video.HAVE_ENOUGH_DATA) return;

      // ── FPS rolling average ───────────────────────────────────────────────
      const now = performance.now();
      const delta = now - lastTickMs;
      lastTickMs = now;
      if (delta > 0) {
        FPS_BUF[fpsBufIdx % FPS_BUF.length] = 1000 / delta;
        fpsBufIdx++;
        if (fpsBufIdx >= FPS_BUF.length) {
          const avg = FPS_BUF.reduce((a, b) => a + b, 0) / FPS_BUF.length;
          fpsDisplay.textContent = `${avg.toFixed(1)} fps | ${viewMode.charAt(0).toUpperCase() + viewMode.slice(1)}`;
        }
      }

      // ── Draw to hidden canvas for jsQR ────────────────────────────────────
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(video, 0, 0);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height,
                        { inversionAttempts: 'dontInvert' });

      // ── Processing mode overlay ───────────────────────────────────────────
      if (viewMode === 'edges') {
        video.style.display    = 'none';
        overlay.style.display  = 'block';
        drawEdges();
      } else if (viewMode === 'contours') {
        video.style.display    = 'block';
        overlay.style.display  = 'block';
        drawContours(code || null);
      } else {
        // raw
        video.style.display    = 'block';
        overlay.style.display  = 'none';
      }

      // ── QR detected ──────────────────────────────────────────────────────
      if (!code || !code.data || detected) return;
      detected = true;
      cancelAnimationFrame(animFrame);
      animFrame = null;
      video.classList.remove('scanning');
      video.classList.add('detected');
      qrStatus.textContent = '✓ QR detected — scoring URL…';
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
    print(f"  Network: http://{ip}:8080  <- open this on any phone (auto-redirects to HTTPS)")
    print(f"           https://{ip}:5000  <- direct HTTPS link")
    print(f"\n  Phone will show a certificate warning (self-signed cert).")
    print(f"  Tap 'Advanced' -> 'Proceed to {ip}' to continue.\n")
    app.run(host="0.0.0.0", port=5000, debug=False, ssl_context="adhoc")
