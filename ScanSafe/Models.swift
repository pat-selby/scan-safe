import Foundation
import SwiftUI

enum RiskLevel: String, Codable {
    case safe = "GREEN"
    case suspicious = "YELLOW"
    case highRisk = "RED"
    
    var color: Color {
        switch self {
        case .safe: return Color(hex: "#00FF9C")
        case .suspicious: return Color(hex: "#FFD60A")
        case .highRisk: return Color(hex: "#FF3B30")
        }
    }
    
    var title: String {
        switch self {
        case .safe: return "SAFE"
        case .suspicious: return "SUSPICIOUS"
        case .highRisk: return "HIGH RISK"
        }
    }
}

struct RiskResult: Codable {
    let url: String
    let score: Int
    let level: RiskLevel
    let reasons: [String]
    let userFindings: [String]
    let techFindings: [String]
}

struct HistoryItem: Codable, Identifiable {
    let id: UUID
    let url: String
    let score: Int
    let level: RiskLevel
    let reasons: [String]
    let userFindings: [String]
    let techFindings: [String]
    let timestamp: Date
    
    init(id: UUID = UUID(), url: String, score: Int, level: RiskLevel, reasons: [String], userFindings: [String], techFindings: [String], timestamp: Date) {
        self.id = id
        self.url = url
        self.score = score
        self.level = level
        self.reasons = reasons
        self.userFindings = userFindings
        self.techFindings = techFindings
        self.timestamp = timestamp
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
