//
//  MainAppView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//

import SwiftUI
import Combine

struct MainAppView: View {
    @StateObject private var cameraManager = CameraManager()
    @StateObject private var viewModel = PushupViewModel()
    @Binding var isTabBarHidden: Bool
    @State private var recordingTime = 0
        
    let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
        
    func formatTime(_ seconds: Int) -> String {
        let m = seconds / 60
        let s = seconds % 60
        return String(format: "%02d:%02d", m, s)
    }
    
    var body: some View {
        ZStack {
            // STATE 1: LOADING SPINNER
            if viewModel.isProcessing {
                LoadingView()
                    .transition(.opacity)
                    .zIndex(1)
            }
            // STATE 2: SNAPCHAT CAMERA UI
            else {
                ZStack {
                    // 1. Full screen camera feed
                    CameraPreviewView(session: cameraManager.session)
                        .ignoresSafeArea()
                    
                    // 2. Top UI Controls (Header & Timer)
                    VStack {
                        if cameraManager.isRecording {
                            // The Active Recording Timer
                            HStack {
                                Circle()
                                    .fill(Color.red)
                                    .frame(width: 10, height: 10)
                                    .opacity(recordingTime % 2 == 0 ? 1.0 : 0.5)
                                    .animation(.easeInOut(duration: 0.5), value: recordingTime) // Smooth blinking
                                
                                Text(formatTime(recordingTime))
                                    .font(.system(.headline, design: .monospaced))
                                    .foregroundColor(.white)
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .background(Color.black.opacity(0.6))
                            .cornerRadius(20)
                            .padding(.top, 50) // Pushed down slightly for notch/Dynamic Island
                            // Animate the timer dropping in from the top
                            .transition(.move(edge: .top).combined(with: .opacity))
                            
                        } else {
                            // 🚀 NEW: The Prompt Header
                            Text("Record your pushups")
                                .font(.headline)
                                .foregroundColor(.white)
                                .padding(.horizontal, 20)
                                .padding(.vertical, 10)
                                .background(Color.black.opacity(0.5)) // Dark pill background so it's readable over the camera
                                .clipShape(Capsule())
                                .padding(.top, 50)
                                .transition(.move(edge: .top).combined(with: .opacity))
                        }
                        Spacer()
                    }
                    
                    // 3. Bottom Controls (ZStack fixes the alignment perfectly)
                    VStack {
                        Spacer()
                        ZStack {
                            // CENTER: The Record Button
                            Button(action: {
                                // Add spring animation to the state change
                                withAnimation(.spring(response: 0.4, dampingFraction: 0.6)) {
                                    cameraManager.toggleRecording()
                                }
                            }) {
                                ZStack {
                                    // Outer Ring
                                    Circle()
                                        .stroke(Color.white, lineWidth: cameraManager.isRecording ? 2 : 4)
                                        .frame(width: 80, height: 80)
                                        .scaleEffect(cameraManager.isRecording ? 1.1 : 1.0) // Expands slightly when recording
                                    
                                    // Inner Circle
                                    Circle()
                                        .fill(cameraManager.isRecording ? Color.red : Color.white.opacity(0.8))
                                        .frame(width: cameraManager.isRecording ? 40 : 65, height: cameraManager.isRecording ? 40 : 65)
                                }
                            }
                            
                            // RIGHT: The Flip Button
                            HStack {
                                Spacer()
                                Button(action: {
                                    let impactMed = UIImpactFeedbackGenerator(style: .medium)
                                    impactMed.impactOccurred()
                                    cameraManager.flipCamera()
                                }) {
                                    Image(systemName: "arrow.triangle.2.circlepath.camera")
                                        .font(.title2)
                                        .foregroundColor(.white)
                                        .padding(15)
                                        .background(Color.black.opacity(0.4))
                                        .clipShape(Circle())
                                }
                                .padding(.trailing, 30)
                                .disabled(cameraManager.isRecording)
                                // Smooth fade out when recording starts
                                .opacity(cameraManager.isRecording ? 0.0 : 1.0)
                                .animation(.easeInOut, value: cameraManager.isRecording)
                            }
                        }
                        .padding(.bottom, 120)
                    }
                }
                .onChange(of: viewModel.isProcessing) { isProcessing in
                            // When processing starts, hide the tab bar. When it finishes, bring it back!
                            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                                isTabBarHidden = isProcessing
                            }
                }
                // Listen to the Combine timer
                .onReceive(timer) { _ in
                    if cameraManager.isRecording {
                        recordingTime += 1
                    }
                }
                .onChange(of: cameraManager.isRecording) { isRecording in
                    if !isRecording {
                        recordingTime = 0
                    }
                }
            }
        }
        // Smooth transition between Camera -> Loading
        .animation(.easeInOut, value: viewModel.isProcessing)
        .onAppear {
            cameraManager.checkPermissionsAndSetup()
        }
        .onChange(of: cameraManager.recordedVideoURL) { newURL in
            if let url = newURL {
                viewModel.uploadVideoForAnalysis(videoURL: url)
                cameraManager.recordedVideoURL = nil
            }
        }
        // --- NEW: The Results Sheet ---
        .sheet(isPresented: Binding<Bool>(
            get: { viewModel.currentSet != nil },
            set: { isPresented in
                if !isPresented {
                    viewModel.currentSet = nil // Safely resets the state when dismissed
                }
            }
        )) {
            PushupResultsView(viewModel: viewModel)
        }
        // --- The Alert ---
        .alert("No pushups detected", isPresented: Binding<Bool>(
            get: { viewModel.errorMessage != nil },
            set: { _ in viewModel.errorMessage = nil }
        )) {
            Button("Try Again", role: .cancel) { }
        } message: {
            Text("Ensure that your camera has a clear side view.")
        }
    }
}
