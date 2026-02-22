//
//  SetData.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/20/26.
//

import Foundation
import FirebaseFirestore // 1. Import Firestore

struct SetData: Codable, Identifiable {
    @DocumentID var id: String?
    var date: Date? = Date() // Must be here
    
    let overallScore: Int
    let totalValidReps: Int
    let coachingTakeaway: String
    let repData: [RepData]
    
    enum CodingKeys: String, CodingKey {
        case id
        case date // MUST BE HERE!
        case overallScore = "overall_score"
        case totalValidReps = "total_valid_reps"
        case coachingTakeaway = "coaching_takeaway"
        case repData = "rep_data"
    }
}
