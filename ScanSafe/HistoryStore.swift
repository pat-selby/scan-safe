import Foundation
import Combine
import SwiftUI

class HistoryStore: ObservableObject {
    @Published var history: [HistoryItem] = []
    
    private let maxItems = 50
    private let historyKey = "ScanSafeHistory"
    
    init() {
        loadHistory()
    }
    
    func addResult(_ result: RiskResult) {
        let item = HistoryItem(
            url: result.url,
            score: result.score,
            level: result.level,
            reasons: result.reasons,
            userFindings: result.userFindings,
            techFindings: result.techFindings,
            timestamp: Date()
        )
        
        history.insert(item, at: 0)
        
        if history.count > maxItems {
            history = Array(history.prefix(maxItems))
        }
        
        saveHistory()
    }
    
    func deleteItems(at offsets: IndexSet) {
        history.remove(atOffsets: offsets)
        saveHistory()
    }
    
    func clearAll() {
        history.removeAll()
        saveHistory()
    }
    
    private func saveHistory() {
        if let encoded = try? JSONEncoder().encode(history) {
            UserDefaults.standard.set(encoded, forKey: historyKey)
        }
    }
    
    private func loadHistory() {
        if let data = UserDefaults.standard.data(forKey: historyKey),
           let decoded = try? JSONDecoder().decode([HistoryItem].self, from: data) {
            self.history = decoded
        }
    }
}
