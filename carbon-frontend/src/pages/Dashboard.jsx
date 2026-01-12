// File: src/pages/Dashboard.jsx
// Interactive, data-driven carbon emissions dashboard with real-time analytics

import React, { useState } from "react";
import { Box, Grid, Typography, CircularProgress, Alert, Skeleton } from "@mui/material";
import {
  TrendingDown,
  WaterDrop,
  Bolt,
  EmojiNature,
  Insights,
  Assessment,
  BarChart,
  PieChart,
} from "@mui/icons-material";
import { Line, Bar, Pie, Doughnut } from "react-chartjs-2";
import {
  Chart,
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip as ChartTooltip,
  Legend,
} from "chart.js";

// Dashboard components
import MetricCard from "../components/dashboard/MetricCard";
import GaugeChart from "../components/dashboard/GaugeChart";
import ChartSection from "../components/dashboard/ChartSection";
import { useDashboardData } from "../components/dashboard/useDashboardData";
import { useAuth } from "../auth/AuthContext";

// Register Chart.js components
Chart.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ChartTooltip,
  Legend
);

export default function Dashboard() {
  const { user, context } = useAuth();
  const [openPanels, setOpenPanels] = useState(["impact", "trends", "quality"]);

  // Fetch real data from API
  const { data, loading, error } = useDashboardData(context?.projectId, user?.token);

  const togglePanel = (panel) => {
    setOpenPanels((prev) =>
      prev.includes(panel) ? prev.filter((p) => p !== panel) : [...prev, panel]
    );
  };

  // Loading state
  if (loading) {
    return (
      <Box sx={{ p: 4 }}>
        <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 3, mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3].map((i) => (
            <Grid item xs={12} md={4} key={i}>
              <Skeleton variant="rectangular" height={180} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">
          Failed to load dashboard data: {error}
        </Alert>
      </Box>
    );
  }

  const summary = data?.summary || {
    emissions: { total: 0, scope1: 0, scope2: 0, scope3: 0 },
    energy: { total: 0 },
    water: { total: 0 },
    dataCompleteness: 0,
    lastUpdate: new Date().toISOString().split('T')[0],
  };

  const monthlyData = data?.monthlyEmissions || [];
  const scopeData = data?.scopeBreakdown || { labels: [], data: [] };

  // Prepare chart data
  const emissionsTrend = {
    labels: monthlyData.map(d => d.month),
    datasets: [
      {
        label: "CO₂ Emissions (t)",
        data: monthlyData.map(d => d.emissions),
        borderColor: "#16a34a",
        backgroundColor: "rgba(22, 163, 74, 0.1)",
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: "#16a34a",
        fill: true,
      },
    ],
  };

  const energyTrend = {
    labels: monthlyData.map(d => d.month),
    datasets: [
      {
        label: "Energy (kWh)",
        data: monthlyData.map(d => d.energy),
        backgroundColor: "#f59e0b",
        borderRadius: 6,
        maxBarThickness: 32,
      },
    ],
  };

  const waterTrend = {
    labels: monthlyData.map(d => d.month),
    datasets: [
      {
        label: "Water (m³)",
        data: monthlyData.map(d => d.water),
        backgroundColor: "#3b82f6",
        borderRadius: 6,
        maxBarThickness: 32,
      },
    ],
  };

  const scopePie = {
    labels: scopeData.labels,
    datasets: [
      {
        data: scopeData.data,
        backgroundColor: ["#43a047", "#1e88e5", "#ff7043"],
        borderWidth: 2,
        borderColor: "#fff",
      },
    ],
  };

  // Chart options
  const lineOptions = {
    plugins: {
      legend: { display: true, position: "top" },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      y: { beginAtZero: true, grid: { color: "#f3f4f6" } },
      x: { grid: { display: false } },
    },
    responsive: true,
    maintainAspectRatio: false,
  };

  const barOptions = {
    plugins: {
      legend: { display: false },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      y: { beginAtZero: true, grid: { color: "#f3f4f6" } },
      x: { grid: { display: false } },
    },
    responsive: true,
    maintainAspectRatio: false,
  };

  const pieOptions = {
    plugins: {
      legend: { position: "bottom" },
      tooltip: { callbacks: { label: (context) => `${context.label}: ${context.parsed} t CO₂e` } },
    },
    responsive: true,
    maintainAspectRatio: false,
  };

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} color="#111827" gutterBottom>
          Carbon Emissions Dashboard
        </Typography>
        <Typography variant="body2" color="#6b7280">
          Real-time analytics from your carbon footprint data
        </Typography>
      </Box>

      {/* Top Metrics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <MetricCard
            title="Total Emissions"
            value={`${summary.emissions.total.toLocaleString()} t`}
            target="CO₂ equivalent"
            icon={<EmojiNature sx={{ fontSize: 24 }} />}
            barColor="#16a34a"
            barValue={summary.dataCompleteness}
            context={`Data completeness: ${summary.dataCompleteness}%`}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <MetricCard
            title="Energy Consumption"
            value={`${Math.round(summary.energy.total / 1000).toLocaleString()}k kWh`}
            target="Total energy used"
            icon={<Bolt sx={{ fontSize: 24 }} />}
            barColor="#f59e0b"
            barValue={75}
            context="Tracking across all facilities"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <MetricCard
            title="Water Usage"
            value={`${Math.round(summary.water.total / 1000).toLocaleString()}k m³`}
            target="Total water consumed"
            icon={<WaterDrop sx={{ fontSize: 24 }} />}
            barColor="#3b82f6"
            barValue={82}
            context="Conservation programs active"
          />
        </Grid>
      </Grid>

      {/* Gauges */}
      <Box sx={{ mb: 4, display: "flex", gap: 3, flexWrap: "wrap", justifyContent: "center" }}>
        <GaugeChart
          value={summary.dataCompleteness}
          label="Data Quality"
          color="#8b5cf6"
          size={140}
        />
        <GaugeChart
          value={summary.emissions.scope1}
          label="Scope 1"
          max={Math.max(summary.emissions.scope1, summary.emissions.scope2, summary.emissions.scope3, 100)}
          color="#43a047"
          size={140}
          unit=" t"
        />
        <GaugeChart
          value={summary.emissions.scope2}
          label="Scope 2"
          max={Math.max(summary.emissions.scope1, summary.emissions.scope2, summary.emissions.scope3, 100)}
          color="#1e88e5"
          size={140}
          unit=" t"
        />
        <GaugeChart
          value={summary.emissions.scope3}
          label="Scope 3"
          max={Math.max(summary.emissions.scope1, summary.emissions.scope2, summary.emissions.scope3, 100)}
          color="#ff7043"
          size={140}
          unit=" t"
        />
      </Box>

      {/* Chart Sections (Accordions) */}
      <ChartSection
        id="impact"
        title="Emissions Impact Analysis"
        subtitle="CO₂ emissions trends and scope breakdown"
        icon={<TrendingDown />}
        expanded={openPanels.includes("impact")}
        onChange={() => togglePanel("impact")}
      >
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Box sx={{ height: 300 }}>
              <Typography variant="subtitle2" color="#6b7280" sx={{ mb: 2 }}>
                Monthly Emissions Trend
              </Typography>
              <Line data={emissionsTrend} options={lineOptions} />
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box sx={{ height: 300 }}>
              <Typography variant="subtitle2" color="#6b7280" sx={{ mb: 2 }}>
                Scope Breakdown
              </Typography>
              <Pie data={scopePie} options={pieOptions} />
            </Box>
          </Grid>
        </Grid>
      </ChartSection>

      <ChartSection
        id="trends"
        title="Resource Consumption Trends"
        subtitle="Energy and water usage patterns"
        icon={<BarChart />}
        expanded={openPanels.includes("trends")}
        onChange={() => togglePanel("trends")}
      >
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Box sx={{ height: 300 }}>
              <Typography variant="subtitle2" color="#6b7280" sx={{ mb: 2 }}>
                Energy Consumption (kWh)
              </Typography>
              <Bar data={energyTrend} options={barOptions} />
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Box sx={{ height: 300 }}>
              <Typography variant="subtitle2" color="#6b7280" sx={{ mb: 2 }}>
                Water Usage (m³)
              </Typography>
              <Bar data={waterTrend} options={barOptions} />
            </Box>
          </Grid>
        </Grid>
      </ChartSection>

      <ChartSection
        id="quality"
        title="Data Quality & Insights"
        subtitle="Monitoring data completeness and reliability"
        icon={<Assessment />}
        expanded={openPanels.includes("quality")}
        onChange={() => togglePanel("quality")}
      >
        <Box sx={{ p: 3, bgcolor: "#f9fafb", borderRadius: 2 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="h6" fontWeight={600} color="#111827" gutterBottom>
                Data Coverage
              </Typography>
              <Typography variant="body2" color="#6b7280">
                {summary.dataCompleteness}% of expected data points collected
              </Typography>
              <Typography variant="body2" color="#6b7280" sx={{ mt: 1 }}>
                Last updated: {summary.lastUpdate}
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="h6" fontWeight={600} color="#111827" gutterBottom>
                Key Insights
              </Typography>
              <Typography variant="body2" color="#6b7280">
                • Scope 2 represents the largest emissions source
              </Typography>
              <Typography variant="body2" color="#6b7280">
                • Energy consumption shows seasonal patterns
              </Typography>
              <Typography variant="body2" color="#6b7280">
                • Water conservation efforts are effective
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </ChartSection>

      {/* Footer */}
      <Box sx={{ mt: 6, pt: 4, borderTop: "1px solid #e5e7eb", textAlign: "center" }}>
        <Typography variant="body2" color="#9ca3af">
          Dashboard powered by real-time data from your carbon accounting system
        </Typography>
      </Box>
    </Box>
  );
}