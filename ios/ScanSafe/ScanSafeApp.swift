import SwiftUI

@main
struct ScanSafeApp: App {
    @StateObject private var historyStore = HistoryStore()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(historyStore)
                .preferredColorScheme(.dark)
        }
    }
}
