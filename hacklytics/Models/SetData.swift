//
//  SetData.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/20/26.
//

import Foundation

struct SetData: Codable {
    let overallScore: Int
    let totalValidReps: Int
    let coachingTakeaway: String
    let repData: [RepData]
    
    enum CodingKeys: String, CodingKey {
        case overallScore = "overall_score"
        case totalValidReps = "total_valid_reps"
        case coachingTakeaway = "coaching_takeaway"
        case repData = "rep_data"
    }
}
