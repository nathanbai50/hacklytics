//
//  RootTabView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import SwiftUI

// 1. Define your tabs
enum AppTab: String, CaseIterable {
    case camera = "Camera"
    case profile = "Profile"
    
    var icon: String {
        switch self {
        case .camera: return "camera.viewfinder"
        case .profile: return "person.crop.circle"
        }
    }
}

// 2. The Main Container
struct RootTabView: View {
    @State private var selectedTab: AppTab = .camera
    
    // 🚀 1. The new master switch for tab bar visibility
    @State private var isTabBarHidden: Bool = false
    
    var body: some View {
        ZStack(alignment: .bottom) {
            // MARK: - The Main Screens
            TabView(selection: $selectedTab) {
                // 🚀 2. Pass the switch down into your MainAppView
                MainAppView(isTabBarHidden: $isTabBarHidden)
                    .tag(AppTab.camera)
                    .toolbar(.hidden, for: .tabBar)
                
                UserProfileView()
                    .tag(AppTab.profile)
                    .toolbar(.hidden, for: .tabBar)
            }
            .ignoresSafeArea()
            
            // MARK: - The Premium Floating Tab Bar
            // 🚀 3. Only show the tab bar if it's not hidden
            if !isTabBarHidden {
                CustomTabBar(selectedTab: $selectedTab)
                    // Add a sleek animation so it slides down off the screen when hiding
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .zIndex(2) // Guarantee it stays on top while animating
            }
        }
        .preferredColorScheme(.dark)
    }
}
// 3. The Custom Floating Pill UI
struct CustomTabBar: View {
    @Binding var selectedTab: AppTab
    
    var body: some View {
        HStack(spacing: 15) {
            ForEach(AppTab.allCases, id: \.self) { tab in
                Button {
                    // Smooth, springy expansion animation
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
                        selectedTab = tab
                    }
                    let impact = UIImpactFeedbackGenerator(style: .light)
                    impact.impactOccurred()
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: tab.icon)
                            .font(.system(size: 20, weight: selectedTab == tab ? .semibold : .regular))
                        
                        // Only show text if this tab is currently selected
                        if selectedTab == tab {
                            Text(tab.rawValue)
                                .font(.system(size: 15, weight: .bold))
                                .fixedSize() // Prevents text from getting squished during animation
                        }
                    }
                    // Selected is black (on white pill), Unselected is gray
                    .foregroundColor(selectedTab == tab ? .black : .gray)
                    .padding(.vertical, 12)
                    .padding(.horizontal, selectedTab == tab ? 20 : 16)
                    .background(
                        // The expanding white pill background
                        selectedTab == tab ? Capsule().fill(Color.white) : Capsule().fill(Color.clear)
                    )
                }
            }
        }
        .padding(8) // Inner padding to create the black border around the pills
        // Deep, pure dark background exactly like the reference image
        .background(Color(red: 0.08, green: 0.08, blue: 0.1))
        .clipShape(Capsule())
        .shadow(color: .black.opacity(0.4), radius: 10, x: 0, y: 5)
        .padding(.bottom, 30) // Hovers right below the camera button
        
        // 🚀 NEW: The Swipe Gesture!
        .gesture(
            DragGesture()
                .onEnded { value in
                    let swipeDistance = value.translation.width
                    let swipeThreshold: CGFloat = 20 // The minimum pixels needed to trigger a change
                    
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
                        if swipeDistance > swipeThreshold {
                            // Swiped Right -> Select Profile (which is on the right)
                            selectedTab = .profile
                        } else if swipeDistance < -swipeThreshold {
                            // Swiped Left -> Select Camera (which is on the left)
                            selectedTab = .camera
                        }
                    }
                    
                    // Fire the haptic feedback when the swipe successfully triggers
                    if abs(swipeDistance) > swipeThreshold {
                        let impact = UIImpactFeedbackGenerator(style: .light)
                        impact.impactOccurred()
                    }
                }
        )
    }
}
