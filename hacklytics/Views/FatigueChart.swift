//
//  FatigueChart.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//


import SwiftUI
import Charts

struct FatigueChart: View {
    let data: [RepData]
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Fatigue")
                .font(.headline)
            
            Chart {
                ForEach(data) { rep in
                    LineMark(
                        x: .value("Rep", rep.repNumber),
                        y: .value("Score", rep.dtwScore)
                    )
                    .foregroundStyle(by: .value("Metric", "Form Score"))
                    .interpolationMethod(.catmullRom) // Smooths the line
                    
                    PointMark(
                        x: .value("Rep", rep.repNumber),
                        y: .value("Score", rep.dtwScore)
                    )
                }
            }
            .frame(height: 200)
            .chartYScale(domain: 0...100) // Keep the scale consistent
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }
}
