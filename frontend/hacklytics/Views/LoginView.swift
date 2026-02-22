//
//  LoginView.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import SwiftUI

// 1. Custom modifier to style the text fields exactly like the design
struct MonotoneTextFieldStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding()
            .background(Color.black)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
            .foregroundColor(.white)
            .autocapitalization(.none)
            .disableAutocorrection(true)
    }
}

struct LoginView: View {
    @EnvironmentObject var authManager: AuthManager
    
    @State private var email = ""
    @State private var password = ""
    @State private var fullName = ""
    @State private var isCreatingAccount = true // Default to sign up based on the image
    
    var body: some View {
        ZStack {
            // Force the background to be deep black
            Color.black.ignoresSafeArea()
            
            VStack(alignment: .leading, spacing: 30) {
                
                // MARK: - Header section
                VStack(alignment: .leading, spacing: 10) {
                    // Logo Placeholder (Using a stack icon similar to the reference)
                    Image(systemName: "figure.strengthtraining.traditional")
                        .font(.system(size: 32))
                        .foregroundColor(.white)
                        .padding(.bottom, 10)
                    
                    // The App Title
                    Text("Welcome to ")
                        .font(.largeTitle)
                        .foregroundColor(.white)
                    + Text("Pushup Pal.")
                        .font(.largeTitle)
                        .bold()
                        .foregroundColor(.white)
                    
                    // Dynamic subtitle
                    Text(isCreatingAccount ? "Let's create your new account to get started." : "Log in to your account to continue.")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                }
                .padding(.top, 50)
                
                // MARK: - Input Fields
                VStack(spacing: 16) {
                    if isCreatingAccount {
                        TextField("", text: $fullName, prompt: Text("Enter your full name").foregroundColor(.gray))
                            .modifier(MonotoneTextFieldStyle())
                    }
                    
                    TextField("", text: $email, prompt: Text("Enter your email").foregroundColor(.gray))
                        .keyboardType(.emailAddress)
                        .modifier(MonotoneTextFieldStyle())
                    
                    SecureField("", text: $password, prompt: Text("Enter your password").foregroundColor(.gray))
                        .modifier(MonotoneTextFieldStyle())
                }
                
                // MARK: - Primary Action Button
                Button(action: {
                    if isCreatingAccount {
                        authManager.signUp(email: email, password: password, fullName: fullName)
                    } else {
                        authManager.login(email: email, password: password)
                    }
                }) {
                    Text(isCreatingAccount ? "Continue with Email" : "Log In")
                        .font(.headline)
                        .foregroundColor(.black) // Black text on white button
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.white)
                        .cornerRadius(10)
                }
                .padding(.top, 10)
                
                Spacer()
                
                // MARK: - Footer
                VStack(spacing: 25) {
                    // Terms and Conditions
                    Text("Made for Hacklytics 2026")
                    
                    // Toggle State Link
                    Button(action: {
                        withAnimation {
                            isCreatingAccount.toggle()
                        }
                    }) {
                        HStack(spacing: 4) {
                            Text(isCreatingAccount ? "Already signed up?" : "Don't have an account?")
                                .foregroundColor(.gray)
                            Text(isCreatingAccount ? "Sign in" : "Sign up")
                                .underline()
                                .foregroundColor(.white)
                        }
                        .font(.footnote)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.bottom, 20)
            }
            .padding(.horizontal, 24)
        }
        // Force dark mode coloring so the keyboard matches the aesthetic
        .preferredColorScheme(.dark)
    }
}
