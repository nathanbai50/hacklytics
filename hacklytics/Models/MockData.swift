//
//  MockData.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//

import Foundation

extension SetData {
    static let mockPerfectSet = SetData(
        overallScore: 94,
        totalValidReps: 10,
        coachingTakeaway: "Incredible consistency! Your form stayed rock solid through the entire set.",
        repData: (1...10).map { i in
            RepData(repNumber: i, dtwScore: Int.random(in: 90...98), minElbowAngle: 85.0, avgBodyAngle: 178.5)
        }
    )
    
    static let mockFatiguedSet = SetData(
        overallScore: 72,
        totalValidReps: 12,
        coachingTakeaway: "Great start, but your hips began to sag after rep 8. Focus on core engagement.",
        repData: [
            RepData(repNumber: 1, dtwScore: 95, minElbowAngle: 82, avgBodyAngle: 179),
            RepData(repNumber: 2, dtwScore: 94, minElbowAngle: 84, avgBodyAngle: 178),
            // ... simulating fatigue around rep 9
            RepData(repNumber: 9, dtwScore: 65, minElbowAngle: 105, avgBodyAngle: 160),
            RepData(repNumber: 10, dtwScore: 50, minElbowAngle: 110, avgBodyAngle: 155)
        ]
    )
}
