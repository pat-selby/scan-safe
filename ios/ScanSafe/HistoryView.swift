import SwiftUI

struct HistoryView: View {
    @EnvironmentObject var historyStore: HistoryStore
    
    var body: some View {
        NavigationView {
            ZStack {
                Color(hex: "#0A0A0A").ignoresSafeArea()
                
                if historyStore.history.isEmpty {
                    VStack {
                        Image(systemName: "tray")
                            .font(.system(size: 50))
                            .foregroundColor(.gray)
                            .padding(.bottom, 10)
                        Text("No scan history yet")
                            .foregroundColor(.gray)
                    }
                } else {
                    List {
                        ForEach(historyStore.history) { item in
                            HStack(spacing: 15) {
                                Circle()
                                    .fill(item.level.color)
                                    .frame(width: 12, height: 12)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.url)
                                        .font(.system(size: 16, weight: .semibold))
                                        .foregroundColor(.white)
                                        .lineLimit(1)
                                        .truncationMode(.tail)
                                    
                                    HStack {
                                        Text("Score: \(item.score)")
                                        Spacer()
                                        Text(Self.formatter.string(from: item.timestamp))
                                    }
                                    .font(.system(size: 12))
                                    .foregroundColor(.gray)
                                }
                            }
                            .padding(.vertical, 4)
                            .listRowBackground(Color(hex: "#0A0A0A"))
                        }
                        .onDelete(perform: historyStore.deleteItems)
                    }
                    .listStyle(PlainListStyle())
                }
            }
            .navigationTitle("Scan History")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if !historyStore.history.isEmpty {
                        Button("Clear All") {
                            historyStore.clearAll()
                        }
                        .foregroundColor(Color(hex: "#FF3B30"))
                    }
                }
            }
        }
        .accentColor(.white)
        .onAppear {
            let navBarAppearance = UINavigationBarAppearance()
            navBarAppearance.configureWithOpaqueBackground()
            navBarAppearance.backgroundColor = UIColor(Color(hex: "#0A0A0A"))
            navBarAppearance.titleTextAttributes = [.foregroundColor: UIColor.white]
            UINavigationBar.appearance().standardAppearance = navBarAppearance
            UINavigationBar.appearance().scrollEdgeAppearance = navBarAppearance
        }
    }
    
    static let formatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter
    }()
}
