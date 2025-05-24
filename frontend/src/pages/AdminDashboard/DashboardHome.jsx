// File: frontend/src/pages/AdminDashboard/DashboardHome.jsx
// Purpose: Home view for the admin dashboard, shows stats and charts.
// Location: frontend/src/pages/AdminDashboard/

import React from "react";
import { Box, Grid, Typography } from "@mui/material";
import StatCard from "./components/StatCard";
import ChartCard from "./components/ChartCard";

// Demo data for statistics
const stats = [
  { label: "Total CO₂ Emissions", value: "12,800", unit: "tons/year" },
  { label: "Electricity Usage", value: "6,400", unit: "MWh/year" },
  { label: "Water Consumption", value: "58,000", unit: "m³/year" },
  { label: "Gas Usage", value: "3,200", unit: "GJ/year" },
  { label: "Active Alerts", value: "4", unit: "" },
];

/**
 * DashboardHome component.
 * Displays summary statistics and charts for the admin dashboard.
 * @param {object} context - The current context (project/cycle/module).
 */
export default function DashboardHome({ context }) {
  return (
    <Box>
      <Typography variant="h5" fontWeight={600} gutterBottom>
        Welcome, Admin!
        {context && context.project && <> (Project: {context.project})</>}
        {context && context.cycle && <> (Cycle: {context.cycle})</>}
        {context && context.module && <> (Module: {context.module})</>}
      </Typography>

      <Grid container spacing={2} sx={{ mt: 1, mb: 3 }}>
        {stats.map((s) => (
          <Grid item xs={12} sm={6} md={3} key={s.label}>
            <StatCard label={s.label} value={s.value} unit={s.unit} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={7}>
          <ChartCard
            title="CO₂ Emissions Trend"
            type="line"
            data={[
              { month: "Jan", value: 1000 },
              { month: "Feb", value: 1100 },
              { month: "Mar", value: 1050 },
              { month: "Apr", value: 1200 },
              { month: "May", value: 1150 },
              { month: "Jun", value: 1230 },
            ]}
          />
        </Grid>
        <Grid item xs={12} md={5}>
          <ChartCard
            title="Resource Usage Breakdown"
            type="pie"
            data={[
              { name: "Electricity", value: 54 },
              { name: "Water", value: 32 },
              { name: "Gas", value: 14 },
            ]}
          />
        </Grid>
      </Grid>
    </Box>
  );
}