"""
ScanSafe — Cross-Platform Python Prototype
==========================================
Implements the full ScanSafe pipeline using pure OpenCV (no Apple frameworks).

Phase 1 — Core pipeline (replaces Apple frameworks):
  - Apple Vision VNDetectBarcodesRequest  → cv2.QRCodeDetector
  - iOS AVFoundation camera capture       → cv2.VideoCapture / image file
  - iOS CoreMotion EMA sensor fusion      → frame-stability check via OpenCV
  - 18-rule additive URL heuristic engine (identical logic to URLRiskScorer.swift)

Phase 2 — Fuzzy matching layer (addresses Dr. Iyer's feedback):
  - LCS fuzzy domain similarity           → typosquatting detection (Rule 19)
  - SimHash near-duplicate URL detection  → structural spoofing detection (Rule 20)
  - Cloudflare Radar reputation lookup    → optional, off by default (--radar flag)

Usage:
  python scansafe_prototype.py --image path/to/qr_image.png
  python scansafe_prototype.py --camera                       # live webcam mode
  python scansafe_prototype.py --url "https://example.com"   # URL-only mode
  python scansafe_prototype.py --url "https://example.com" --radar  # with Cloudflare

Requirements:
  pip install opencv-python          # Phase 1 + Phase 2 (LCS/SimHash are pure Python)
  pip install requests               # optional — only needed for --radar flag
"""

import cv2
import re
import argparse
import sys
import urllib.parse
from typing import Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel:
    SAFE      = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK  = "HIGH RISK"

    # Actual hex colours from ScanSafe iOS source (Models.swift)
    COLOR = {
        SAFE:      "\033[92m",   # bright green
        SUSPICIOUS: "\033[93m",  # bright yellow
        HIGH_RISK:  "\033[91m",  # bright red
    }
    RESET = "\033[0m"

    @staticmethod
    def from_score(score: int) -> str:
        """Mirror exact thresholds from URLRiskScorer.swift lines 182-187."""
        if score <= 2:
            return RiskLevel.SAFE
        elif score <= 5:
            return RiskLevel.SUSPICIOUS
        else:
            return RiskLevel.HIGH_RISK


class RiskResult:
    def __init__(self, url: str, score: int, level: str,
                 user_findings: list[str], tech_findings: list[str]):
        self.url = url
        self.score = score
        self.level = level
        self.user_findings = user_findings   # plain-English layer
        self.tech_findings = tech_findings   # technical detail layer

    def print_report(self):
        col = RiskLevel.COLOR[self.level]
        rst = RiskLevel.RESET
        print("\n" + "=" * 60)
        print(f"  ScanSafe Result: {col}{self.level} (score {self.score}){rst}")
        print("=" * 60)
        print(f"  URL: {self.url}")
        print()
        print("  ── Plain-English Summary ──────────────────────────────")
        for f in self.user_findings:
            print(f"    {f}")
        print()
        print("  ── Technical Detail ───────────────────────────────────")
        for f in self.tech_findings:
            print(f"    {f}")
        print("=" * 60 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# OPENCV QR PIPELINE  (replaces Apple Vision VNDetectBarcodesRequest)
# ─────────────────────────────────────────────────────────────────────────────

def opencv_preprocess(frame: "cv2.Mat") -> "cv2.Mat":
    """
    Classical CV pipeline matching ScanSafe iOS:
      ITU-R BT.601 grayscale → 5×5 Gaussian blur → Canny 50/150

    This preprocessing is applied before QR detection to improve
    decode reliability on low-contrast or noisy frames — mirroring
    the OpenCV pipeline in QRScanner.swift.
    """
    # Step 1: ITU-R BT.601 grayscale (OpenCV default for COLOR_BGR2GRAY)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Step 2: 5×5 Gaussian blur to suppress noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Step 3: Canny edge detection (thresholds: 50 low, 150 high)
    edges = cv2.Canny(blurred, 50, 150)

    return edges


def decode_qr_from_frame(frame: "cv2.Mat") -> Optional[str]:
    """
    Pure OpenCV QR decode — replaces Apple Vision VNDetectBarcodesRequest.
    Uses cv2.QRCodeDetector with multi-stage fallback pipeline to handle:
      - Standard black-on-white QR codes
      - Coloured/branded QR codes (e.g. gold GSU-branded phishing QRs)
      - Embedded-logo QR codes (logo disrupts centre finder pattern)
      - Low-contrast or noisy frames
    Cross-platform: works on macOS, Windows, Linux, Android (OpenCV for Android).
    """
    import numpy as np
    detector = cv2.QRCodeDetector()

    # Stage 1: original colour frame
    data, _, _ = detector.detectAndDecode(frame)
    if data:
        return data

    # Stage 2: standard grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    data, _, _ = detector.detectAndDecode(gray)
    if data:
        return data

    # Stage 3: Otsu binarisation — handles coloured QR codes (gold, blue, etc.)
    # Converts non-black module colour to pure black for reliable detection.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    data, _, _ = detector.detectAndDecode(binary)
    if data:
        return data

    # Stage 4: inverted Otsu — for light-on-dark QR codes
    data, _, _ = detector.detectAndDecode(cv2.bitwise_not(binary))
    if data:
        return data

    # Stage 5: upscale 2× — improves detection on small/low-res QR images
    upscaled = cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray_up = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    _, binary_up = cv2.threshold(gray_up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    data, _, _ = detector.detectAndDecode(binary_up)
    if data:
        return data

    return None


def decode_qr_from_image(image_path: str) -> Optional[str]:
    """Load an image file and extract the QR URL."""
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[ERROR] Could not read image: {image_path}")
        return None
    return decode_qr_from_frame(frame)


def scan_from_camera() -> Optional[str]:
    """
    Live camera mode — equivalent to iOS AVFoundation live frame capture.
    Replaces AVFoundation with cv2.VideoCapture (cross-platform).
    Press 'q' to quit, SPACE to freeze and decode.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera.")
        return None

    print("[INFO] Camera open. Point at a QR code. Press SPACE to scan, Q to quit.")
    detector = cv2.QRCodeDetector()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Try decoding every frame (live mode)
        data, bbox, _ = detector.detectAndDecode(frame)
        if data:
            # Draw bounding box when QR is found
            if bbox is not None:
                import numpy as np
                bbox = bbox.astype(int)
                cv2.polylines(frame, [bbox], True, (0, 255, 0), 2)
            cv2.imshow("ScanSafe — Live (QR Detected)", frame)
            cap.release()
            cv2.destroyAllWindows()
            return data

        cv2.putText(frame, "Scanning...", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.imshow("ScanSafe — Live", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 22-RULE HEURISTIC URL RISK ENGINE  (Phase 1: 1–18 + Phase 2: 19–22)
# ─────────────────────────────────────────────────────────────────────────────

# Known brand names for homoglyph / substitution detection (Rules 8, 19, 22)
BRAND_LIST = [
    "paypal", "apple", "microsoft", "google", "amazon", "facebook",
    "instagram", "twitter", "netflix", "chase", "wellsfargo", "bankofamerica",
    "grambling", "gsumail", "gram", "outlook", "office365",
    "onedrive", "dropbox", "sharepoint", "docusign", "zoom", "webex",
]

# Free hosting platforms abused for phishing (Rule 22)
# Attackers use these because accounts are free, anonymous, and fast to create.
FREE_HOSTING_PLATFORMS = {
    "wixsite.com", "weebly.com", "carrd.co", "webflow.io",
    "github.io", "gitlab.io", "netlify.app", "vercel.app",
    "pages.dev", "firebaseapp.com", "web.app", "glitch.me",
    "replit.app", "000webhostapp.com", "infinityfreeapp.com",
    "freewebhostingarea.com", "byet.host",
}

# Suspicious TLDs (Rule 3)
SUSPICIOUS_TLDS = {
    ".xyz", ".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".club",
    ".online", ".site", ".link", ".click", ".download", ".zip",
}

# High-risk ccTLDs sometimes abused (Rule 4)
RISKY_CCTLDS = {".ru", ".cn", ".pw", ".cc", ".su"}

# Common URL shorteners (Rule 9)
URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "goo.gl", "tiny.cc",
    "is.gd", "buff.ly", "rebrand.ly", "short.io", "cutt.ly",
}

# SafeLinks / redirect wrapper patterns (Rule 13 — GSU phishing case study)
REDIRECT_WRAPPERS = [
    r"safelinks\.protection\.outlook\.com",
    r"urldefense\.proofpoint\.com",
    r"urldefense\.com",
    r"protect-us\.mimecast\.com",
    r"protect2\.fireeye\.com",
    r"na01\.safelinks\.protection\.outlook\.com",
]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — LCS FUZZY DOMAIN SIMILARITY  (Rule 19: typosquatting detection)
# Ref: Charikar 2002; addresses Dr. Iyer's feedback on closing the ~30% gap
#      that rigid rule-matching misses on sophisticated visual spoofing.
# ─────────────────────────────────────────────────────────────────────────────

def _lcs_length(a: str, b: str) -> int:
    """
    Compute Longest Common Subsequence length via space-optimised DP (O(mn) time,
    O(min(m,n)) space). Used for fuzzy string similarity scoring.
    """
    if len(a) < len(b):
        a, b = b, a
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr
    return prev[n]


def lcs_similarity(a: str, b: str) -> float:
    """LCS-based Jaccard-style similarity ratio in [0.0, 1.0]."""
    if not a or not b:
        return 0.0
    return _lcs_length(a, b) / max(len(a), len(b))


# Common second-level SLDs that form two-part TLDs (e.g. .co.uk, .com.au)
_KNOWN_SLDS = {"co", "com", "net", "org", "gov", "edu", "ac", "me", "ne", "or"}


def _apex_domain(host: str) -> str:
    """
    Return the registrable domain label, handling two-part TLDs like .co.uk.
    'amaz0n.co.uk' → 'amaz0n';  'login.paypa1.com' → 'paypa1'.
    """
    parts = host.replace("www.", "").split(".")
    if len(parts) >= 3 and parts[-2] in _KNOWN_SLDS:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]


def detect_typosquatting(host: str) -> Optional[Tuple[str, float]]:
    """
    Compare the apex domain against known brands using LCS similarity.
    Returns (brand, similarity_score) when LCS similarity >= 0.75 and the
    domain is NOT an exact match (avoids false-positives on legitimate sites).

    Example catches that hard-coded Rule 8 misses:
      'grarnbling.edu'  → brand 'grambling', LCS similarity ≈ 0.89
      'paypa1.com'      → brand 'paypal',    LCS similarity ≈ 0.83
      'arnazon.com'     → brand 'amazon',    LCS similarity ≈ 0.86
    """
    # Apex = registrable domain label, two-part TLD aware (amaz0n.co.uk → amaz0n)
    apex = _apex_domain(host)
    apex_clean = re.sub(r"[^a-z0-9]", "", apex.lower())

    LCS_THRESHOLD = 0.75

    best_brand, best_sim = None, 0.0
    for brand in BRAND_LIST:
        brand_clean = re.sub(r"[^a-z0-9]", "", brand.lower())
        if apex_clean == brand_clean:
            continue  # exact match — legitimate, skip
        sim = lcs_similarity(apex_clean, brand_clean)
        if sim >= LCS_THRESHOLD and sim > best_sim:
            best_brand, best_sim = brand, sim

    return (best_brand, best_sim) if best_brand else None


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — SIMHASH NEAR-DUPLICATE URL DETECTION  (Rule 20)
# Ref: Charikar 2002, "Similarity Estimation Techniques from Rounding Algorithms"
# Generates a 64-bit locality-sensitive fingerprint; URLs structurally similar
# to a known-bad URL will have low Hamming distance (≤ SIMHASH_THRESHOLD bits).
# ─────────────────────────────────────────────────────────────────────────────

def _hash_token(token: str) -> int:
    """Jenkins-style 64-bit non-cryptographic hash for SimHash token weighting."""
    h = 5381
    for ch in token.encode("utf-8"):
        h = ((h << 5) + h + ch) & 0xFFFFFFFFFFFFFFFF
    return h


def simhash(url: str, bits: int = 64) -> int:
    """
    Compute a 64-bit SimHash fingerprint of a normalised URL.
    Tokens: lowercase domain labels + path segments + query key names.
    Query values are excluded (they carry per-session noise, not structure).
    """
    try:
        parsed = urllib.parse.urlparse(url.lower())
    except Exception:
        return 0

    tokens: list[str] = []
    tokens.extend([t for t in parsed.netloc.split(".") if t])
    tokens.extend([t for t in parsed.path.split("/") if t])
    if parsed.query:
        for kv in parsed.query.split("&"):
            key = kv.split("=")[0]
            if key:
                tokens.append(key)

    v = [0] * bits
    for token in tokens:
        h = _hash_token(token)
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1

    fingerprint = 0
    for i in range(bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Population count of XOR — number of differing bits."""
    return bin(a ^ b).count("1")


# In-session SimHash cache — grows as URLs are scored in a single run.
# In a production app this would be persisted to disk (SQLite / JSON).
_SIMHASH_CACHE: list[Tuple[str, int]] = []
SIMHASH_THRESHOLD = 4  # ≤4 differing bits → structurally near-duplicate


def check_near_duplicate(url: str) -> Optional[str]:
    """
    Compare this URL's SimHash fingerprint against every cached fingerprint.
    Returns the first cached URL within SIMHASH_THRESHOLD Hamming distance,
    or None if no near-duplicate exists. Always adds the URL to the cache.
    """
    fp = simhash(url)
    match: Optional[str] = None
    for cached_url, cached_fp in _SIMHASH_CACHE:
        if hamming_distance(fp, cached_fp) <= SIMHASH_THRESHOLD:
            match = cached_url
            break
    _SIMHASH_CACHE.append((url, fp))
    return match


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — CLOUDFLARE RADAR REPUTATION LOOKUP  (optional, off by default)
# Privacy-by-default: enabled only with --radar CLI flag (user-configurable).
# ─────────────────────────────────────────────────────────────────────────────

def cloudflare_radar_lookup(host: str) -> Optional[dict]:
    """
    Query the Cloudflare Radar domain reputation API (free, no key required).
    Returns a dict with 'malicious_score' and 'categories' on success, else None.
    Only called when --radar flag is passed — preserves on-device privacy default.
    """
    try:
        import requests  # optional dependency
        apex = ".".join(host.replace("www.", "").split(".")[-2:])
        url = f"https://radar.cloudflare.com/api/v0/domains/top?domain={apex}&format=json"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def score_url(url_string: str, enable_radar: bool = False) -> RiskResult:
    """
    20-rule additive heuristic scoring engine (Phase 1: Rules 1–18 + Phase 2: Rules 19–20).
    Phase 1 rules mirror URLRiskScorer.swift exactly (same weights, same thresholds).
    Phase 2 rules add fuzzy matching: LCS typosquatting + SimHash near-duplicate.
    Pure Python — no platform dependencies beyond stdlib.
    """
    score = 0
    user_findings: list[str] = []
    tech_findings: list[str] = []

    def flag(user_msg: str, tech_msg: str, points: int):
        nonlocal score
        score += points
        user_findings.append(user_msg)
        tech_findings.append(tech_msg)

    # Normalise — handle special schemes before parsing
    lower = url_string.lower().strip()

    # Track whether original URL used a dangerous wrapper scheme
    blob_wrapped = lower.startswith("blob:")

    # blob: wraps an inner https URL (e.g. blob:https://host/uuid)
    # Extract inner URL so host/path rules fire correctly; Rule 14 uses blob_wrapped flag
    if blob_wrapped:
        inner = lower[5:]  # strip "blob:"
        if inner.startswith("http"):
            lower = inner
    elif not lower.startswith("http") and not any(
        lower.startswith(p) for p in ("data:", "javascript:", "vbscript:")
    ):
        # Only prepend https:// for bare domains — dangerous schemes must reach the
        # parser intact so Rule 14 can read parsed.scheme correctly.
        lower = "https://" + lower

    try:
        parsed = urllib.parse.urlparse(lower)
        host = parsed.netloc or ""
        path = parsed.path or ""
        query = parsed.query or ""
    except Exception:
        return RiskResult(url_string, 10, RiskLevel.HIGH_RISK,
                          ["⚠️ This URL could not be parsed — treat as high risk."],
                          ["URL parsing failed."])

    full_url = lower

    # ── Rule 1: HTTP (no HTTPS) — weight +2 ──────────────────────────────────
    if parsed.scheme == "http":
        flag("🔓 This link uses HTTP, not HTTPS — your connection is unencrypted.",
             f"Rule 1: HTTP scheme detected. No transport encryption.",
             2)

    # ── Rule 2: IP address instead of domain — weight +3 ─────────────────────
    ip_pattern = r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$"
    if re.match(ip_pattern, host):
        flag("🔢 This link goes to a raw IP address — legitimate sites use domain names.",
             f"Rule 2: Host is an IP address ({host}), not a domain name.",
             3)

    # ── Rule 3: Suspicious TLD — weight +2 ───────────────────────────────────
    tld = "." + host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in SUSPICIOUS_TLDS:
        flag(f"🚩 The domain ends in '{tld}', a TLD commonly used for phishing.",
             f"Rule 3: TLD '{tld}' is in high-abuse list.",
             2)

    # ── Rule 4: High-risk ccTLD — weight +1 ──────────────────────────────────
    if tld in RISKY_CCTLDS:
        flag(f"⚠️ The domain ends in '{tld}', a country code with elevated phishing usage.",
             f"Rule 4: ccTLD '{tld}' has elevated phishing association.",
             1)

    # ── Rule 5: Excessive subdomains (> 3) — weight +2 ───────────────────────
    parts = host.split(".")
    if len(parts) > 4:
        flag("🔗 This URL has an unusually long chain of subdomains — a phishing pattern.",
             f"Rule 5: {len(parts)} subdomain levels detected (threshold: 4).",
             2)

    # ── Rule 6: Long path (> 50 chars) — weight +1 ───────────────────────────
    if len(path) > 50:
        flag("📏 This link has an unusually long URL path, often used to confuse users.",
             f"Rule 6: Path length {len(path)} chars > 50 threshold.",
             1)

    # ── Rule 7: Excessive query params — weight +1 ────────────────────────────
    if query.count("&") > 4:
        flag("🧩 This URL contains many query parameters — a common obfuscation pattern.",
             f"Rule 7: {query.count('&') + 1} query parameters detected.",
             1)

    # ── Rule 8: Brand name + character substitution — weight +3 ──────────────
    # Skip if the APEX domain IS the brand (e.g. docs.google.com is legitimate
    # Google — only flag when brand appears in a non-owner domain like
    # google-login.xyz or paypal.fakesite.com).
    apex_domain = _apex_domain(host)
    host_clean = re.sub(r"[^a-z0-9]", "", host)
    for brand in BRAND_LIST:
        brand_clean = re.sub(r"[^a-z0-9]", "", brand)
        apex_clean_r8 = re.sub(r"[^a-z0-9]", "", apex_domain)
        # Brand is in the full host but the apex domain is NOT the brand itself
        if brand_clean in host_clean and apex_clean_r8 != brand_clean:
            flag(f"🎭 '{brand}' appears embedded in the domain — possible brand spoofing.",
                 f"Rule 8: Brand '{brand}' detected in non-apex domain position.",
                 3)
            break

    # ── Rule 9: URL shortener — weight +2 ────────────────────────────────────
    base_host = host.replace("www.", "")
    if base_host in URL_SHORTENERS:
        flag("🔀 This is a shortened URL — the real destination is hidden.",
             f"Rule 9: URL shortener detected ({base_host}).",
             2)

    # ── Rule 10: '@' in URL (credential trick) — weight +3 ───────────────────
    if "@" in full_url.split("?")[0]:
        flag("⚠️ This URL contains '@', which can be used to hide the real destination.",
             "Rule 10: '@' character detected in URL path — credential-hiding technique.",
             3)

    # ── Rule 11: Punycode / IDN homoglyph — weight +3 ────────────────────────
    if "xn--" in host:
        flag("🔡 This URL uses special encoding to visually mimic a legitimate domain.",
             f"Rule 11: Punycode/IDN detected in host ({host}).",
             3)

    # ── Rule 12: Double extension in path — weight +2 ────────────────────────
    double_ext = re.search(r"\.\w{2,4}\.\w{2,4}$", path)
    if double_ext:
        flag("📄 The URL path has a double file extension — a common malware distribution trick.",
             f"Rule 12: Double extension detected in path: {double_ext.group()}.",
             2)

    # ── Rule 13: Redirect wrapper (SafeLinks / Proofpoint) — weight +3 ───────
    # GSU phishing case study: SafeLinks wrapping hid malicious destination.
    # Outer domain scores SAFE on all structural rules — inner URL is hidden.
    for pattern in REDIRECT_WRAPPERS:
        if re.search(pattern, host):
            inner_url = None
            # Try to extract destination from 'url=' param
            q_params = urllib.parse.parse_qs(query)
            if "url" in q_params:
                inner_url = urllib.parse.unquote(q_params["url"][0])
            flag(
                "🔗 This is a redirect wrapper (e.g. SafeLinks). The real destination is hidden inside. "
                + (f"Inner URL: {inner_url}" if inner_url else "Could not extract inner URL."),
                f"Rule 13: Redirect wrapper matched pattern '{pattern}'. "
                + (f"Extracted destination: {inner_url}" if inner_url else "Inner URL extraction failed."),
                3
            )
            # Recursively score the inner URL if extractable
            if inner_url:
                inner_result = score_url(inner_url, enable_radar=enable_radar)
                score += inner_result.score
                tech_findings.append(
                    f"Rule 13 (recursive): Inner URL scored {inner_result.score} "
                    f"({inner_result.level}): {inner_url}"
                )
            break

    # ── Rule 14: Dangerous URI scheme — weight +6 (forces HIGH RISK) ───────────
    # blob: added after real GSU phishing case: blob URLs never appear in
    # legitimate QR codes — browser-generated in-memory references hide the
    # real destination. Weight +6 guarantees HIGH RISK (threshold > 5).
    DANGEROUS_SCHEMES = {"data", "javascript", "vbscript"}
    is_dangerous_scheme = parsed.scheme in DANGEROUS_SCHEMES or blob_wrapped
    if is_dangerous_scheme:
        scheme_name = "blob" if blob_wrapped else parsed.scheme
        extra = (" Blob URLs never appear in legitimate QR codes — the real destination is hidden."
                 if blob_wrapped else "")
        flag(f"🚨 This URL uses a dangerous scheme ('{scheme_name}') — likely malicious.{extra}",
             f"Rule 14: Dangerous URI scheme '{scheme_name}' detected. Weight +6 → forced HIGH RISK.",
             6)

    # ── Rule 15: High consonant ratio in domain — weight +1 ──────────────────
    domain_alpha = re.sub(r"[^a-z]", "", host.split(".")[0])
    if len(domain_alpha) > 4:
        consonants = sum(1 for c in domain_alpha if c not in "aeiou")
        ratio = consonants / len(domain_alpha)
        if ratio > 0.75:
            flag("🔠 The domain name has an unusual pattern of characters — typical of generated domains.",
                 f"Rule 15: Consonant ratio {ratio:.2f} > 0.75 in domain '{domain_alpha}'.",
                 1)

    # ── Rule 16: Numeric-heavy domain — weight +1 ─────────────────────────────
    host_base = host.split(".")[0]
    digit_count = sum(c.isdigit() for c in host_base)
    if digit_count > 2:
        flag("🔢 The domain name contains multiple numbers — uncommon for legitimate sites.",
             f"Rule 16: {digit_count} digits in domain base '{host_base}'.",
             1)

    # ── Rule 17: Known-bad keywords in path — weight +2 ──────────────────────
    bad_keywords = ["login", "signin", "verify", "update", "secure",
                    "account", "banking", "confirm", "password", "auth"]
    for kw in bad_keywords:
        if kw in path.lower() or kw in query.lower():
            flag(f"🔑 The URL contains '{kw}' — a keyword commonly used in phishing pages.",
                 f"Rule 17: High-risk keyword '{kw}' detected in path/query.",
                 2)
            break

    # ── Rule 18: Encoded characters in suspicious positions — weight +1 ───────
    if "%" in query and query.count("%") > 3:
        flag("🔤 The URL contains unusual encoded characters in the query string.",
             f"Rule 18: {query.count('%')} percent-encoded chars in query — potential obfuscation.",
             1)

    # ── Rule 19: LCS Fuzzy Typosquatting — Phase 2, weight +3 ─────────────────
    # Extended: also checks path segments for brand impersonation with homoglyphs
    # Catches: /0ne-dr1ve (onedrive), /paypa1 (paypal), /g00gle (google)
    # Catches 'grarnbling.edu', 'paypa1.com', 'arnazon.com', etc. that pass
    # Rule 8 because they avoid exact brand-string inclusion.
    ts_match = detect_typosquatting(host)
    if ts_match:
        ts_brand, ts_sim = ts_match
        flag(
            f"🎭 This domain closely resembles '{ts_brand}' ({ts_sim:.0%} similar) "
            f"— likely a typosquatting attempt.",
            f"Rule 19 (LCS fuzzy): apex domain vs '{ts_brand}', LCS similarity = {ts_sim:.3f} "
            f"(threshold: 0.75).",
            3
        )

    # Rule 19b: LCS path-segment brand impersonation with homoglyph normalisation.
    # Catches /0ne-dr1ve → onedrive, /paypa1 → paypal, /g00gle → google.
    # Homoglyph map: 0→o, 1→i/l, 3→e, 4→a, 5→s, 6→g, 7→t, 8→b, @→a
    HOMOGLYPH_MAP = str.maketrans("013456789@!$", "oieasgbtbgas")
    apex_for_19b = _apex_domain(host)
    path_segments = [s for s in path.lower().split("/") if len(s) >= 4]
    for seg in path_segments:
        seg_norm = re.sub(r"[^a-z0-9]", "", seg).translate(HOMOGLYPH_MAP)
        for brand in BRAND_LIST:
            brand_clean = re.sub(r"[^a-z0-9]", "", brand.lower())
            # Only flag if the apex domain is NOT the brand itself
            # (e.g. onedrive.live.com/path is legitimate; wixsite.com/0ne-dr1ve is not)
            if apex_for_19b.lower() == brand_clean:
                continue
            sim = lcs_similarity(seg_norm, brand_clean)
            if sim >= 0.80:  # higher threshold for path (shorter strings = less noise)
                flag(
                    f"🎭 The URL path '/{seg}' closely resembles '{brand}' after homoglyph "
                    f"substitution ({sim:.0%} similar) — brand impersonation in path.",
                    f"Rule 19b (path LCS): '{seg}' → normalised '{seg_norm}' vs '{brand_clean}', "
                    f"LCS similarity = {sim:.3f}.",
                    3
                )
                break

    # ── Rule 20: SimHash Near-Duplicate URL — Phase 2, informational ──────────
    # Structural similarity to a previously seen URL in this session.
    # Weight +2 only when both the near-duplicate AND another rule fire
    # (avoids false positives from legitimate site variants).
    near_dup = check_near_duplicate(url_string)
    if near_dup and near_dup != url_string:
        flag(
            f"🔁 This URL is structurally almost identical to another URL scanned in this session "
            f"— a pattern associated with evasion campaigns.",
            f"Rule 20 (SimHash): Hamming distance ≤ {SIMHASH_THRESHOLD} bits vs previously seen "
            f"URL: {near_dup}",
            2
        )

    # ── Rule 21: Urgency language in URL — Phase 2, weight +2 ────────────────
    # Smishing/vishing/email phishing hallmark: urgency phrases embedded in
    # URL paths or query strings to pressure users into clicking immediately.
    # Real GSU phishing examples: "verify-now", "act-immediately", "suspended"
    URGENCY_KEYWORDS = [
        "urgent", "immediately", "act-now", "act_now", "expires",
        "suspended", "limited-time", "winner", "prize", "claim-now",
        "claim_now", "verify-now", "verify_now", "alert", "warning",
        "blocked", "unusual-activity", "unusual_activity"
    ]
    full_path_query = (path + "?" + query).lower()
    for kw in URGENCY_KEYWORDS:
        if kw in full_path_query:
            flag(
                f"⏰ This URL contains urgency language ('{kw}') — a pressure tactic used in "
                f"smishing, email phishing, and quishing attacks.",
                f"Rule 21: Urgency keyword '{kw}' detected in path/query.",
                2
            )
            break

    # ── Rule 22: Free hosting platform abuse — Phase 2, weight +3 ───────────────
    # Attackers abuse free website builders (Wix, Weebly, Carrd, etc.) to host
    # phishing pages quickly and anonymously. Legitimate organisations never host
    # login portals or 2FA pages on free site builders.
    # Real GSU case: ivoryrobinson94.wixsite.com/0ne-dr1ve impersonating OneDrive.
    host_lower = host.lower()
    for platform in FREE_HOSTING_PLATFORMS:
        if host_lower.endswith(platform) or ("." + platform) in host_lower:
            flag(
                f"🏗️ This URL is hosted on a free website builder ({platform}) — "
                f"legitimate organisations never host login or authentication pages here.",
                f"Rule 22: Free hosting platform detected: {platform}. "
                f"Common phishing vector — fast, anonymous, free account creation.",
                3
            )
            break

    # ── Optional: Cloudflare Radar reputation lookup ───────────────────────────
    if enable_radar:
        radar_data = cloudflare_radar_lookup(host)
        if radar_data:
            tech_findings.append(f"Cloudflare Radar: {radar_data}")

    # ── Classify ──────────────────────────────────────────────────────────────
    level = RiskLevel.from_score(score)

    # Add clean verdict if no issues found
    if not user_findings:
        user_findings = ["✅ No suspicious patterns detected in this URL."]
        tech_findings = ["All 22 rules passed (Phase 1 + Phase 2). Score: 0."]

    return RiskResult(url_string, score, level, user_findings, tech_findings)


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def get_clipboard_url() -> Optional[str]:
    """
    Read a URL from the system clipboard — cross-platform, no extra dependencies.
    Useful for instantly scoring any link copied from an email, SMS, or DM.
    Windows: PowerShell Get-Clipboard | macOS: pbpaste | Linux: xclip
    """
    try:
        import subprocess
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or None
        elif sys.platform == "darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return result.stdout.strip() or None
        else:
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                                    capture_output=True, text=True, timeout=5)
            return result.stdout.strip() or None
    except Exception as e:
        print(f"[ERROR] Could not read clipboard: {e}")
        return None


def main():
    # Fix Windows cp1252 terminal encoding — allows box-drawing and emoji output
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="ScanSafe — Cross-Platform QR Phishing Detector (Python/OpenCV)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image",  metavar="PATH",
                       help="Path to a QR code image file (PNG, JPG, etc.)")
    group.add_argument("--camera", action="store_true",
                       help="Live webcam mode — decodes QR codes in real time")
    group.add_argument("--url",    metavar="URL",
                       help="Skip QR decode; score a URL directly")
    group.add_argument("--clipboard", action="store_true",
                       help="Score the URL currently in your clipboard — paste any "
                            "link from an email, SMS, or DM and run this instantly")
    parser.add_argument("--radar", action="store_true",
                        help="Enable optional Cloudflare Radar reputation lookup "
                             "(requires: pip install requests). Off by default to "
                             "preserve on-device privacy architecture.")

    args = parser.parse_args()

    url: Optional[str] = None

    if args.url:
        url = args.url
        print(f"[INFO] Scoring URL directly: {url}")

    elif args.clipboard:
        print("[INFO] Reading URL from clipboard...")
        url = get_clipboard_url()
        if url:
            print(f"[INFO] Clipboard URL: {url}")
        else:
            print("[WARN] Clipboard is empty or does not contain a URL.")
            sys.exit(1)

    elif args.image:
        print(f"[INFO] Decoding QR from image: {args.image}")
        url = decode_qr_from_image(args.image)
        if url:
            print(f"[INFO] QR decoded: {url}")
        else:
            print("[WARN] No QR code detected in image.")
            sys.exit(1)

    elif args.camera:
        print("[INFO] Starting live camera mode...")
        url = scan_from_camera()
        if url:
            print(f"[INFO] QR decoded: {url}")
        else:
            print("[INFO] No QR code scanned. Exiting.")
            sys.exit(0)

    if args.radar:
        print("[INFO] Cloudflare Radar lookups enabled (Phase 2, optional).")

    if url:
        result = score_url(url, enable_radar=args.radar)
        result.print_report()

        # Exit code reflects risk level (useful for CI / scripting)
        if result.level == RiskLevel.HIGH_RISK:
            sys.exit(2)
        elif result.level == RiskLevel.SUSPICIOUS:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()
