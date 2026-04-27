import SwiftUI

struct ResultView: View {
    let result: RiskResult
    @Environment(\.presentationMode) var presentationMode
    
    @State private var circleScale: CGFloat = 0.0
    @State private var textOpacity: Double = 0.0
    
    var body: some View {
        ZStack {
            Color(hex: "#0A0A0A").ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 24) {
                    
                    // Close button
                    HStack {
                        Spacer()
                        Button(action: {
                            presentationMode.wrappedValue.dismiss()
                        }) {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 30))
                                .foregroundColor(.white.opacity(0.8))
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 20)
                    
                    // Verdict Circle
                    ZStack {
                        Circle()
                            .stroke(result.level.color, lineWidth: 8)
                            .frame(width: 200, height: 200)
                        
                        Circle()
                            .fill(result.level.color.opacity(0.2))
                            .frame(width: 200, height: 200)
                        
                        VStack {
                            Image(systemName: result.level == .safe ? "checkmark.shield.fill" : (result.level == .suspicious ? "exclamationmark.triangle.fill" : "xmark.shield.fill"))
                                .font(.system(size: 60))
                                .foregroundColor(result.level.color)
                                .padding(.bottom, 8)
                            
                            Text(result.level.title)
                                .font(.system(size: 24, weight: .bold))
                                .foregroundColor(result.level.color)
                        }
                    }
                    .scaleEffect(circleScale)
                    .onAppear {
                        withAnimation(.spring(response: 0.6, dampingFraction: 0.7, blendDuration: 0)) {
                            circleScale = 1.0
                        }
                        withAnimation(.easeIn(duration: 0.5).delay(0.5)) {
                            textOpacity = 1.0
                        }
                    }
                    
                    // Risk Score
                    Text("Risk Score: \(result.score)")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                    
                    // URL
                    Text(result.url)
                        .font(.body)
                        .foregroundColor(.gray)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                        .onLongPressGesture {
                            UIPasteboard.general.string = result.url
                        }
                    
                    // Findings
                    if !result.userFindings.isEmpty {
                        VStack(alignment: .leading, spacing: 16) {
                            Text("Findings:")
                                .font(.headline)
                                .foregroundColor(.white)
                            
                            ForEach(Array(zip(result.userFindings, result.techFindings).enumerated()), id: \.offset) { index, pair in
                                FindingRow(
                                    userMessage: pair.0,
                                    techMessage: pair.1,
                                    accentColor: result.level.color
                                )
                            }
                        }
                        .padding()
                        .background(Color.white.opacity(0.05))
                        .cornerRadius(12)
                        .padding(.horizontal)
                    }
                    
                    // Share Button
                    ShareLink(item: "ScanSafe Result: \(result.level.title) | Score: \(result.score) | URL: \(result.url) | Findings: \(result.reasons.joined(separator: ", "))") {
                        HStack {
                            Image(systemName: "square.and.arrow.up")
                            Text("Share Result")
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(result.level.color)
                        .cornerRadius(12)
                        .padding(.horizontal)
                    }
                    .padding(.bottom, 40)
                }
            }
        }
    }
}

// MARK: - Finding Row

struct FindingRow: View {
    let userMessage: String
    let techMessage: String
    let accentColor: Color
    
    @State private var expanded: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            
            // Plain English — always visible
            HStack(alignment: .top, spacing: 8) {
                Text(userMessage)
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.95))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .multilineTextAlignment(.leading)
                    .lineLimit(nil)
            }
            
            // See details toggle
            if !techMessage.isEmpty {
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.25)) {
                        expanded.toggle()
                    }
                }) {
                    HStack(spacing: 4) {
                        Text(expanded ? "Hide details" : "See details")
                            .font(.caption)
                            .foregroundColor(accentColor)
                        Image(systemName: expanded ? "chevron.up" : "chevron.down")
                            .font(.caption2)
                            .foregroundColor(accentColor)
                    }
                }
                
                // Technical detail — shown when expanded
                if expanded {
                    Text(techMessage)
                        .font(.caption)
                        .foregroundColor(.gray)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .multilineTextAlignment(.leading)
                        .lineLimit(nil)
                        .padding(.top, 2)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            
            Divider()
                .background(Color.white.opacity(0.1))
        }
    }
}
