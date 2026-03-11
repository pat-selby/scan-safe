import SwiftUI
import AVFoundation

struct CameraView: View {
    @StateObject private var qrScanner = QRScanner()
    
    var body: some View {
        ZStack {
            if let result = qrScanner.currentResult, let url = qrScanner.currentURL {
                ResultView(result: result, scannedURL: url) {
                    qrScanner.reset()
                }
            } else {
                CameraPreview(scanner: qrScanner)
                    .edgesIgnoringSafeArea(.all)
                
                VStack {
                    HStack {
                        Button(action: {
                            qrScanner.simulate(url: "https://www.google.com")
                        }) {
                            Text("SIMULATE GOOGLE (SAFE)")
                                .font(.caption)
                                .padding()
                                .background(Color.green.opacity(0.8))
                                .foregroundColor(.white)
                                .cornerRadius(8)
                        }
                        
                        Button(action: {
                            qrScanner.simulate(url: "http://paypa1-secure.com/login/verify")
                        }) {
                            Text("SIMULATE PAYPAL PHISH (MALICIOUS)")
                                .font(.caption)
                                .padding()
                                .background(Color.red.opacity(0.8))
                                .foregroundColor(.white)
                                .cornerRadius(8)
                        }
                    }
                    .padding()
                    Spacer()
                }
            }
        }
    }
}

struct CameraPreview: UIViewRepresentable {
    let scanner: QRScanner
    
    func makeUIView(context: Context) -> CameraPreviewView {
        let view = CameraPreviewView(scanner: scanner)
        return view
    }
    
    func updateUIView(_ uiView: CameraPreviewView, context: Context) {}
}

class CameraPreviewView: UIView {
    private var captureSession: AVCaptureSession?
    private var videoPreviewLayer: AVCaptureVideoPreviewLayer?
    private let scanner: QRScanner
    
    init(scanner: QRScanner) {
        self.scanner = scanner
        super.init(frame: .zero)
        setupCamera()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    private func setupCamera() {
        let session = AVCaptureSession()
        session.sessionPreset = .high
        
        guard let captureDevice = AVCaptureDevice.default(for: .video) else { return }
        guard let input = try? AVCaptureDeviceInput(device: captureDevice) else { return }
        
        if session.canAddInput(input) {
            session.addInput(input)
        }
        
        let videoOutput = AVCaptureVideoDataOutput()
        videoOutput.setSampleBufferDelegate(scanner, queue: DispatchQueue(label: "videoQueue"))
        if session.canAddOutput(videoOutput) {
            session.addOutput(videoOutput)
        }
        
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        self.layer.addSublayer(previewLayer)
        self.videoPreviewLayer = previewLayer
        
        self.captureSession = session
        
        DispatchQueue.global(qos: .userInitiated).async {
            session.startRunning()
        }
    }
    
    override func layoutSubviews() {
        super.layoutSubviews()
        videoPreviewLayer?.frame = self.bounds
    }
}
