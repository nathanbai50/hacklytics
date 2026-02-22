//
//  BodyAngleChart.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/22/26.
//


//
//  BodyAngleChart.swift
//  hacklytics
//
//  Created by Nathan Bai on 2/21/26.
//
import SwiftUI
import Charts

struct BodyAngleChart: View {
    let data: [RepData]
    
    var body: some View {
        VStack(alignment: .leading) {
            Text("Body Alignment")
                .font(.headline)
            
            Chart {
                ForEach(data) { rep in
                    BarMark(
                        x: .value("Rep", "\(rep.repNumber)"),
                        y: .value("Angle", rep.avgBodyAngle)
                    )
                    .foregroundStyle(rep.avgBodyAngle < 150 ? .red : .green)
                }
                
                RuleMark(y: .value("Target", 150))
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [5]))
                    .annotation(position: .top, alignment: .leading) {
                        Text("150°").font(.caption).foregroundColor(.secondary)
                    }
            }
            .frame(height: 250)
            .chartYAxisLabel("Degrees (°)")
            .chartYScale(domain: 120...190)
            .chartYAxis {
                AxisMarks(values: .stride(by: 15)) { value in
                    AxisGridLine()
                    AxisTick()
                    if let angle = value.as(Double.self) {
                        AxisValueLabel("\(Int(angle))")
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
