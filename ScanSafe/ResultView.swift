import SwiftUI

struct ResultView: View {
    let result: RiskResult
    @Environment(\.presentationMode) var presentationMode
    
    @State private var circleScale: CGFloat = 0.0
    @State private var textOpacity: Double = 0.0
    
    var body: some View {
        ZStack {
            Color(hex: "#0A0A0A").ignoresSafeArea()
            
            VStack(spacing: 30) {
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
                .padding()
                
                Spacer()
                
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
                            .font(.system(size: 24, weight: .bold, design: .default))
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
                
                VStack(spacing: 20) {
                    Text("Risk Score: \(result.score)")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                    
                    Text(result.url)
                        .font(.body)
                        .foregroundColor(.gray)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                        .onLongPressGesture {
                            UIPasteboard.general.string = result.url
                        }
                    
                    if !result.reasons.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Findings:")
                                .font(.headline)
                                .foregroundColor(.white)
                            
                            ScrollView {
                                VStack(alignment: .leading, spacing: 10) {
                                    ForEach(result.reasons, id: \.self) { reason in
                                        HStack(alignment: .top) {
                                            Image(systemName: "info.circle")
                                                .foregroundColor(result.level.color)
                                            Text(reason)
                                                .font(.subheadline)
                                                .foregroundColor(.white.opacity(0.9))
                                                .fixedSize(horizontal: false, vertical: true)
                                        }
                                    }
                                }
                            }
                            .frame(maxHeight: 150)
                        }
                        .padding()
                        .background(Color.white.opacity(0.05))
                        .cornerRadius(12)
                        .padding(.horizontal)
                    }
                }
                .opacity(textOpacity)
                
                Spacer()
                
                ShareLink(item: "ScanSafe Result: \(result.level.title) | Score: \(result.score) | URL: \(result.url) | Reason: \(result.reasons.first ?? "N/A")") {
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
                .padding(.bottom, 20)
                .opacity(textOpacity)
            }
        }
    }
}
