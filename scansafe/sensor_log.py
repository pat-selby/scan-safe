"""
ScanSafe Sensor Logger
======================
Serves a browser page that captures accelerometer and gyroscope readings
via the DeviceMotion API, applies EMA smoothing (alpha=0.15), and streams
each reading to this server where it is appended to a CSV file.

Satisfies the sensor data extraction requirement:
  - 6-axis capture: accelerometer (x, y, z) + gyroscope (alpha, beta, gamma)
  - EMA filter matches the formula used in the iOS CoreMotion implementation
  - Output: sensor_data.csv alongside this script

Usage:
  python sensor_log.py

Open https://<IP>:5001 on your phone (accept self-signed cert warning).
Tap "Start Logging", move the device, then tap "Download CSV".

DeviceMotion API requires HTTPS on iOS 13+ and Android Chrome. The server
runs with an adhoc TLS cert (same as app.py) for compatibility.
"""

import csv
import os
import socket
import time
import threading
from flask import Flask, request, jsonify, render_template_string

app   = Flask(__name__)
_lock = threading.Lock()

EMA_ALPHA = 0.15
CSV_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensor_data.csv")

_ema      = {}   # key → smoothed value
_row_count = 0

# ── EMA filter ────────────────────────────────────────────────────────────────

def _ema_update(key: str, value):
    """s_hat_t = alpha * s_t + (1 - alpha) * s_hat_{t-1}"""
    if value is None:
        return None
    if key not in _ema:
        _ema[key] = value
    else:
        _ema[key] = EMA_ALPHA * value + (1.0 - EMA_ALPHA) * _ema[key]
    return _ema[key]


def _fmt(v):
    return round(v, 5) if v is not None else ""


def _ensure_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "timestamp_ms",
                "acc_x", "acc_y", "acc_z",
                "gyro_alpha", "gyro_beta", "gyro_gamma",
                "ema_acc_x", "ema_acc_y", "ema_acc_z",
                "ema_gyro_alpha", "ema_gyro_beta", "ema_gyro_gamma",
            ])

# ── Browser page ──────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ScanSafe — Sensor Logger</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0a0a0a; color: #f0f0f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; padding: 32px 16px; gap: 0;
    }
    h1 { font-size: 1.5rem; font-weight: 700; color: #00ff9c; margin-bottom: 4px; }
    .sub { font-size: 0.82rem; color: #666; margin-bottom: 24px; }
    .btn {
      padding: 12px 28px; border-radius: 8px; border: none;
      font-weight: 700; font-size: 0.95rem; cursor: pointer;
      transition: opacity 0.15s;
    }
    .btn:disabled { opacity: 0.35; cursor: default; }
    #startBtn { background: #00ff9c; color: #0a0a0a; }
    #stopBtn  { background: #ff3b30; color: #fff; display: none; }
    #dlBtn    { background: #1a3a6b; color: #fff; margin-top: 8px; display: none; }
    .row-count {
      font-size: 0.78rem; color: #555; margin-top: 10px;
      font-family: monospace;
    }
    /* ── Live readout panel ── */
    .panel {
      margin-top: 20px; width: 100%; max-width: 480px;
      background: #141414; border: 1px solid #222; border-radius: 12px;
      padding: 16px 20px;
    }
    .panel h2 { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
                color: #555; text-transform: uppercase; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th { text-align: left; color: #555; font-weight: 600;
         padding: 3px 0; font-size: 0.72rem; letter-spacing: 0.06em; }
    td { text-align: right; font-family: monospace; color: #ccc;
         padding: 3px 0; border-bottom: 1px solid #1e1e1e; }
    td:first-child { text-align: left; color: #666; }
    tr:last-child td { border-bottom: none; }
    .ema-val { color: #00ff9c; }
    .note {
      font-size: 0.75rem; color: #555; margin-top: 20px;
      max-width: 480px; text-align: center; line-height: 1.5;
    }
  </style>
</head>
<body>
  <h1>ScanSafe Sensor Logger</h1>
  <p class="sub">Accelerometer &amp; Gyroscope &rarr; CSV &nbsp;|&nbsp; EMA &alpha;=0.15</p>

  <button class="btn" id="startBtn">Start Logging</button>
  <button class="btn" id="stopBtn">Stop</button>
  <button class="btn" id="dlBtn">&#8595; Download CSV</button>
  <p class="row-count" id="rowCount">0 rows logged</p>

  <!-- Live readout -->
  <div class="panel">
    <h2>Live Readings</h2>
    <table>
      <tr>
        <th>Axis</th>
        <th>Raw</th>
        <th>EMA (smoothed)</th>
      </tr>
      <tr><td>acc_x</td><td id="r_ax">--</td><td class="ema-val" id="e_ax">--</td></tr>
      <tr><td>acc_y</td><td id="r_ay">--</td><td class="ema-val" id="e_ay">--</td></tr>
      <tr><td>acc_z</td><td id="r_az">--</td><td class="ema-val" id="e_az">--</td></tr>
      <tr><td>gyro_&alpha;</td><td id="r_ga">--</td><td class="ema-val" id="e_ga">--</td></tr>
      <tr><td>gyro_&beta;</td><td id="r_gb">--</td><td class="ema-val" id="e_gb">--</td></tr>
      <tr><td>gyro_&gamma;</td><td id="r_gg">--</td><td class="ema-val" id="e_gg">--</td></tr>
    </table>
  </div>

  <p class="note">
    On iOS 13+: tap Start, then allow motion access when prompted.<br>
    CSV is saved server-side. Use Download to export it from the browser.
  </p>

  <script>
    const startBtn  = document.getElementById('startBtn');
    const stopBtn   = document.getElementById('stopBtn');
    const dlBtn     = document.getElementById('dlBtn');
    const rowCount  = document.getElementById('rowCount');

    let logging = false;
    let pending = null;   // latest reading waiting to be sent
    let sendLoop = null;  // setInterval handle

    // ── Request iOS permission ────────────────────────────────────────────────
    async function requestMotionPermission() {
      if (typeof DeviceMotionEvent !== 'undefined' &&
          typeof DeviceMotionEvent.requestPermission === 'function') {
        const state = await DeviceMotionEvent.requestPermission();
        return state === 'granted';
      }
      return true; // non-iOS — permission not needed
    }

    // ── DeviceMotion handler ──────────────────────────────────────────────────
    function motionHandler(e) {
      if (!logging) return;
      const a  = e.accelerationIncludingGravity || {};
      const rr = e.rotationRate || {};
      pending = {
        ts: Date.now(),
        ax: a.x  ?? null, ay: a.y  ?? null, az: a.z  ?? null,
        ga: rr.alpha ?? null, gb: rr.beta ?? null, gg: rr.gamma ?? null,
      };
    }

    // ── Send one reading to /log ──────────────────────────────────────────────
    async function sendPending() {
      if (!pending) return;
      const payload = pending;
      pending = null;
      try {
        const resp = await fetch('/log', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
        });
        const d = await resp.json();
        rowCount.textContent = `${d.rows} rows logged`;
        const ea = d.ema.acc, eg = d.ema.gyro;
        // Update live table — raw (from payload)
        const fmt = v => (v === null || v === undefined || v === '') ? '--' : Number(v).toFixed(4);
        document.getElementById('r_ax').textContent = fmt(payload.ax);
        document.getElementById('r_ay').textContent = fmt(payload.ay);
        document.getElementById('r_az').textContent = fmt(payload.az);
        document.getElementById('r_ga').textContent = fmt(payload.ga);
        document.getElementById('r_gb').textContent = fmt(payload.gb);
        document.getElementById('r_gg').textContent = fmt(payload.gg);
        // EMA (from server)
        document.getElementById('e_ax').textContent = fmt(ea[0]);
        document.getElementById('e_ay').textContent = fmt(ea[1]);
        document.getElementById('e_az').textContent = fmt(ea[2]);
        document.getElementById('e_ga').textContent = fmt(eg[0]);
        document.getElementById('e_gb').textContent = fmt(eg[1]);
        document.getElementById('e_gg').textContent = fmt(eg[2]);
      } catch (_) { /* network error during stop — ignore */ }
    }

    // ── Start / stop ─────────────────────────────────────────────────────────
    startBtn.addEventListener('click', async function() {
      const granted = await requestMotionPermission();
      if (!granted) {
        alert('Motion access denied. Enable it in Settings → Privacy → Motion & Fitness.');
        return;
      }
      logging = true;
      window.addEventListener('devicemotion', motionHandler);
      sendLoop = setInterval(sendPending, 100);   // 10 Hz log rate
      startBtn.style.display = 'none';
      stopBtn.style.display  = 'inline-block';
      dlBtn.style.display    = 'inline-block';
    });

    stopBtn.addEventListener('click', function() {
      logging = false;
      window.removeEventListener('devicemotion', motionHandler);
      clearInterval(sendLoop);
      startBtn.style.display = 'inline-block';
      stopBtn.style.display  = 'none';
    });

    // ── Download CSV ─────────────────────────────────────────────────────────
    dlBtn.addEventListener('click', function() {
      window.location.href = '/download';
    });
  </script>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(_HTML)


@app.route("/log", methods=["POST"])
def log_reading():
    global _row_count
    d  = request.get_json(silent=True) or {}
    ts = d.get("ts", int(time.time() * 1000))

    ax = d.get("ax"); ay = d.get("ay"); az = d.get("az")
    ga = d.get("ga"); gb = d.get("gb"); gg = d.get("gg")

    eax = _ema_update("ax", ax); eay = _ema_update("ay", ay); eaz = _ema_update("az", az)
    ega = _ema_update("ga", ga); egb = _ema_update("gb", gb); egg = _ema_update("gg", gg)

    row = [
        ts,
        _fmt(ax), _fmt(ay), _fmt(az),
        _fmt(ga), _fmt(gb), _fmt(gg),
        _fmt(eax), _fmt(eay), _fmt(eaz),
        _fmt(ega), _fmt(egb), _fmt(egg),
    ]
    with _lock:
        with open(CSV_FILE, "a", newline="") as f:
            csv.writer(f).writerow(row)
        _row_count += 1
        count = _row_count

    return jsonify({
        "rows": count,
        "ema": {
            "acc":  [_fmt(eax), _fmt(eay), _fmt(eaz)],
            "gyro": [_fmt(ega), _fmt(egb), _fmt(egg)],
        },
    })


@app.route("/download")
def download():
    from flask import send_file
    return send_file(CSV_FILE, as_attachment=True,
                     download_name="sensor_data.csv",
                     mimetype="text/csv")


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
    _ensure_csv()
    ip = _local_ip()
    print(f"\n  ScanSafe Sensor Logger")
    print(f"  Logging to: {CSV_FILE}")
    print(f"  EMA alpha:  {EMA_ALPHA}")
    print(f"\n  Local:   https://127.0.0.1:5001")
    print(f"  Network: https://{ip}:5001  <- open this on your phone")
    print(f"\n  Accept the certificate warning, then tap Start Logging.\n")
    app.run(host="0.0.0.0", port=5001, debug=False, ssl_context="adhoc")
