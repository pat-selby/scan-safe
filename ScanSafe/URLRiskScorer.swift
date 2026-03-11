import Foundation

struct URLRiskScorer {
    static func evaluate(url: String) -> RiskResult {
        var score = 0
        var reasons: [String] = []
        
        let lowerUrl = url.lowercased()
        
        // Rule 1: IP address instead of domain (+3)
        // "Legitimate services use domain names (IP address detected)"
        if let host = URL(string: url)?.host, isIPAddress(host) {
            score += 3
            reasons.append("Legitimate services use domain names (IP address detected)")
        } else {
            let ipPattern = "^(http[s]?://)?([0-9]{1,3}\\.){3}[0-9]{1,3}"
            if url.range(of: ipPattern, options: .regularExpression) != nil {
                score += 3
                reasons.append("Legitimate services use domain names (IP address detected)")
            }
        }
        
        // Rule 2: Brand substitution (+3)
        // "Classic phishing pattern (brand name substitution)"
        let phishBrands = ["paypa1", "amaz0n", "g00gle", "faceb00k", "micr0s0ft", "app1e"]
        var brandFired = false
        for brand in phishBrands {
            if lowerUrl.contains(brand) {
                brandFired = true
                break
            }
        }
        if brandFired {
            score += 3
            reasons.append("Classic phishing pattern (brand name substitution)")
        }
        
        // Rule 3: HTTP instead of HTTPS (+2)
        // "No transport encryption (HTTP used)"
        if lowerUrl.starts(with: "http://") {
            score += 2
            reasons.append("No transport encryption (HTTP used)")
        }
        
        // Rule 4: Subdomain count > 3 (+2)
        // "Common in phishing infrastructure (too many subdomains)"
        if let host = URL(string: url)?.host {
            let parts = host.split(separator: ".")
            if parts.count > 4 {
                score += 2
                reasons.append("Common in phishing infrastructure (too many subdomains)")
            }
        }
        
        // Rule 5: Path length > 50 chars (+1)
        // "Obfuscation indicator (long path)"
        if let parts = URL(string: url), let path = parts.path.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)?.removingPercentEncoding {
            if parts.path.count > 50 {
                score += 1
                reasons.append("Obfuscation indicator (long path)")
            }
        } else if let path = url.components(separatedBy: "?").first, path.count > 100 {
            if url.count > 50 && !url.contains("?") && url.components(separatedBy: "/").dropFirst(3).joined(separator: "/").count > 50 {
                score += 1
                reasons.append("Obfuscation indicator (long path)")
            }
        }
        
        // Rule 6: Consonant ratio in domain > 0.75 (+1)
        // "Generated domain pattern (high consonant ratio)"
        if let host = URL(string: url)?.host {
            let domainOnly = host.replacingOccurrences(of: ".", with: "")
            let lettersOnly = domainOnly.filter { $0.isLetter }
            if !lettersOnly.isEmpty {
                let vowels: Set<Character> = ["a", "e", "i", "o", "u"]
                let consonantCount = lettersOnly.filter { !vowels.contains($0) }.count
                let ratio = Double(consonantCount) / Double(lettersOnly.count)
                if ratio > 0.75 {
                    score += 1
                    reasons.append("Generated domain pattern (high consonant ratio)")
                }
            }
        }
        
        let finalVerdict: Verdict
        if score <= 2 {
            finalVerdict = .GREEN
        } else if score <= 5 {
            finalVerdict = .YELLOW
        } else {
            finalVerdict = .RED
        }
        
        let finalReason = score == 0 ? "Safe URL" : reasons.joined(separator: " • ")
        
        return RiskResult(score: score, verdict: finalVerdict, reason: finalReason)
    }
    
    private static func isIPAddress(_ string: String) -> Bool {
        let parts = string.split(separator: ".")
        guard parts.count == 4 else { return false }
        for part in parts {
            guard let num = Int(part), num >= 0 && num <= 255 else { return false }
        }
        return true
    }
}
