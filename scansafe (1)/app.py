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
from flask import Flask, request, jsonify, render_template_string
from scansafe_prototype import score_url, RiskLevel

app = Flask(__name__)

# ── Browser UI ────────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ScanSafe</title>
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
    .tagline { font-size: 0.85rem; color: #888; margin-bottom: 32px; }
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
    #result { margin-top: 32px; width: 100%; max-width: 520px; }
    .card {
      border-radius: 12px; padding: 20px 24px; margin-bottom: 16px;
      background: #141414; border: 1px solid #222;
    }
    .verdict { font-size: 1.4rem; font-weight: 800; letter-spacing: 0.05em; }
    .score { font-size: 0.85rem; color: #888; margin-top: 4px; }
    .SAFE     { color: #00ff9c; }
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
    .error { color: #ff3b30; font-size: 0.9rem; margin-top: 16px; }
    .spinner { display: none; color: #555; margin-top: 16px; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>ScanSafe</h1>
  <p class="tagline">Look before you tap &mdash; 22-rule on-device phishing detector</p>

  <form id="scanForm">
    <input type="text" id="urlInput" placeholder="Paste a URL to scan&hellip;"
           autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false">
    <button type="submit">Scan</button>
  </form>

  <p class="spinner" id="spinner">Scanning&hellip;</p>
  <div id="result"></div>

  <script>
    document.getElementById('scanForm').addEventListener('submit', async function(e) {
      e.preventDefault();
      const url = document.getElementById('urlInput').value.trim();
      if (!url) return;

      document.getElementById('result').innerHTML = '';
      document.getElementById('spinner').style.display = 'block';

      try {
        const resp = await fetch('/scan', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({url})
        });
        const data = await resp.json();
        document.getElementById('spinner').style.display = 'none';

        if (data.error) {
          document.getElementById('result').innerHTML =
            `<p class="error">Error: ${data.error}</p>`;
          return;
        }

        const levelClass = data.risk_level.replace(' ', '_');
        const findings = data.findings.map(f =>
          `<li>${f}</li>`).join('');
        const technical = data.technical.map(t =>
          `<li class="tech">${t}</li>`).join('');

        document.getElementById('result').innerHTML = `
          <div class="card">
            <div class="verdict ${levelClass}">${data.risk_level}</div>
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
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('result').innerHTML =
          `<p class="error">Request failed: ${err.message}</p>`;
      }
    });
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
    print(f"\n  ScanSafe API running.")
    print(f"  Local:   http://127.0.0.1:5000")
    print(f"  Network: http://{ip}:5000  ← open this on any phone on the same WiFi\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
