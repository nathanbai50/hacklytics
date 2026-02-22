//
//  PushupResultsView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import SwiftUI
import ConfettiSwiftUI

struct PushupResultsView: View {
    @ObservedObject var viewModel: PushupViewModel
    @State private var confettiCounter = 0
    
    func scoreColor(for score: Int) -> Color {
        if score >= 80 { return .green }
        if score >= 60 { return .orange }
        return .red
    }
    
    var body: some View {
        if let set = viewModel.currentSet {
            // 1. Wrap the whole thing in a NavigationStack
            NavigationStack {
                VStack(spacing: 20) {
                    VStack {
                        Text("\(set.overallScore)")
                            .font(.system(size: 80, weight: .bold, design: .rounded))
                            .foregroundColor(scoreColor(for: set.overallScore))
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
                        BodyAngleChart(data: set.repData)
                    }
                    .padding()
                }
                // 2. Add the Top Navigation Bar and Dismiss Button
                .navigationTitle("Set Results")
                .navigationBarTitleDisplayMode(.inline)
                .onAppear {
                    if set.overallScore >= 90 {
                        confettiCounter += 1
                    }
                }
                .confettiCannon(trigger: $confettiCounter, num: 50, radius: 350)
            }
        }
    }
}
