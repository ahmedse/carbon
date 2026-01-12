// File: src/components/dashboard/GaugeChart.jsx
// SVG Gauge chart component for professional data visualization

import React from "react";
import { Box, Typography } from "@mui/material";

export default function GaugeChart({ 
  value, 
  label, 
  min = 0, 
  max = 100, 
  color = "#16a34a",
  size = 120,
  unit = "%"
}) {
  const radius = size * 0.38;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;
  const percent = Math.min(1, Math.max(0, (value - min) / (max - min)));
  const offset = circumference * (1 - percent);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <svg width={size} height={size * 0.75} viewBox={`0 0 ${size} ${size * 0.75}`}>
        <g>
          {/* Background circle */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="#f3f4f6"
            strokeWidth={size * 0.08}
            strokeDasharray={circumference}
            strokeDashoffset={0}
          />
          {/* Progress circle */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={size * 0.08}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cy})`}
            style={{
              transition: "stroke-dashoffset 0.5s ease",
            }}
          />
          {/* Value text */}
          <text 
            x={cx} 
            y={cy + 5} 
            fontSize={size * 0.23} 
            fontWeight="bold" 
            textAnchor="middle" 
            fill="#111827"
          >
            {Math.round(value)}{unit}
          </text>
          {/* Label text */}
          <text 
            x={cx} 
            y={cy + size * 0.22} 
            fontSize={size * 0.11} 
            textAnchor="middle" 
            fill="#6b7280"
          >
            {label}
          </text>
        </g>
      </svg>
    </Box>
  );
}
