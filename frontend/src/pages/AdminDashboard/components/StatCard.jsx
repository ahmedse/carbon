// src/pages/AdminDashboard/components/StatCard.jsx
import React from "react";
import { Card, CardContent, Typography, Box } from "@mui/material";

const StatCard = ({ label, value, unit }) => (
  <Card
    sx={{
      background: "linear-gradient(135deg, #e8f5e9 0%, #e3f2fd 100%)",
      boxShadow: 2,
      borderRadius: 3,
    }}
  >
    <CardContent>
      <Typography
        variant="subtitle2"
        color="text.secondary"
        sx={{ fontWeight: 500, mb: 1 }}
      >
        {label}
      </Typography>
      <Box sx={{ display: "flex", alignItems: "baseline" }}>
        <Typography
          variant="h5"
          sx={{ fontWeight: 700, mr: 1, fontSize: "2rem" }}
        >
          {value}
        </Typography>
        {unit && (
          <Typography color="text.secondary" sx={{ fontSize: "1rem" }}>
            {unit}
          </Typography>
        )}
      </Box>
    </CardContent>
  </Card>
);

export default StatCard;