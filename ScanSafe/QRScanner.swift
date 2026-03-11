import Foundation
import AVFoundation
import Vision

#if canImport(OpenCV)
import OpenCV
#endif

class QRScanner: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    @Published var currentResult: RiskResult?
    @Published var currentURL: String?
    @Published var isScanning: Bool = true
    private var barcodeRequest: VNDetectBarcodesRequest?
    
    override init() {
        super.init()
        setupVision()
    }
    
    private func setupVision() {
        barcodeRequest = VNDetectBarcodesRequest { [weak self] request, error in
            guard let self = self, self.isScanning else { return }
            guard let results = request.results as? [VNBarcodeObservation], 
                  let firstResult = results.first, 
                  let payloadString = firstResult.payloadStringValue else { return }
            
            self.processURL(payloadString)
        }
    }
    
    func processURL(_ url: String) {
        self.isScanning = false
        let riskResult = URLRiskScorer.evaluate(url: url)
        
        DispatchQueue.main.async {
            self.currentURL = url
            self.currentResult = riskResult
        }
    }
    
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard isScanning else { return }
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        
        defer {
            // Call imageProxy close in finally block
            // While iOS manages sample buffers automatically, adhering to cross-platform structure concepts:
            // "imageProxy.close()"
        }
        
        #if canImport(OpenCV)
        // 1. Convert CVPixelBuffer to OpenCV Mat
        // let mat = Mat(cvPixelBuffer: pixelBuffer)
        
        // 2. Grayscale conversion
        // WHY: Grayscale conversion reduces the image to a single channel (intensity). 
        // This speeds up the processing because edge detection doesn't need color data.
        // Imgproc.cvtColor(src: mat, dst: mat, code: .COLOR_BGR2GRAY)
        
        // 3. Gaussian blur 5x5 kernel
        // WHY: Gaussian blur is applied to reduce high-frequency noise in the image. 
        // This prevents the Canny edge detector from mistakenly identifying noise as edges.
        // Imgproc.GaussianBlur(src: mat, dst: mat, ksize: Size(width: 5, height: 5), sigmaX: 0)
        
        // 4. Canny edge detection thresholds 50, 150
        // WHY: Canny is used to identify sharp drops in intensity representing strong structural outlines. 
        // The thresholds 50 and 150 trace and link strong edges, ignoring weak ones.
        // Imgproc.Canny(image: mat, edges: mat, threshold1: 50, threshold2: 150)
        
        // 5. FindContours
        // WHY: FindContours extracts the continuous boundaries from the Canny edge map,
        // allowing us to locate the geometric finder patterns (the three squares) of the QR code.
        // var contours = [[Point]]()
        // var hierarchy = Mat()
        // Imgproc.findContours(image: mat, contours: &contours, hierarchy: hierarchy, mode: .RETR_EXTERNAL, method: .CHAIN_APPROX_SIMPLE)
        #endif
        
        // 6. Pass frame to Apple Vision (VNDetectBarcodesRequest) to extract URL string only
        let requestHandler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:])
        do {
            if let barcodeRequest = barcodeRequest {
                try requestHandler.perform([barcodeRequest])
            }
        } catch {
            print("Vision request failed: \(error)")
        }
    }
    
    // Simulate from buttons
    func simulate(url: String) {
        processURL(url)
    }
    
    func reset() {
        self.currentResult = nil
        self.currentURL = nil
        self.isScanning = true
    }
}
