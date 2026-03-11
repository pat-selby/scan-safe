import SwiftUI
import AVFoundation

struct ContentView: View {
    @State private var cameraPermissionGranted = false
    @State private var permissionDetermined = false
    
    var body: some View {
        Group {
            if !permissionDetermined {
                Color.black.edgesIgnoringSafeArea(.all)
                    .onAppear(perform: requestCameraPermission)
            } else if cameraPermissionGranted {
                CameraView()
            } else {
                Text("Camera permission is required to use ScanSafe.")
                    .foregroundColor(.white)
                    .padding()
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.edgesIgnoringSafeArea(.all))
            }
        }
    }
    
    private func requestCameraPermission() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            cameraPermissionGranted = true
            permissionDetermined = true
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                DispatchQueue.main.async {
                    self.cameraPermissionGranted = granted
                    self.permissionDetermined = true
                }
            }
        case .denied, .restricted:
            cameraPermissionGranted = false
            permissionDetermined = true
        @unknown default:
            cameraPermissionGranted = false
            permissionDetermined = true
        }
    }
}
