import Foundation

class URLRiskScorer {
    
    func scoreURL(_ urlString: String) -> RiskResult {
        var score = 0
        var reasons: [String] = []
        
        let lowerURL = urlString.lowercased()
        
        let validURLString = lowerURL.hasPrefix("http") ? lowerURL : "https://\(lowerURL)"
        guard let url = URL(string: validURLString), let host = url.host else {
            return RiskResult(url: urlString, score: 0, level: .safe, reasons: ["Could not parse URL properly."])
        }
        
        // 1. IP address
        let ipRegex = "^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$"
        if host.range(of: ipRegex, options: .regularExpression) != nil {
            score += 3
            reasons.append("Legitimate services use domain names (IP address detected)")
        }
        
        // 2. Brand substitution
        let brandSubstitutions = ["paypa1", "amaz0n", "g00gle", "faceb00k", "micr0s0ft", "app1e"]
        for brand in brandSubstitutions {
            if lowerURL.contains(brand) {
                score += 3
                reasons.append("Classic phishing pattern (brand name substitution)")
                break
            }
        }
        
        // 3. HTTP not HTTPS
        if validURLString.hasPrefix("http://") {
            score += 2
            reasons.append("No transport encryption (HTTP used)")
        }
        
        // 4. Subdomain count > 3
        let components = host.split(separator: ".")
        if components.count > 4 {
            score += 2
            reasons.append("Common in phishing infrastructure (too many subdomains)")
        }
        
        // 5. Path length > 50
        let path = url.path
        if path.count > 50 {
            score += 1
            reasons.append("Obfuscation indicator (long path)")
        }
        
        // 6. Consonant ratio > 0.75 in domain
        let domainOnly = host.replacingOccurrences(of: ".", with: "")
        let letters = domainOnly.filter { $0.isLetter }
        let totalLetters = letters.count
        if totalLetters > 0 {
            let pureVowels: Set<Character> = ["a", "e", "i", "o", "u"]
            let consonants = letters.filter { !pureVowels.contains($0) }.count
            let ratio = Double(consonants) / Double(totalLetters)
            if ratio > 0.75 {
                score += 1
                reasons.append("Generated domain pattern (high consonant ratio)")
            }
        }
        
        // 7. URL shortener
        let shorteners = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly"]
        for shortener in shorteners {
            if host.contains(shortener) {
                score += 3
                reasons.append("URL shortener hides true destination")
                break
            }
        }
        
        // 8. Suspicious path keywords
        let suspiciousKeywords = ["verify", "confirm", "secure", "login", "update", "account", "password", "signin"]
        var foundKeyword = false
        for keyword in suspiciousKeywords {
            if url.path.lowercased().contains(keyword) {
                score += 2
                reasons.append("Suspicious keywords in URL path (\(keyword))")
                foundKeyword = true
                break
            }
        }
        if !foundKeyword {
            for keyword in suspiciousKeywords {
                if host.lowercased().contains(keyword) {
                    score += 2
                    reasons.append("Suspicious keywords in domain (\(keyword))")
                    break
                }
            }
        }
        
        // 9. Free hosting — expanded to catch wixsite, weebly subdomains etc.
        let freeHosts = ["000webhostapp", "weebly", "wixsite", "wix.", "firebaseapp", "netlify", "github.io", "glitch.me", "herokuapp", "pages.dev"]
        for freeHost in freeHosts {
            if host.contains(freeHost) {
                score += 2
                reasons.append("Free hosting platform (common in phishing)")
                break
            }
        }
        
        // 10. Punycode (xn--)
        if host.contains("xn--") {
            score += 3
            reasons.append("Internationalized domain spoofing detected")
        }
        
        // 11. Excessive hyphens > 2 in domain
        if host.filter({ $0 == "-" }).count > 2 {
            score += 2
            reasons.append("Hyphen abuse common in phishing domains")
        }
        
        // 12. Numeric characters in domain (excluding IP addresses)
        if host.rangeOfCharacter(from: CharacterSet.decimalDigits) != nil &&
           host.range(of: ipRegex, options: .regularExpression) == nil {
            score += 1
            reasons.append("Numbers in domain may indicate spoofing")
        }
        
        let level: RiskLevel
        if score <= 2 {
            level = .safe
        } else if score <= 5 {
            level = .suspicious
        } else {
            level = .highRisk
        }
        
        if reasons.isEmpty {
            reasons.append("No suspicious indicators found.")
        }
        
        return RiskResult(url: urlString, score: score, level: level, reasons: reasons)
    }
}
