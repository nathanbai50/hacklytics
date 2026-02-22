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
            Text("Form Consistency")
                .font(.headline)
            
            Chart {
                ForEach(data) { rep in
                    LineMark(
                        x: .value("Rep", rep.repNumber),
                        y: .value("Score", rep.dtwScore)
                    )
                    .foregroundStyle(.blue)
                    .interpolationMethod(.catmullRom)
                    
                    PointMark(
                        x: .value("Rep", rep.repNumber),
                        y: .value("Score", rep.dtwScore)
                    )
                }
                
                // 1. Add the Goal Line (RuleMark)
                RuleMark(y: .value("Goal", 80))
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [5])) // Dashed line
                    .foregroundStyle(.secondary)
                    // 2. Add an annotation so the user knows what 80% means
                    .annotation(position: .top, alignment: .leading) {
                        Text("80%")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
            }
            .frame(height: 250)
            .chartYScale(domain: 0...100)
            .chartYAxisLabel("Accuracy (%)")
            .chartYAxis {
                AxisMarks(values: .stride(by: 25)) { value in
                    AxisGridLine()
                    AxisTick()
                    if let score = value.as(Int.self) {
                        AxisValueLabel("\(score)")
                    }
                }
            }
            .chartXScale(domain: 1...(data.map { $0.repNumber }.max() ?? 1))
            .chartXAxis {
                            AxisMarks(values: data.map { $0.repNumber }) { value in
                                if let repNum = value.as(Int.self) {
                                    
                                    let minRep = data.map { $0.repNumber }.min() ?? 1
                                    let maxRep = data.map { $0.repNumber }.max() ?? 1
                                    
                                    // 🚀 ULTIMATE FIX: Shift the first label right, and the last label left!
                                    let anchorTarget: UnitPoint = repNum == minRep ? .topLeading : (repNum == maxRep ? .topTrailing : .top)
                                    
                                    AxisValueLabel("\(repNum)", anchor: anchorTarget)
                                }
                            }
                        }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }
}
