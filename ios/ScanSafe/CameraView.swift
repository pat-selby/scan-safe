import SwiftUI
import AVFoundation

struct CameraView: View {
    @ObservedObject var scanner: QRScanner
    @EnvironmentObject var historyStore: HistoryStore
    @State private var showResult = false
    @State private var bracketScale: CGFloat = 1.0
    
    var body: some View {
        ZStack {
            Color(hex: "#0A0A0A").ignoresSafeArea()
            
            CameraPreview(session: scanner.captureSession)
                .ignoresSafeArea()
            
            // Animated brackets
            VStack {
                HStack {
                    BracketView(angle: 0)
                    Spacer()
                    BracketView(angle: 90)
                }
                Spacer()
                HStack {
                    BracketView(angle: -90)
                    Spacer()
                    BracketView(angle: 180)
                }
            }
            .padding(40)
            .scaleEffect(bracketScale)
            .animation(Animation.easeInOut(duration: 1.5).repeatForever(autoreverses: true), value: bracketScale)
            .onAppear {
                bracketScale = 1.05
            }
            
            VStack {
                Spacer()
                
                HStack(spacing: 20) {
                    Button(action: {
                        scanner.simulateSafe()
                    }) {
                        Text("SIMULATE SAFE")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.black)
                            .padding()
                            .background(Color(hex: "#00FF9C"))
                            .cornerRadius(8)
                    }
                    
                    Button(action: {
                        scanner.simulatePhishing()
                    }) {
                        Text("SIMULATE PHISHING")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.white)
                            .padding()
                            .background(Color(hex: "#FF3B30"))
                            .cornerRadius(8)
                    }
                }
                .padding(.bottom, 30)
            }
        }
        .onAppear {
            scanner.startScanning()
        }
        .onDisappear {
            scanner.stopScanning()
        }
        .onChange(of: scanner.currentResult?.url) { _ in
            if let result = scanner.currentResult {
                historyStore.addResult(result)
                triggerHaptic(for: result.level)
                showResult = true
            }
        }
        .sheet(isPresented: $showResult, onDismiss: {
            scanner.reset()
        }) {
            if let result = scanner.currentResult {
                ResultView(result: result)
            }
        }
    }
    
    private func triggerHaptic(for level: RiskLevel) {
        let generator: UIImpactFeedbackGenerator
        switch level {
        case .highRisk:
            generator = UIImpactFeedbackGenerator(style: .heavy)
        case .suspicious:
            generator = UIImpactFeedbackGenerator(style: .medium)
        case .safe:
            generator = UIImpactFeedbackGenerator(style: .light)
        }
        generator.prepare()
        generator.impactOccurred()
    }
}

struct BracketView: View {
    let angle: Double
    
    var body: some View {
        Path { path in
            path.move(to: CGPoint(x: 0, y: 40))
            path.addLine(to: CGPoint(x: 0, y: 0))
            path.addLine(to: CGPoint(x: 40, y: 0))
        }
        .stroke(Color(hex: "#00FF9C"), lineWidth: 4)
        .frame(width: 40, height: 40)
        .rotationEffect(.degrees(angle))
    }
}

struct CameraPreview: UIViewControllerRepresentable {
    let session: AVCaptureSession
    
    func makeUIViewController(context: Context) -> UIViewController {
        let vc = UIViewController()
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        vc.view.layer.addSublayer(layer)
        
        DispatchQueue.main.async {
            layer.frame = vc.view.bounds
        }
        
        return vc
    }
    
    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {
        if let layer = uiViewController.view.layer.sublayers?.first as? AVCaptureVideoPreviewLayer {
            layer.frame = uiViewController.view.bounds
        }
    }
}
