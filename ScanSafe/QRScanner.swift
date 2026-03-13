import Foundation
import AVFoundation
import Vision
import Combine

#if canImport(OpenCV)
import OpenCV
#else
import opencv2
#endif

class QRScanner: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    @Published var currentResult: RiskResult?
    @Published var isScanning: Bool = true
    
    let captureSession = AVCaptureSession()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let scorer = URLRiskScorer()
    
    override init() {
        super.init()
        setupCamera()
    }
    
    private func setupCamera() {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device) else {
            return
        }
        
        if captureSession.canAddInput(input) {
            captureSession.addInput(input)
        }
        
        videoOutput.setSampleBufferDelegate(self, queue: DispatchQueue(label: "videoQueue"))
        if captureSession.canAddOutput(videoOutput) {
            captureSession.addOutput(videoOutput)
        }
    }
    
    func startScanning() {
        if !captureSession.isRunning {
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                self?.captureSession.startRunning()
            }
        }
        isScanning = true
    }
    
    func stopScanning() {
        if captureSession.isRunning {
            captureSession.stopRunning()
        }
        isScanning = false
    }
    
    func reset() {
        currentResult = nil
        isScanning = true
    }
    
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard isScanning else { return }
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        
        #if canImport(OpenCV) || canImport(opencv2)
        // 1. Convert CVPixelBuffer to OpenCV Mat (comment: converts camera frame to processable format)
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let context = CIContext()
        guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else { return }
        let mat = Mat(uiImage: UIImage(cgImage: cgImage))
        
        // 2. Grayscale (comment: reduces complexity, removes color noise)
        Imgproc.cvtColor(src: mat, dst: mat, code: .COLOR_BGR2GRAY)
        
        // 3. Gaussian blur 5x5 (comment: smooths edges, reduces false contours)
        Imgproc.GaussianBlur(src: mat, dst: mat, ksize: Size(width: 5, height: 5), sigmaX: 0)
        
        // 4. Canny edge detection 50/150 (comment: detects QR code edges)
        Imgproc.Canny(image: mat, edges: mat, threshold1: 50, threshold2: 150)
        
        // 5. FindContours (comment: identifies rectangular regions)
        var contours = [[Point]]()
        let hierarchy = Mat()
        Imgproc.findContours(image: mat, contours: &contours, hierarchy: hierarchy, mode: .RETR_EXTERNAL, method: .CHAIN_APPROX_SIMPLE)
        #endif
        
        // 6. Pass to Vision for URL decode only
        let requestHandler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:])
        let barcodeRequest = VNDetectBarcodesRequest { [weak self] request, error in
            guard let self = self, self.isScanning else { return }
            guard let results = request.results as? [VNBarcodeObservation],
                  let firstResult = results.first,
                  let payloadString = firstResult.payloadStringValue else { return }
            
            let lower = payloadString.lowercased()
            guard lower.hasPrefix("http") || lower.contains(".") else { return }
            
            DispatchQueue.main.async {
                self.isScanning = false
                // 7. Send URL to URLRiskScorer
                self.currentResult = self.scorer.scoreURL(payloadString)
            }
        }
        
        do {
            try requestHandler.perform([barcodeRequest])
        } catch {
            print("Vision request failed: \(error)")
        }
    }
    
    func simulateSafe() {
        isScanning = false
        let safeURL = "https://www.google.com"
        let riskResult = scorer.scoreURL(safeURL)
        DispatchQueue.main.async {
            self.currentResult = riskResult
        }
    }
    
    func simulatePhishing() {
        isScanning = false
        let phishingURL = "https://ivoryrobinson94.wixsite.com/0ne-dr1ve"
        let riskResult = scorer.scoreURL(phishingURL)
        print("Score: \(riskResult.score)")
        print("Reasons: \(riskResult.reasons)")
        DispatchQueue.main.async {
            self.currentResult = riskResult
        }
    }
}
