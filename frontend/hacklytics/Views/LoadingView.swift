//
//  LoadingView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//

import SwiftUI

struct LoadingView: View {
    @State private var isSpinning = false
    @State private var isPulsing = false
    
    var body: some View {
        ZStack {
            // Force deep black background
            Color.black.ignoresSafeArea()
            
            VStack(spacing: 40) {
                ZStack {
                    // 1. The Spinning Outer Ring
                    Circle()
                        .stroke(
                            LinearGradient(
                                colors: [.white, .white.opacity(0.0)],
                                startPoint: .top,
                                endPoint: .bottom
                            ),
                            lineWidth: 3
                        )
                        .frame(width: 130, height: 130)
                        .rotationEffect(.degrees(isSpinning ? 360 : 0))
                        // 🚀 FIX 1: Attach animation directly to the state value
                        .animation(.linear(duration: 1.5).repeatForever(autoreverses: false), value: isSpinning)
                    
                    // 2. The Pulsing Inner Logo
                    Image(systemName: "figure.strengthtraining.traditional")
                        .font(.system(size: 50))
                        .foregroundColor(.white)
                        .scaleEffect(isPulsing ? 1.05 : 0.95)
                        // 🚀 Attach pulsing animation here
                        .animation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true), value: isPulsing)
                }
                
                // 3. The Animated Text
                VStack(spacing: 12) {
                    Text("Analyzing Form")
                        .font(.title2)
                        .bold()
                        .foregroundColor(.white)
                    
                    Text("Your coach is hard at work looking at your technique...")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }
                .opacity(isPulsing ? 1.0 : 0.6)
                // 🚀 Attach pulsing animation here too
                .animation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true), value: isPulsing)
            }
        }
        .onAppear {
            // 🚀 FIX 2: Wait for the view to physically render before flipping the switches
            DispatchQueue.main.async {
                isSpinning = true
                isPulsing = true
            }
        }
    }
}
