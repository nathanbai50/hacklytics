//
//  CameraManager.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//

import SwiftUI
import AVFoundation
import Foundation
import Combine

class CameraManager: NSObject, ObservableObject, AVCaptureFileOutputRecordingDelegate {
    @Published var session = AVCaptureSession()
    @Published var isRecording = false
    @Published var recordedVideoURL: URL?
    @Published var currentPosition: AVCaptureDevice.Position = .back
    
    private var output = AVCaptureMovieFileOutput()
    
    func checkPermissionsAndSetup() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            setupCamera()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                if granted {
                    DispatchQueue.main.async { self.setupCamera() }
                }
            }
        default:
            break
        }
    }
    
    private func setupCamera() {
        do {
            session.beginConfiguration()
            
            // 1. Get the back camera
            guard let videoDevice = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let videoInput = try? AVCaptureDeviceInput(device: videoDevice) else { return }
            
            if session.canAddInput(videoInput) {
                session.addInput(videoInput)
            }
            
            // 2. Setup video output
            if session.canAddOutput(output) {
                session.addOutput(output)
            }
            
            session.commitConfiguration()
            
            DispatchQueue.global(qos: .background).async {
                self.session.startRunning()
            }
        }
    }
    
    func toggleRecording() {
        if isRecording {
            output.stopRecording()
            isRecording = false
        } else {
            // Save to temporary directory
            let tempDirectory = FileManager.default.temporaryDirectory
            let fileURL = tempDirectory.appendingPathComponent("pushup_workout_\(UUID().uuidString).mov")
            output.startRecording(to: fileURL, recordingDelegate: self)
            isRecording = true
        }
    }
    
    // This fires when the video finishes saving
    func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL, from connections: [AVCaptureConnection], error: Error?) {
        if error == nil {
            DispatchQueue.main.async {
                self.recordedVideoURL = outputFileURL
            }
        }
    }
    
    func flipCamera() {
            // Don't allow flipping while actively recording a video
            guard !isRecording else { return }
            
            session.beginConfiguration()
            
            // 1. Find the current video input and remove it
            guard let currentInput = session.inputs.first as? AVCaptureDeviceInput else {
                session.commitConfiguration()
                return
            }
            session.removeInput(currentInput)
            
            // 2. Determine the new position
            let newPosition: AVCaptureDevice.Position = currentInput.device.position == .back ? .front : .back
            
            // 3. Find the hardware for the new position
            guard let newDevice = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: newPosition),
                  let newInput = try? AVCaptureDeviceInput(device: newDevice) else {
                // Fallback: If it fails, put the old camera back
                session.addInput(currentInput)
                session.commitConfiguration()
                return
            }
            
            // 4. Attach the new camera
            if session.canAddInput(newInput) {
                session.addInput(newInput)
                self.currentPosition = newPosition
            } else {
                session.addInput(currentInput)
            }
            
            session.commitConfiguration()
        }
}

struct CameraPreviewView: UIViewRepresentable {
    var session: AVCaptureSession
    
    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: UIScreen.main.bounds)
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.frame = view.frame
        previewLayer.videoGravity = .resizeAspectFill // Fills the screen like Snapchat
        view.layer.addSublayer(previewLayer)
        return view
    }
    
    func updateUIView(_ uiView: UIView, context: Context) {}
}
