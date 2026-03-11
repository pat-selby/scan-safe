import SwiftUI

struct ResultView: View {
    let result: RiskResult
    let scannedURL: String
    let onScanAgain: () -> Void
    
    var color: Color {
        switch result.verdict {
        case .GREEN: return Color(hex: "#2ECC71")
        case .YELLOW: return Color(hex: "#F39C12")
        case .RED: return Color(hex: "#E74C3C")
        }
    }
    
    var verdictText: String {
        switch result.verdict {
        case .GREEN: return "SAFE"
        case .YELLOW: return "SUSPICIOUS"
        case .RED: return "HIGH RISK"
        }
    }
    
    var body: some View {
        VStack(spacing: 30) {
            Spacer()
            
            // Large colored circle with verdict
            ZStack {
                Circle()
                    .fill(color)
                    .frame(width: 250, height: 250)
                    .shadow(radius: 10)
                
                Text(verdictText)
                    .font(.system(size: 32, weight: .bold))
                    .foregroundColor(.white)
            }
            
            // Reason below
            Text(result.reason)
                .font(.headline)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            // Scanned URL
            Text(scannedURL)
                .font(.subheadline)
                .foregroundColor(.gray)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
                .lineLimit(4)
            
            Spacer()
            
            // Scan Again button
            Button(action: onScanAgain) {
                Text("Scan Again")
                    .font(.title3.bold())
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .cornerRadius(12)
                    .padding(.horizontal, 40)
            }
            .padding(.bottom, 40)
        }
        .background(Color(.systemBackground).edgesIgnoringSafeArea(.all))
    }
}

extension Color {
    init(hex: String) {
        var cleanHexCode = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        cleanHexCode = cleanHexCode.replacingOccurrences(of: "#", with: "")
        var rgb: UInt64 = 0
        Scanner(string: cleanHexCode).scanHexInt64(&rgb)
        let redValue = Double((rgb >> 16) & 0xFF) / 255.0
        let greenValue = Double((rgb >> 8) & 0xFF) / 255.0
        let blueValue = Double(rgb & 0xFF) / 255.0
        self.init(red: redValue, green: greenValue, blue: blueValue)
    }
}
