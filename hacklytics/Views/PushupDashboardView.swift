import SwiftUI

struct PushupDashboardView: View {
    // Bring in your ViewModel
    @StateObject private var viewModel = PushupViewModel()
    
    // State to control when the camera opens
    @State private var isShowingCamera = false
    
    var body: some View {
        VStack {
            if viewModel.isProcessing {
                ProgressView("un momento")
                    .padding()
            } else if let set = viewModel.currentSet {
                VStack(spacing: 20) {
                    VStack {
                        Text("\(set.overallScore)")
                            .font(.system(size: 80, weight: .bold, design: .rounded))
                            .foregroundColor(set.overallScore > 80 ? .green : .orange)
                        Text("OVERALL FORM SCORE")
                            .font(.caption).bold().foregroundColor(.secondary)
                        Text(set.coachingTakeaway)
                            .font(.subheadline)
                            .multilineTextAlignment(.center)
                            .padding()
                            .background(Color.blue.opacity(0.1))
                            .cornerRadius(10)
                    }
                    
                    ScrollView {

                        FatigueChart(data: set.repData)
                        DepthChart(data: set.repData)
                        
                    }
                    .padding()
                    
                    Button("Test New Workout") {
                        viewModel.currentSet = nil
                    }
                }
            } else {
                Text("Ready to workout?")
                    .padding()
                Button(action: {
                    isShowingCamera = true
                }) {
                    Text("Record Push-ups")
                        .foregroundColor(.white)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(10)
                }
                .disabled(viewModel.isProcessing)
            }
            
            if viewModel.currentSet == nil && !viewModel.isProcessing {
                Button(action: {
                    // Manually inject the mock data from our extension
                    viewModel.currentSet = SetData.mockFatiguedSet
                }) {
                    Text("Run Demo (Mock Data)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.top, 8)
                }
            }
        }
        // This makes the camera slide up over the whole screen
        .fullScreenCover(isPresented: $isShowingCamera) {
            VideoRecorderView { recordedURL in
                // This block runs the second the user hits "Use Video"
                print("Video saved to: \(recordedURL)")
                viewModel.uploadVideoForAnalysis(videoURL: recordedURL)
            }
            .ignoresSafeArea()
        }
    }
}
