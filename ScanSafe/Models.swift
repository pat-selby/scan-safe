import Foundation

enum Verdict {
    case GREEN
    case YELLOW
    case RED
}

struct RiskResult {
    let score: Int
    let verdict: Verdict
    let reason: String
}
