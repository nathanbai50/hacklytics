//
//  FirebaseManager.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//

import Foundation
import FirebaseFirestore
import FirebaseAuth

class FirebaseManager {
    static let shared = FirebaseManager()
    private let db = Firestore.firestore()
    
    // MARK: - Save Workout
    func saveWorkout(set: SetData) {
        guard let currentUserId = Auth.auth().currentUser?.uid else {
            print("❌ Cannot save workout: No user is logged in.")
            return
        }
        
        let workoutRef = db.collection("users")
            .document(currentUserId)
            .collection("workouts")
            .document()
        
        do {
            try workoutRef.setData(from: set)
            print("✅ Successfully saved workout to Firestore!")
            
            // 1. Increment the counter
            self.incrementTotalSets()
            
            // 2. Fetch the 5 most recent sets
            db.collection("users")
                .document(currentUserId)
                .collection("workouts")
                .order(by: "date", descending: true)
                .limit(to: 5)
                .getDocuments { snapshot, error in
                    guard let documents = snapshot?.documents else { return }
                    
                    let recentSets = documents.compactMap { doc -> SetData? in
                        try? doc.data(as: SetData.self)
                    }
                    
                    // 3. Ask Python for the new goals (Text, Reps, and Score)
                    self.fetchNewAIGoal(workoutHistory: recentSets) { newGoal, repGoal, scoreGoal in
                        guard let goal = newGoal, let rGoal = repGoal, let sGoal = scoreGoal else { return }
                        
                        // Get the existing goals from the AuthManager
                        let currentRepGoal = AuthManager.shared.currentUserProfile?.currentRepGoal ?? 0
                        let currentScoreGoal = AuthManager.shared.currentUserProfile?.currentScoreGoal ?? 0
                        
                        // 🚀 Only update if the user has reached or exceeded their existing targets
                        // This ensures goals only "level up" once the current ones are conquered
                        let maxRepsInHistory = recentSets.map { $0.totalValidReps }.max() ?? 0
                        let avgScoreInHistory = recentSets.isEmpty ? 0 : recentSets.reduce(0) { $0 + $1.overallScore } / recentSets.count

                        if maxRepsInHistory >= currentRepGoal || avgScoreInHistory >= currentScoreGoal {
                            print("🎯 Goal Conquered! Updating to new targets: \(goal)")
                            self.updateAIGoal(newGoal: goal, repGoal: rGoal, scoreGoal: sGoal)
                        } else {
                            print("📈 Progressing... Current goals maintained until hit.")
                        }
                    }
                }
            
        } catch {
            print("❌ Error saving workout: \(error.localizedDescription)")
        }
    }
    
    // MARK: - Live Workout History Listener
    func listenToWorkoutHistory(completion: @escaping ([SetData]) -> Void) {
        guard let currentUserId = Auth.auth().currentUser?.uid else {
            completion([])
            return
        }
            
        // .addSnapshotListener creates a live websocket to your database
        db.collection("users")
            .document(currentUserId)
            .collection("workouts")
            .order(by: "date", descending: true) // Newest first
            .addSnapshotListener { snapshot, error in
                if let error = error {
                    print("❌ Error listening to history: \(error.localizedDescription)")
                    completion([])
                    return
                }
                    
                guard let documents = snapshot?.documents else {
                    completion([])
                    return
                }
                    
                // This block automatically runs EVERY TIME a workout is added, deleted, or changed
                let workouts = documents.compactMap { doc -> SetData? in
                    try? doc.data(as: SetData.self)
                }
                    
                completion(workouts)
            }
    }
    
    // MARK: - Live User Profile Listener
    func listenToUserProfile(completion: @escaping (UserProfile?) -> Void) {
        guard let userId = Auth.auth().currentUser?.uid else { return }
        
        // .addSnapshotListener means this fires IMMEDIATELY every time the database changes!
        db.collection("users").document(userId).addSnapshotListener { documentSnapshot, error in
            guard let document = documentSnapshot, document.exists, error == nil else {
                print("❌ Error fetching live user profile: \(error?.localizedDescription ?? "Unknown error")")
                completion(nil)
                return
            }
            
            // Decode the Firebase document directly into your Swift struct
            do {
                let updatedProfile = try document.data(as: UserProfile.self)
                completion(updatedProfile)
            } catch {
                print("❌ Error decoding live user profile: \(error)")
                completion(nil)
            }
        }
    }
    
    // MARK: - Delete Workout
    func deleteWorkout(workoutId: String) {
        guard let currentUserId = Auth.auth().currentUser?.uid else { return }
            
        db.collection("users")
            .document(currentUserId)
            .collection("workouts")
            .document(workoutId)
            .delete { error in
                if let error = error {
                    print("❌ Error deleting workout: \(error.localizedDescription)")
                } else {
                    print("🗑️ Successfully deleted workout from Firestore!")
                }
            }
    }
    
    // MARK: - Fetch AI Goal
    func fetchNewAIGoal(workoutHistory: [SetData], completion: @escaping (String?, Int?, Int?) -> Void) {
        guard let url = URL(string: "https://kristi-incredible-niko.ngrok-free.dev/generate_goal") else { return }
        
        let recentSets = Array(workoutHistory.prefix(5))
        
        let recentScores = recentSets.map { $0.overallScore }
        let recentReps = recentSets.map { $0.totalValidReps }
        let recentTakeaways = recentSets.map { $0.coachingTakeaway }
        
        let allRecentReps = recentSets.flatMap { $0.repData }
        let avgDepth: Double = allRecentReps.isEmpty ? 0.0 : allRecentReps.reduce(0.0) { $0 + $1.minElbowAngle } / Double(allRecentReps.count)
        
        let body: [String: Any] = [
            "total_lifetime_sets": workoutHistory.count,
            "recent_scores": recentScores,
            "recent_reps": recentReps,
            "average_depth": avgDepth,
            "recent_takeaways": recentTakeaways
        ]
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            guard let data = data, error == nil else {
                print("❌ Network Error: \(error?.localizedDescription ?? "Unknown")")
                completion(nil, nil, nil)
                return
            }
            
            // Decode the expanded JSON response
            if let jsonResponse = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let newGoal = jsonResponse["goal"] as? String,
               let repGoal = jsonResponse["rep_goal"] as? Int,
               let scoreGoal = jsonResponse["score_goal"] as? Int {
                
                // Return all three back to the main thread
                DispatchQueue.main.async {
                    completion(newGoal, repGoal, scoreGoal)
                }
            } else {
                print("❌ Error parsing the AI JSON response. Check your Python keys!")
                completion(nil, nil, nil)
            }
        }.resume()
    }
    
    // MARK: - Increment / Decrement Sets
    func incrementTotalSets() {
        guard let userId = Auth.auth().currentUser?.uid else { return }
        let userRef = db.collection("users").document(userId)
        
        userRef.updateData([
            "total_sets_completed": FieldValue.increment(Int64(1))
        ]) { error in
            if let error = error {
                print("❌ Error updating total sets: \(error.localizedDescription)")
            } else {
                print("✅ Successfully incremented total_sets_completed in Firestore!")
            }
        }
    }
    
    func decrementTotalSets() {
        guard let userId = Auth.auth().currentUser?.uid else { return }
        let userRef = db.collection("users").document(userId)
            
        userRef.updateData([
            "total_sets_completed": FieldValue.increment(Int64(-1))
        ]) { error in
            if let error = error {
                print("❌ Error decrementing total sets: \(error.localizedDescription)")
            } else {
                print("✅ Successfully decremented total_sets_completed in Firestore!")
            }
        }
    }
    
    // MARK: - Update AI Goal
    func updateAIGoal(newGoal: String, repGoal: Int, scoreGoal: Int) {
        guard let userId = Auth.auth().currentUser?.uid else { return }
        
        let userRef = db.collection("users").document(userId)
        
        // 🚀 Pushes all three fields to Firebase!
        userRef.updateData([
            "current_ai_goal": newGoal,
            "current_rep_goal": repGoal,
            "current_score_goal": scoreGoal
        ]) { error in
            if let error = error {
                print("❌ Error saving new AI Goal data: \(error.localizedDescription)")
            } else {
                print("✅ Successfully saved all AI Goals to Firestore!")
            }
        }
    }
}
