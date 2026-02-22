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

// 1. ADD THIS: A struct to catch the Python server's error format
struct ServerResponse: Codable {
    let status: String?
    let message: String?
}

class PushupViewModel: ObservableObject {
    @Published var currentSet: SetData?
    @Published var isProcessing: Bool = false
    @Published var errorMessage: String?
    
    func uploadVideoForAnalysis(videoURL: URL) {
        isProcessing = true
        errorMessage = nil
        
        print("🚀 [TEST] Received video for upload at: \(videoURL.path)")
        
        let serverURLString = "https://kristi-incredible-niko.ngrok-free.dev/analyze"
        guard let url = URL(string: serverURLString) else {
            print("❌ Invalid URL")
            self.isProcessing = false
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        let filename = videoURL.lastPathComponent
        let mimeType = "video/quicktime"
        
        let appendString = { (string: String) in
            if let data = string.data(using: .utf8) {
                body.append(data)
            }
        }
        
        appendString("--\(boundary)\r\n")
        appendString("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        appendString("Content-Type: \(mimeType)\r\n\r\n")
        
        do {
            let videoData = try Data(contentsOf: videoURL)
            body.append(videoData)
        } catch {
            self.errorMessage = "Could not load video file from device."
            self.isProcessing = false
            return
        }
        
        appendString("\r\n--\(boundary)--\r\n")
        request.httpBody = body
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                self.isProcessing = false
                
                if let error = error {
                    self.errorMessage = "Network error: \(error.localizedDescription)"
                    print("❌ Network Error: \(error.localizedDescription)")
                    return
                }
                
                guard let data = data else {
                    self.errorMessage = "No data received from server."
                    print("❌ No data received.")
                    return
                }
                
                if let rawString = String(data: data, encoding: .utf8) {
                    print("Raw Server Response: \(rawString)")
                }
                
                do {
                    // 1. Check if it's an error message first (your existing logic)
                    if let errorResponse = try? JSONDecoder().decode(ServerResponse.self, from: data),
                       errorResponse.status == "error",
                       let msg = errorResponse.message {
                        
                        self.errorMessage = msg
                        print("❌ Server Rejected Video: \(msg)")
                        return
                    }

                    // 2. NEW: A temporary struct that perfectly matches the Python JSON
                    // (Notice how we just use snake_case here so we don't even need CodingKeys!)
                    struct PythonSetResponse: Codable {
                        let overall_score: Int
                        let total_valid_reps: Int
                        let coaching_takeaway: String
                        let rep_data: [RepData]
                    }

                    // 3. Decode the raw data into our temporary Python struct
                    let pythonData = try JSONDecoder().decode(PythonSetResponse.self, from: data)
                    
                    // 4. Map it into your official Firebase SetData model!
                    let newSet = SetData(
                        id: nil,          // Pass nil so Firestore auto-generates the document ID
                        date: Date(),
                        overallScore: pythonData.overall_score,
                        totalValidReps: pythonData.total_valid_reps,
                        coachingTakeaway: pythonData.coaching_takeaway,
                        repData: pythonData.rep_data
                    )
                    
                    self.currentSet = newSet
                    print("✅ Successfully decoded and mapped SetData!")
                    
                    FirebaseManager.shared.saveWorkout(set: newSet)
                    
                } catch {
                    self.errorMessage = "Failed to decode results."
                    print("❌ Decoding error: \(error)")
                }            }
        }.resume()
    }
}
