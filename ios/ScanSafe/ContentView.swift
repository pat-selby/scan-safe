import SwiftUI

struct ContentView: View {
    @StateObject private var scanner = QRScanner()
    @EnvironmentObject var historyStore: HistoryStore
    
    init() {
        let appearance = UITabBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor(Color(hex: "#0A0A0A"))
        
        appearance.stackedLayoutAppearance.normal.iconColor = UIColor.gray
        appearance.stackedLayoutAppearance.normal.titleTextAttributes = [.foregroundColor: UIColor.gray]
        
        appearance.stackedLayoutAppearance.selected.iconColor = UIColor(Color(hex: "#00FF9C"))
        appearance.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: UIColor(Color(hex: "#00FF9C"))]
        
        UITabBar.appearance().standardAppearance = appearance
        if #available(iOS 15.0, *) {
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
    }
    
    var body: some View {
        TabView {
            CameraView(scanner: scanner)
                .tabItem {
                    Label("Scan", systemImage: "qrcode.viewfinder")
                }
            
            HistoryView()
                .tabItem {
                    Label("History", systemImage: "clock.fill")
                }
        }
        .accentColor(Color(hex: "#00FF9C"))
    }
}
