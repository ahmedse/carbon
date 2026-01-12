// File: src/components/dashboard/MetricCard.jsx
// Reusable metric card component for dashboard

import React from "react";
import { Box, Typography, LinearProgress, Tooltip, Paper } from "@mui/material";

export default function MetricCard({
  title,
  value,
  target,
  change,
  changeColor = "success",
  icon,
  barValue,
  barColor = "#43a047",
  context,
  onClick,
}) {
  const changeTextColor = {
    success: "#16a34a",
    error: "#dc2626",
    warning: "#f59e0b",
  }[changeColor] || "#6b7280";

  return (
    <Paper
      onClick={onClick}
      sx={{
        p: 2.5,
        borderRadius: 3,
        border: "1px solid #e5e7eb",
        cursor: onClick ? "pointer" : "default",
        transition: "all 0.2s",
        "&:hover": onClick ? {
          boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
          transform: "translateY(-2px)",
        } : {},
      }}
    >
      {/* Header with icon and title */}
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography fontSize="0.75rem" color="#6b7280" fontWeight={500} sx={{ mb: 0.5 }}>
            {title}
          </Typography>
          <Typography fontSize="1.75rem" fontWeight={700} color="#111827" sx={{ lineHeight: 1 }}>
            {value}
          </Typography>
        </Box>
        <Box
          sx={{
            width: 44,
            height: 44,
            borderRadius: 2,
            bgcolor: `${barColor}15`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: barColor,
          }}
        >
          {icon}
        </Box>
      </Box>

      {/* Target and change */}
      {target && (
        <Typography fontSize="0.6875rem" color="#6b7280" sx={{ mb: 1 }}>
          {target}
        </Typography>
      )}
      
      {change && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
          <Typography
            fontSize="0.75rem"
            fontWeight={600}
            sx={{ color: changeTextColor }}
          >
            {change}
          </Typography>
          <Typography fontSize="0.6875rem" color="#6b7280">
            vs last period
          </Typography>
        </Box>
      )}

      {/* Progress bar */}
      {barValue !== undefined && (
        <Box>
          <LinearProgress
            variant="determinate"
            value={barValue}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: "#f3f4f6",
              "& .MuiLinearProgress-bar": {
                bgcolor: barColor,
                borderRadius: 3,
              },
            }}
          />
          {context && (
            <Typography fontSize="0.6875rem" color="#6b7280" sx={{ mt: 0.75 }}>
              {context}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
}
