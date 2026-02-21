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
                    BarMark(
                        x: .value("Rep", rep.repNumber),
                        y: .value("Angle", rep.minElbowAngle)
                    )
                    // Visual feedback: Red if too shallow, Green if deep enough
                    .foregroundStyle(rep.minElbowAngle > 90 ? .red : .green)
                }
                
                RuleMark(y: .value("Target", 90))
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [5]))
                    .annotation(position: .top, alignment: .leading) {
                        Text("Goal").font(.caption).foregroundColor(.secondary)
                    }
            }
            .frame(height: 150)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }
}
