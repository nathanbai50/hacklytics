//
//  AuthManager.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//
import Foundation
import FirebaseAuth
import FirebaseFirestore
import Combine
class AuthManager: ObservableObject {
    @Published var userSession: FirebaseAuth.User?
    @Published var currentUserProfile: UserProfile?
    static let shared = AuthManager()

    init() {
        // This listener automatically fires when the app opens to check if they are already logged in
        Auth.auth().addStateDidChangeListener { [weak self] auth, user in
            self?.userSession = user
            if let user = user {
                self?.fetchUserProfile(uid: user.uid)
            }
        }
    }

    func signUp(email: String, password: String, fullName: String) {
        Auth.auth().createUser(withEmail: email, password: password) { result, error in
            if let error = error {
                print("❌ Sign Up Error: \(error.localizedDescription)")
                return
            }

            guard let uid = result?.user.uid else { return }

            // Create the new user profile model
            let newUser = UserProfile(id: uid, fullName: fullName, email: email)

            // Save it to Firestore
            do {
                try Firestore.firestore().collection("users").document(uid).setData(from: newUser)
                self.currentUserProfile = newUser
            } catch {
                print("❌ Error saving user to Firestore: \(error.localizedDescription)")
            }
        }
    }

    func login(email: String, password: String) {
        Auth.auth().signIn(withEmail: email, password: password) { result, error in
            if let error = error {
                print("❌ Login Error: \(error.localizedDescription)")
            }
        }
    }

    func signOut() {
        do {
            try Auth.auth().signOut()
            self.userSession = nil
            self.currentUserProfile = nil
        } catch {
            print("❌ Sign Out Error: \(error.localizedDescription)")
        }
    }

    private func fetchUserProfile(uid: String) {
        Firestore.firestore().collection("users").document(uid).getDocument { snapshot, error in
            if let snapshot = snapshot, snapshot.exists {
                do {
                    self.currentUserProfile = try snapshot.data(as: UserProfile.self)
                } catch {
                    print("❌ Error decoding user profile")
                }
            }
        }
    }
}
