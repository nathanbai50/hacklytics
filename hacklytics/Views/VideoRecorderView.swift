//
//  VideoRecorderView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct VideoRecorderView: UIViewControllerRepresentable {
    @Environment(\.presentationMode) var presentationMode
    var onVideoRecorded: (URL) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.delegate = context.coordinator
        
        // Ensure the device has a camera
        if UIImagePickerController.isSourceTypeAvailable(.camera) {
            picker.sourceType = .camera
            // Set it to record video, not take photos
            picker.mediaTypes = [UTType.movie.identifier]
            picker.cameraCaptureMode = .video
            // Optional: Default to the side/back camera
            picker.cameraDevice = .rear 
        }
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let parent: VideoRecorderView

        init(_ parent: VideoRecorderView) {
            self.parent = parent
        }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            // Extract the URL of the recorded video
            if let videoURL = info[.mediaURL] as? URL {
                parent.onVideoRecorded(videoURL)
            }
            parent.presentationMode.wrappedValue.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.presentationMode.wrappedValue.dismiss()
        }
    }
}