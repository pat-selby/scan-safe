import Foundation

class URLRiskScorer {
    
    struct Finding {
        let userMessage: String
        let techMessage: String
    }
    
    func scoreURL(_ urlString: String) -> RiskResult {
        var score = 0
        var findings: [Finding] = []
        
        let lowerURL = urlString.lowercased()
        let validURLString = lowerURL.hasPrefix("http") ? lowerURL : "https://\(lowerURL)"
        
        guard let url = URL(string: validURLString), let host = url.host else {
            return RiskResult(
                url: urlString,
                score: 0,
                level: .safe,
                reasons: ["Could not parse URL."],
                userFindings: ["⚠️ This URL could not be read properly. Do not open it."],
                techFindings: ["URL parsing failed — malformed or non-standard format."]
            )
        }
        
        // 1. IP address
        let ipRegex = "^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$"
        if host.range(of: ipRegex, options: .regularExpression) != nil {
            score += 3
            findings.append(Finding(
                userMessage: "🔴 This link goes to a raw number address (\(host)), not a real website name. Legitimate companies like your bank or Amazon never do this — attackers use IP addresses to hide who they are.",
                techMessage: "Direct IP address detected in host field: \(host). Legitimate services resolve to named domains. IP-based URLs bypass domain reputation checks."
            ))
        }
        
        // 2. Brand substitution
        let brandSubstitutions: [String: String] = [
            "paypa1": "PayPal", "amaz0n": "Amazon", "g00gle": "Google",
            "faceb00k": "Facebook", "micr0s0ft": "Microsoft", "app1e": "Apple"
        ]
        for (fake, real) in brandSubstitutions {
            if lowerURL.contains(fake) {
                score += 3
                findings.append(Finding(
                    userMessage: "🔴 This URL is pretending to be \(real) by swapping a letter for a number — \"\(fake)\" instead of the real spelling. This is a classic trick to make you think you're on a trusted site.",
                    techMessage: "Brand homoglyph substitution detected: \"\(fake)\" mimics \"\(real.lowercased())\". Character substitution (letter→digit) used to evade exact-match domain filters."
                ))
                break
            }
        }
        
        // 3. HTTP not HTTPS
        if validURLString.hasPrefix("http://") {
            score += 2
            findings.append(Finding(
                userMessage: "🟡 This link is not encrypted. Any password or personal information you enter on this page can be intercepted by anyone on the same network — like public WiFi.",
                techMessage: "Protocol is http:// — no TLS/SSL layer. Data transmitted in plaintext. Susceptible to MITM interception. All modern legitimate services enforce HTTPS."
            ))
        }
        
        // 4. Subdomain count > 4
        let components = host.split(separator: ".")
        if components.count > 4 {
            score += 2
            findings.append(Finding(
                userMessage: "🟡 This web address has an unusually long structure (\(host)). Legitimate websites keep their addresses short and simple. Attackers add extra layers to make fake sites look more official.",
                techMessage: "Subdomain depth \(components.count) exceeds threshold of 4 components in host: \(host). Deep subdomain nesting is a common phishing infrastructure pattern."
            ))
        }
        
        // 5. Path length > 50
        let path = url.path
        if path.count > 50 {
            score += 1
            findings.append(Finding(
                userMessage: "🟡 The path in this URL is unusually long (\(path.count) characters). Attackers use long, complex paths to hide what a link actually does or to bypass security filters.",
                techMessage: "URL path length \(path.count) chars exceeds 50-char threshold. Long paths are used to bury malicious parameters or confuse pattern-matching security tools."
            ))
        }
        
        // 6. Consonant ratio > 0.75
        let domainOnly = host.replacingOccurrences(of: ".", with: "")
        let letters = domainOnly.filter { $0.isLetter }
        let totalLetters = letters.count
        if totalLetters > 0 {
            let pureVowels: Set<Character> = ["a", "e", "i", "o", "u"]
            let consonants = letters.filter { !pureVowels.contains($0) }.count
            let ratio = Double(consonants) / Double(totalLetters)
            if ratio > 0.75 {
                score += 1
                findings.append(Finding(
                    userMessage: "🟡 The domain name \"\(host)\" looks like it was randomly generated — it's mostly consonants with no real word pattern. Attackers use auto-generated domains because they're cheap and disposable.",
                    techMessage: "Consonant ratio \(String(format: "%.2f", ratio)) in domain \(host) exceeds 0.75 threshold. High consonant density is a statistical marker of algorithmically generated domains (DGAs)."
                ))
            }
        }
        
        // 7. URL shortener
        let shorteners = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly"]
        for shortener in shorteners {
            if host.contains(shortener) {
                score += 3
                findings.append(Finding(
                    userMessage: "🔴 This is a shortened link from \(shortener) — it completely hides where it actually takes you. Attackers use URL shorteners specifically so you cannot see the real destination before tapping.",
                    techMessage: "URL shortener service detected: \(shortener). Shorteners mask the true destination URL, bypassing visual domain inspection and many URL-reputation lookups."
                ))
                break
            }
        }
        
        // 8. Suspicious path keywords
        let suspiciousKeywords = ["verify", "confirm", "secure", "login", "update", "account", "password", "signin"]
        var foundKeyword: String? = nil
        for keyword in suspiciousKeywords {
            if url.path.lowercased().contains(keyword) {
                foundKeyword = keyword
                break
            }
        }
        if foundKeyword == nil {
            for keyword in suspiciousKeywords {
                if host.lowercased().contains(keyword) {
                    foundKeyword = keyword
                    break
                }
            }
        }
        if let keyword = foundKeyword {
            score += 2
            findings.append(Finding(
                userMessage: "🟡 This URL contains the word \"\(keyword)\" — a word commonly used in phishing pages designed to steal your credentials. Legitimate sites rarely put words like this directly in their links.",
                techMessage: "High-risk keyword \"\(keyword)\" detected in URL path/host. Keywords like verify, login, confirm, and password are strongly associated with credential harvesting pages."
            ))
        }
        
        // 9. Free hosting
        let freeHosts = ["000webhostapp", "weebly", "wixsite", "wix.", "firebaseapp", "netlify", "github.io", "glitch.me", "herokuapp", "pages.dev"]
        for freeHost in freeHosts {
            if host.contains(freeHost) {
                score += 2
                findings.append(Finding(
                    userMessage: "🟡 This website is hosted on \"\(freeHost)\", a free hosting platform. Your bank, employer, or any serious company would never use a free website builder to send you a link. Attackers use these because they're free, fast, and easy to abandon.",
                    techMessage: "Free hosting provider identified in host: \(host) matches pattern \"\(freeHost)\". Free platforms are heavily abused in phishing due to low barrier to entry and disposable infrastructure."
                ))
                break
            }
        }
        
        // 10. Punycode
        if host.contains("xn--") {
            score += 3
            findings.append(Finding(
                userMessage: "🔴 This URL uses a disguised international character to impersonate a real website. For example, the letter \"a\" might actually be a visually identical character from another language. You cannot tell the difference just by looking.",
                techMessage: "Punycode encoding detected in host: \(host). ACE prefix \"xn--\" indicates internationalized domain name (IDN). Commonly used in homograph attacks to spoof trusted domains using visually identical Unicode characters."
            ))
        }
        
        // 11. Excessive hyphens
        let hyphenCount = host.filter({ $0 == "-" }).count
        if hyphenCount > 2 {
            score += 2
            findings.append(Finding(
                userMessage: "🟡 This domain has \(hyphenCount) hyphens in it (\(host)). Real company websites rarely use more than one hyphen. Attackers use extra hyphens to squeeze in recognizable brand names while using a different domain.",
                techMessage: "Hyphen count \(hyphenCount) in domain \(host) exceeds threshold of 2. Hyphen abuse is used to construct plausible-looking domains such as secure-paypal-login.com that pass casual inspection."
            ))
        }
        
        // 12. Numeric characters in domain
        if host.rangeOfCharacter(from: CharacterSet.decimalDigits) != nil &&
           host.range(of: ipRegex, options: .regularExpression) == nil {
            score += 1
            findings.append(Finding(
                userMessage: "🟡 The domain name \"\(host)\" contains numbers. Most legitimate websites don't mix numbers into their domain names — this can be a sign of a spoofed or auto-generated domain.",
                techMessage: "Numeric characters detected in domain: \(host). Digits in domain names (excluding IP addresses) are statistically associated with phishing and DGA domains."
            ))
        }
        
        // Determine level
        let level: RiskLevel
        if score <= 2 {
            level = .safe
        } else if score <= 5 {
            level = .suspicious
        } else {
            level = .highRisk
        }
        
        // Build legacy reasons array for history/share compatibility
        let reasons = findings.isEmpty
            ? ["No suspicious indicators found."]
            : findings.map { $0.techMessage }
        
        let userFindings = findings.isEmpty
            ? ["✅ No suspicious patterns detected in this URL."]
            : findings.map { $0.userMessage }
        
        let techFindings = findings.isEmpty
            ? [""]
            : findings.map { $0.techMessage }
        
        return RiskResult(
            url: urlString,
            score: score,
            level: level,
            reasons: reasons,
            userFindings: userFindings,
            techFindings: techFindings
        )
    }
}
