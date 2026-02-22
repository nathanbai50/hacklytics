//
//  SetCardView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import SwiftUI

struct SetCardView: View {
    let set: SetData
    
    // Helper to format the date nicely (e.g., "Feb 21, 2026 at 5:15 PM")
    var formattedDate: String {
        guard let date = set.date else { return "Unknown Date" }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short 
        return formatter.string(from: date)
    }
    
    // Helper for score color
    func scoreColor(for score: Int) -> Color {
        if score >= 80 { return .green }
        if score >= 60 { return .orange }
        return .red
    }
    
    var body: some View {
        HStack(spacing: 16) {
            
            // 1. The Score Progress Ring
            ZStack {
                // Background Track
                Circle()
                    .stroke(scoreColor(for: set.overallScore).opacity(0.2), lineWidth: 5)
                
                // Animated Fill
                Circle()
                    .trim(from: 0, to: CGFloat(set.overallScore) / 100.0)
                    .stroke(scoreColor(for: set.overallScore), style: StrokeStyle(lineWidth: 5, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                
                Text("\(set.overallScore)")
                    .font(.system(size: 20, weight: .bold, design: .rounded))
                    .foregroundColor(scoreColor(for: set.overallScore))
            }
            .frame(width: 65, height: 65)
            
            // 2. The Workout Details
            VStack(alignment: .leading, spacing: 6) {
                Text(formattedDate)
                    .font(.headline)
                    .foregroundColor(.primary)
                
                HStack(spacing: 4) {
                    Image(systemName: "figure.strengthtraining.traditional")
                    Text("\(set.totalValidReps) Valid Reps")
                }
                .font(.subheadline)
                .foregroundColor(.secondary)
                
                Text(set.coachingTakeaway)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
            }
            
            Spacer()
            
            Image(systemName: "chevron.right")
                            .font(.body.weight(.semibold))
                            .foregroundColor(Color(.tertiaryLabel))
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(16)
    }
}
