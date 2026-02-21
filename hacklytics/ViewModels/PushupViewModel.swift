//
//  PushupViewModel.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/20/26.
//


import Foundation
import Combine

// Helper extension to make appending strings to Data easier
extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}

class PushupViewModel: ObservableObject {
    @Published var currentSet: SetData? // Using your SetData model
    @Published var isProcessing: Bool = false
    @Published var errorMessage: String?
    
    func uploadVideoForAnalysis(videoURL: URL) {
        isProcessing = true
        errorMessage = nil
        
        // 1. Set the URL (Update this to your Python server's local IP or deployed URL)
        guard let url = URL(string: "http://127.0.0.1:5000/analyze") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        // 2. Create the Boundary
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        // 3. Build the Multipart Form Body
        var body = Data()
        let filename = videoURL.lastPathComponent
        // If recording natively on iOS, this might be "video/quicktime" (.mov)
        let mimeType = "video/quicktime"
        
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"video\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: \(mimeType)\r\n\r\n")
        
        // Try to load the video data
        do {
            let videoData = try Data(contentsOf: videoURL)
            body.append(videoData)
        } catch {
            self.errorMessage = "Could not load video file from device."
            self.isProcessing = false
            return
        }
        
        body.append("\r\n--\(boundary)--\r\n")
        request.httpBody = body
        
        // 4. Send the Request
        URLSession.shared.dataTask(with: request) { data, response, error in
            // Always update UI state on the main thread
            DispatchQueue.main.async {
                self.isProcessing = false
                
                if let error = error {
                    self.errorMessage = "Network error: \(error.localizedDescription)"
                    return
                }
                
                guard let data = data else {
                    self.errorMessage = "No data received from server."
                    return
                }
                
                // 5. Decode the Python JSON into your SetData struct
                do {
                    let decodedData = try JSONDecoder().decode(SetData.self, from: data)
                    self.currentSet = decodedData
                } catch {
                    self.errorMessage = "Failed to decode results: \(error.localizedDescription)"
                    print("Decoding error: \(error)")
                }
            }
        }.resume()
    }
}
