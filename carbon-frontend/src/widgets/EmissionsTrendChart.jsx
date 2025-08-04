// src/widgets/EmissionsTrendChart.jsx
import React from "react";
import { Card, CardContent, Typography, CircularProgress } from "@mui/material";
import { Line } from "react-chartjs-2";
import useEmissionsTrend from "../hooks/useEmissionsTrend";
import ErrorBoundary from "../components/ErrorBoundary";

export default function EmissionsTrendChart({ tableId, ...props }) {
  const { data, loading, error } = useEmissionsTrend(tableId);

  if (loading) {
    return <Card><CardContent><CircularProgress /></CardContent></Card>;
  }
  if (error) {
    return <Card><CardContent>Error loading chart.</CardContent></Card>;
  }
  return (
    <Card>
      <CardContent>
        <Typography fontWeight={700} mb={1}>CO₂ Emissions Trend</Typography>
        <ErrorBoundary>
          <Line data={data.chartData} options={data.options} />
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
}