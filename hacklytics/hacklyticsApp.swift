//
//  hacklyticsApp.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/20/26.
//

import SwiftUI
import FirebaseCore

// 1. Create a Delegate to initialize Firebase at launch
class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                   didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        FirebaseApp.configure()
        return true
    }
}

@main
struct hacklyticsApp: App {
    // 2. Register the delegate
    @UIApplicationDelegateAdaptor(AppDelegate.self) var delegate
    
    // 3. 🚀 Use the shared instance of AuthManager
    // This ensures that when FirebaseManager updates the goals,
    // the UI receives the update through this exact same instance.
    @StateObject var authManager = AuthManager.shared
    
    var body: some Scene {
        WindowGroup {
            // 4. Determine which view to show based on login status
            if authManager.userSession != nil {
                RootTabView()
                    .environmentObject(authManager)
            } else {
                LoginView()
                    .environmentObject(authManager)
            }
        }
    }
}
