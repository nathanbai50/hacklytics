import SwiftUI

struct UserProfileView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var workoutHistory: [SetData] = []
    @State private var isLoading = true
    
    func scoreColor(for score: Int) -> Color {
        if score >= 80 { return .green }
        if score >= 60 { return .orange }
        return .red
    }
    
    var body: some View {
        NavigationStack {
            List {
                // MARK: - Header & Stats
                VStack(alignment: .leading, spacing: 25) {
                    
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Hello, \(authManager.currentUserProfile?.fullName.components(separatedBy: " ").first ?? "Athlete")!")
                            .font(.largeTitle)
                            .bold()
                        
                        // MARK: - The AI Goal Card
                                            VStack(alignment: .leading, spacing: 15) {
                                                
                                                // 1. Title and AI Text
                                                VStack(alignment: .leading, spacing: 8) {
                                                    HStack {
                                                        Image(systemName: "sparkles")
                                                            .foregroundColor(.purple)
                                                        Text("Your Goal")
                                                            .font(.subheadline)
                                                            .bold()
                                                            .foregroundColor(.purple)
                                                    }
                                                    
                                                    Text(authManager.currentUserProfile?.currentAIGoal ?? "Keep pushing! Your coach is analyzing your baseline to generate your next goal.")
                                                        .font(.body)
                                                        .foregroundColor(.primary)
                                                        .fixedSize(horizontal: false, vertical: true) // Prevents text from truncating
                                                }
                                                

                                                if let repGoal = authManager.currentUserProfile?.currentRepGoal,
                                                   let scoreGoal = authManager.currentUserProfile?.currentScoreGoal,
                                                   repGoal > 0, // 🚀 This prevents "0 / 0" bars from showing
                                                   scoreGoal > 0,
                                                   let aiGoal = authManager.currentUserProfile?.currentAIGoal,
                                                      aiGoal != "Keep pushing! Your coach is analyzing your baseline to generate your next goal."
                                                {
                                                    
                                                    // Calculate stats only when goals exist
                                                    let maxReps = workoutHistory.map { $0.totalValidReps }.max() ?? 0
                                                    let avgScore = workoutHistory.isEmpty ? 0 : workoutHistory.reduce(0) { $0 + $1.overallScore } / workoutHistory.count
                                                    
                                                    VStack(spacing: 12) {
                                                        // --- REP GOAL BAR ---
                                                        VStack(alignment: .leading, spacing: 4) {
                                                            HStack {
                                                                Text("Max Reps")
                                                                    .font(.caption2)
                                                                    .bold()
                                                                    .foregroundColor(.gray)
                                                                Spacer()
                                                                Text("\(maxReps) / \(repGoal)")
                                                                    .font(.caption2)
                                                                    .bold()
                                                                    .foregroundColor(maxReps >= repGoal ? .green : .white)
                                                            }
                                                            ProgressView(value: Double(min(maxReps, repGoal)), total: Double(repGoal))
                                                                .tint(maxReps >= repGoal ? .green : .purple)
                                                        }
                                                        
                                                        // --- SCORE GOAL BAR ---
                                                        VStack(alignment: .leading, spacing: 4) {
                                                            HStack {
                                                                Text("Average Score")
                                                                    .font(.caption2)
                                                                    .bold()
                                                                    .foregroundColor(.gray)
                                                                Spacer()
                                                                Text("\(avgScore) / \(scoreGoal)")
                                                                    .font(.caption2)
                                                                    .bold()
                                                                    .foregroundColor(avgScore >= scoreGoal ? .green : .white)
                                                            }
                                                            ProgressView(value: Double(min(avgScore, scoreGoal)), total: Double(scoreGoal))
                                                                .tint(avgScore >= scoreGoal ? .green : scoreColor(for: avgScore))
                                                        }
                                                    }
                                                    .padding(.top, 5)
                                                }
                                            }
                                            .padding()
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                            .background(RoundedRectangle(cornerRadius: 15).fill(Color.purple.opacity(0.1)))
                                            .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.purple.opacity(0.3), lineWidth: 1))                   }
                    
                    HStack {
                        VStack(alignment: .center) {
                            // 🚀 1. The UI Fix: Read directly from Firebase instead of the local array!
                            Text("\(authManager.currentUserProfile?.totalSetsCompleted ?? 0)")
                                .font(.title)
                                .bold()
                            Text("Total Sets")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.secondarySystemBackground))
                        .cornerRadius(12)
                        
                        VStack(alignment: .center) {
                            let avg = workoutHistory.isEmpty ? 0 : workoutHistory.reduce(0) { $0 + $1.overallScore } / workoutHistory.count
                            Text("\(avg)")
                                .font(.title)
                                .bold()
                                .foregroundColor(scoreColor(for: avg))
                            Text("Avg Score")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.secondarySystemBackground))
                        .cornerRadius(12)
                    }
                    
                    Text("Past sets")
                        .font(.title2)
                        .bold()
                }
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 20, leading: 16, bottom: 10, trailing: 16))
                
                // MARK: - Workout History Cards
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                        .listRowSeparator(.hidden)
                        .listRowBackground(Color.clear)
                } else if workoutHistory.isEmpty {
                    Text("No sets yet. Go record your first set!")
                        .foregroundColor(.secondary)
                        .listRowSeparator(.hidden)
                        .listRowBackground(Color.clear)
                } else {
                    ForEach(workoutHistory) { set in
                        ZStack {
                            SetCardView(set: set)
                            
                            NavigationLink(destination: PushupResultsView(viewModel: createTempViewModel(for: set))) {
                                EmptyView()
                            }
                            .opacity(0)
                        }
                        .listRowSeparator(.hidden)
                        .listRowBackground(Color.clear)
                        .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                    }
                    .onDelete(perform: deleteWorkoutLocallyAndRemotely)
                }
            }
            .listStyle(.plain)
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Sign Out") {
                        authManager.signOut()
                    }
                    .foregroundColor(.red)
                }
            }
            .onAppear {
                startLiveListener()
            }
        }
    }
    
    // MARK: - Functions
    
    private func startLiveListener() {
            // 1. Listen to the Workout History
            FirebaseManager.shared.listenToWorkoutHistory { fetchedWorkouts in
                DispatchQueue.main.async {
                    self.workoutHistory = fetchedWorkouts
                    self.isLoading = false
                }
            }
            
            // 🚀 2. NEW: Listen to the User Profile Document
            // This is what tells your UI that the "totalSetsCompleted" number changed!
            FirebaseManager.shared.listenToUserProfile { updatedProfile in
                DispatchQueue.main.async {
                    if let liveProfile = updatedProfile {
                        self.authManager.currentUserProfile = liveProfile
                    }
                }
            }
        }
    
    // Handles the swipe action
    private func deleteWorkoutLocallyAndRemotely(at offsets: IndexSet) {
        offsets.forEach { index in
            let workoutToDelete = workoutHistory[index]
            
            if let documentId = workoutToDelete.id {
                // Delete from Firestore
                FirebaseManager.shared.deleteWorkout(workoutId: documentId)
                
                // 🚀 2. The Logic Fix: Tell Firestore to decrement the total sets count
                FirebaseManager.shared.decrementTotalSets()
            }
        }
        
        // Remove it from the UI instantly for a smooth animation
        workoutHistory.remove(atOffsets: offsets)
    }
    
    private func createTempViewModel(for set: SetData) -> PushupViewModel {
        let vm = PushupViewModel()
        vm.currentSet = set
        return vm
    }
}
