//
//  RepData.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/20/26.
//

import Foundation

struct RepData: Codable, Identifiable {
    // SwiftUI requires 'Identifiable' to plot this data in Charts or Lists
    let id = UUID()
    
    let repNumber: Int
    let dtwScore: Int
    let minElbowAngle: Double
    let avgBodyAngle: Double
    
    enum CodingKeys: String, CodingKey {
        case repNumber = "rep_number"
        case dtwScore = "dtw_score"
        case minElbowAngle = "min_elbow_angle"
        case avgBodyAngle = "avg_body_angle"
    }
}
