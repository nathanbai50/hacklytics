//
//  DepthChart.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//

import SwiftUI
import Charts

struct DepthChart: View {
    let data: [RepData]
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Elbow Depth")
                .font(.headline)
            
            Chart {
                ForEach(data) { rep in
                    // 🚀 1. THE STRING TRICK: Convert repNumber to a String
                    BarMark(
                        x: .value("Rep", "\(rep.repNumber)"),
                        y: .value("Angle", rep.minElbowAngle)
                    )
                    .foregroundStyle(rep.minElbowAngle > 90 ? .red : .green)
                }
                
                RuleMark(y: .value("Target", 90))
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [5]))
                    .annotation(position: .top, alignment: .leading) {
                        Text("90°").font(.caption).foregroundColor(.secondary)
                    }
            }
            .frame(height: 250)
            .chartYAxisLabel("Degrees (°)")
            .chartYAxis {
                AxisMarks(values: .stride(by: 30)) { value in
                    AxisGridLine()
                    AxisTick()
                    if let angle = value.as(Double.self) {
                        AxisValueLabel("\(Int(angle))")
                    }
                }
            }
            // 🚀 2. Look at how clean this is!
            // We deleted .chartXScale and .chartXAxis entirely.
            // SwiftUI's default categorical handling does all the hard work for us.
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }
}
