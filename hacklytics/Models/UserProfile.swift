//
//  UserProfile.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import Foundation
import FirebaseFirestore

struct UserProfile: Codable, Identifiable {
    @DocumentID var id: String? // This will be the Firebase Auth UID
    
    let fullName: String
    let email: String
    
    // App-specific data
        var currentAIGoal: String?
        var currentRepGoal: Int?      // 🚀 Add this
        var currentScoreGoal: Int?    // 🚀 Add this
        var totalSetsCompleted: Int = 0
        
        enum CodingKeys: String, CodingKey {
            case id
            case fullName = "full_name"
            case email
            case currentAIGoal = "current_ai_goal"
            case currentRepGoal = "current_rep_goal"       // 🚀 Map this
            case currentScoreGoal = "current_score_goal"   // 🚀 Map this
            case totalSetsCompleted = "total_sets_completed"
        }
}
