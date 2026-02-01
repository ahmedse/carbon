// File: src/pages/EmissionsDashboard.jsx
// Professional Carbon Emissions Dashboard with beautiful visualizations

import React, { useState, useEffect, useMemo } from "react";
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Chip,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tooltip,
  IconButton,
  Paper,
  LinearProgress,
  Button,
  Stack,
} from "@mui/material";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Bar, Doughnut, Pie } from "react-chartjs-2";
import {
  TrendingUp,
  TrendingDown,
  Factory,
  Bolt,
  LocalShipping,
  Refresh,
  Download,
  CalendarMonth,
  Assessment,
  Nature,
  CloudQueue,
  Speed,
} from "@mui/icons-material";
import { fetchEmissionsDashboard, triggerCalculations } from "../api/emissions";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  ChartTooltip,
  Legend,
  Filler
);

// ============ Styled Components ============

const GlassCard = ({ children, sx = {}, ...props }) => (
  <Card
    elevation={0}
    sx={{
      background: "rgba(255, 255, 255, 0.95)",
      backdropFilter: "blur(10px)",
      border: "1px solid rgba(0, 0, 0, 0.08)",
      borderRadius: 3,
      transition: "all 0.3s ease",
      "&:hover": {
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.08)",
        transform: "translateY(-2px)",
      },
      ...sx,
    }}
    {...props}
  >
    {children}
  </Card>
);

const StatCard = ({ title, value, unit, subtitle, icon, color, trend, trendValue }) => (
  <GlassCard>
    <CardContent sx={{ p: 3 }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", mb: 2 }}>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: `linear-gradient(135deg, ${color}20, ${color}40)`,
            color: color,
          }}
        >
          {icon}
        </Box>
        {trend && (
          <Chip
            size="small"
            icon={trend === "up" ? <TrendingUp fontSize="small" /> : <TrendingDown fontSize="small" />}
            label={trendValue}
            sx={{
              bgcolor: trend === "up" ? "#fee2e2" : "#d1fae5",
              color: trend === "up" ? "#dc2626" : "#059669",
              fontWeight: 600,
              "& .MuiChip-icon": {
                color: "inherit",
              },
            }}
          />
        )}
      </Box>
      <Typography variant="h3" sx={{ fontWeight: 700, color: "#111827", mb: 0.5 }}>
        {typeof value === "number" ? value.toLocaleString() : value}
        <Typography component="span" variant="h6" sx={{ ml: 1, fontWeight: 400, color: "#6b7280" }}>
          {unit}
        </Typography>
      </Typography>
      <Typography variant="body2" sx={{ color: "#6b7280", fontWeight: 500 }}>
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="caption" sx={{ color: "#9ca3af", display: "block", mt: 0.5 }}>
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </GlassCard>
);

const ScopeCard = ({ scope, name, value, percentage, color }) => (
  <Box sx={{ flex: 1, minWidth: 200 }}>
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          bgcolor: color,
        }}
      />
      <Typography variant="body2" sx={{ fontWeight: 600, color: "#374151" }}>
        {name}
      </Typography>
    </Box>
    <Typography variant="h5" sx={{ fontWeight: 700, color: "#111827" }}>
      {value.toLocaleString()}
      <Typography component="span" variant="body2" sx={{ ml: 0.5, color: "#6b7280" }}>
        t CO₂e
      </Typography>
    </Typography>
    <Box sx={{ mt: 1, display: "flex", alignItems: "center", gap: 1 }}>
      <LinearProgress
        variant="determinate"
        value={percentage}
        sx={{
          flex: 1,
          height: 6,
          borderRadius: 3,
          bgcolor: `${color}20`,
          "& .MuiLinearProgress-bar": {
            bgcolor: color,
            borderRadius: 3,
          },
        }}
      />
      <Typography variant="caption" sx={{ fontWeight: 600, color: "#6b7280", minWidth: 40 }}>
        {percentage.toFixed(1)}%
      </Typography>
    </Box>
  </Box>
);

// ============ Main Component ============

export default function EmissionsDashboard({ projectId }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [selectedYear, setSelectedYear] = useState(2025); // Demo data year
  const [recalculating, setRecalculating] = useState(false);
  
  const token = localStorage.getItem("access");

  // Fetch dashboard data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchEmissionsDashboard(
          { project_id: projectId, year: selectedYear },
          token
        );
        setData(result);
      } catch (err) {
        console.error("Failed to load emissions dashboard:", err);
        setError(err.message || "Failed to load emissions data");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [projectId, selectedYear, token]);

  // Handle recalculation
  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      await triggerCalculations({ project_id: projectId, recalculate: true }, token);
      // Refresh data
      const result = await fetchEmissionsDashboard(
        { project_id: projectId, year: selectedYear },
        token
      );
      setData(result);
    } catch (err) {
      console.error("Recalculation failed:", err);
    } finally {
      setRecalculating(false);
    }
  };

  // Scope colors
  const scopeColors = {
    1: "#10b981", // Green - Scope 1
    2: "#3b82f6", // Blue - Scope 2
    3: "#f59e0b", // Orange - Scope 3
  };

  // Chart configurations
  const monthlyTrendChart = useMemo(() => {
    if (!data?.monthly_trend) return null;

    return {
      labels: data.monthly_trend.map((m) => m.month_name),
      datasets: [
        {
          label: "Scope 1",
          data: data.monthly_trend.map((m) => m.scope1),
          borderColor: scopeColors[1],
          backgroundColor: `${scopeColors[1]}20`,
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: "Scope 2",
          data: data.monthly_trend.map((m) => m.scope2),
          borderColor: scopeColors[2],
          backgroundColor: `${scopeColors[2]}20`,
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: "Scope 3",
          data: data.monthly_trend.map((m) => m.scope3),
          borderColor: scopeColors[3],
          backgroundColor: `${scopeColors[3]}20`,
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
      ],
    };
  }, [data]);

  const scopePieChart = useMemo(() => {
    if (!data?.scope_breakdown) return null;

    return {
      labels: data.scope_breakdown.map((s) => s.scope_name),
      datasets: [
        {
          data: data.scope_breakdown.map((s) => s.co2e_tonnes),
          backgroundColor: data.scope_breakdown.map((s) => scopeColors[s.scope]),
          borderColor: "#fff",
          borderWidth: 3,
          hoverOffset: 8,
        },
      ],
    };
  }, [data]);

  const categoryBarChart = useMemo(() => {
    if (!data?.category_breakdown) return null;

    // Group by category
    const categories = {};
    data.category_breakdown.forEach((c) => {
      if (!categories[c.category_name]) {
        categories[c.category_name] = 0;
      }
      categories[c.category_name] += c.co2e_tonnes;
    });

    const sortedCategories = Object.entries(categories)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);

    return {
      labels: sortedCategories.map(([name]) => name),
      datasets: [
        {
          label: "Emissions (t CO₂e)",
          data: sortedCategories.map(([, value]) => value),
          backgroundColor: [
            "#10b981",
            "#3b82f6",
            "#f59e0b",
            "#8b5cf6",
            "#ef4444",
            "#06b6d4",
            "#ec4899",
            "#84cc16",
          ],
          borderRadius: 8,
          maxBarThickness: 50,
        },
      ],
    };
  }, [data]);

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: {
        position: "top",
        labels: {
          usePointStyle: true,
          padding: 20,
          font: { size: 12, weight: 500 },
        },
      },
      tooltip: {
        backgroundColor: "#1f2937",
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (context) => `${context.dataset.label}: ${context.parsed.y.toLocaleString()} t CO₂e`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: "#f3f4f6" },
        ticks: {
          font: { size: 11 },
          callback: (value) => `${value} t`,
        },
      },
      x: {
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
    },
  };

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1f2937",
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (context) => `${context.parsed.x.toLocaleString()} t CO₂e`,
        },
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: { color: "#f3f4f6" },
        ticks: {
          font: { size: 11 },
          callback: (value) => `${value} t`,
        },
      },
      y: {
        grid: { display: false },
        ticks: { font: { size: 11 } },
      },
    },
  };

  const pieChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          usePointStyle: true,
          padding: 16,
          font: { size: 12, weight: 500 },
        },
      },
      tooltip: {
        backgroundColor: "#1f2937",
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (context) => {
            const total = context.dataset.data.reduce((a, b) => a + b, 0);
            const percentage = ((context.parsed / total) * 100).toFixed(1);
            return `${context.label}: ${context.parsed.toLocaleString()} t CO₂e (${percentage}%)`;
          },
        },
      },
    },
  };

  // Loading state
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 400 }}>
        <CircularProgress size={48} sx={{ color: "#10b981" }} />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  // No data state
  if (!data || data.calculation_count === 0) {
    return (
      <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
        <Paper sx={{ p: 6, textAlign: "center", bgcolor: "#f9fafb" }}>
          <CloudQueue sx={{ fontSize: 64, color: "#9ca3af", mb: 2 }} />
          <Typography variant="h5" sx={{ fontWeight: 600, color: "#374151", mb: 1 }}>
            No Emissions Data Yet
          </Typography>
          <Typography variant="body1" sx={{ color: "#6b7280", mb: 3 }}>
            Run calculations to see your carbon emissions dashboard
          </Typography>
          <Button
            variant="contained"
            startIcon={<Refresh />}
            onClick={handleRecalculate}
            sx={{
              bgcolor: "#10b981",
              "&:hover": { bgcolor: "#059669" },
              borderRadius: 2,
              px: 4,
            }}
          >
            Calculate Emissions
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        maxWidth: 1600,
        mx: "auto",
        px: { xs: 2, md: 4 },
        py: 4,
        background: "linear-gradient(135deg, #f0fdf4 0%, #f8fafc 100%)",
        minHeight: "100vh",
      }}
    >
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 4 }}>
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 800,
              background: "linear-gradient(135deg, #10b981, #059669)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              mb: 0.5,
            }}
          >
            Carbon Emissions Dashboard
          </Typography>
          <Typography variant="body1" sx={{ color: "#6b7280" }}>
            {data.reporting_period?.name || `Year ${selectedYear}`} • Last updated:{" "}
            {data.last_updated
              ? new Date(data.last_updated).toLocaleDateString()
              : "N/A"}
          </Typography>
        </Box>
        <Stack direction="row" spacing={2}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Year</InputLabel>
            <Select
              value={selectedYear}
              label="Year"
              onChange={(e) => setSelectedYear(e.target.value)}
            >
              {[2023, 2024, 2025, 2026].map((y) => (
                <MenuItem key={y} value={y}>
                  {y}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tooltip title="Recalculate emissions">
            <IconButton
              onClick={handleRecalculate}
              disabled={recalculating}
              sx={{
                bgcolor: "white",
                border: "1px solid #e5e7eb",
                "&:hover": { bgcolor: "#f9fafb" },
              }}
            >
              <Refresh sx={{ animation: recalculating ? "spin 1s linear infinite" : "none" }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Download report">
            <IconButton
              sx={{
                bgcolor: "white",
                border: "1px solid #e5e7eb",
                "&:hover": { bgcolor: "#f9fafb" },
              }}
            >
              <Download />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Top Stats */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Total Carbon Emissions"
            value={data.total_co2e_tonnes}
            unit="t CO₂e"
            subtitle={`${data.calculation_count.toLocaleString()} data points`}
            icon={<Nature sx={{ fontSize: 28 }} />}
            color="#10b981"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Data Quality Score"
            value={data.data_quality_score}
            unit="%"
            subtitle="Based on completeness"
            icon={<Speed sx={{ fontSize: 28 }} />}
            color="#3b82f6"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Reporting Period"
            value={data.reporting_period?.name || selectedYear}
            unit=""
            subtitle={
              data.reporting_period
                ? `${data.reporting_period.start_date} to ${data.reporting_period.end_date}`
                : "Calendar Year"
            }
            icon={<CalendarMonth sx={{ fontSize: 28 }} />}
            color="#8b5cf6"
          />
        </Grid>
      </Grid>

      {/* Scope Breakdown */}
      <GlassCard sx={{ mb: 4, p: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, color: "#111827", mb: 3 }}>
          GHG Protocol Scope Breakdown
        </Typography>
        <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {data.scope_breakdown?.map((scope) => (
            <ScopeCard
              key={scope.scope}
              scope={scope.scope}
              name={scope.scope_name}
              value={scope.co2e_tonnes}
              percentage={scope.percentage}
              color={scopeColors[scope.scope]}
            />
          ))}
        </Box>
      </GlassCard>

      {/* Charts Row */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Monthly Trend */}
        <Grid item xs={12} lg={8}>
          <GlassCard sx={{ height: "100%" }}>
            <CardContent sx={{ height: "100%", p: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#111827", mb: 3 }}>
                Monthly Emissions Trend
              </Typography>
              <Box sx={{ height: 350 }}>
                {monthlyTrendChart && (
                  <Line data={monthlyTrendChart} options={lineChartOptions} />
                )}
              </Box>
            </CardContent>
          </GlassCard>
        </Grid>

        {/* Scope Distribution */}
        <Grid item xs={12} lg={4}>
          <GlassCard sx={{ height: "100%" }}>
            <CardContent sx={{ height: "100%", p: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#111827", mb: 3 }}>
                Scope Distribution
              </Typography>
              <Box sx={{ height: 350, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {scopePieChart && <Doughnut data={scopePieChart} options={pieChartOptions} />}
              </Box>
            </CardContent>
          </GlassCard>
        </Grid>
      </Grid>

      {/* Category Breakdown */}
      <GlassCard sx={{ mb: 4 }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "#111827", mb: 3 }}>
            Emissions by Category
          </Typography>
          <Box sx={{ height: 400 }}>
            {categoryBarChart && <Bar data={categoryBarChart} options={barChartOptions} />}
          </Box>
        </CardContent>
      </GlassCard>

      {/* Category Details Table */}
      <GlassCard>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "#111827", mb: 3 }}>
            Detailed Category Breakdown
          </Typography>
          <Box sx={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ backgroundColor: "#f9fafb" }}>
                  <th style={{ padding: "12px 16px", textAlign: "left", fontWeight: 600, color: "#374151", borderBottom: "2px solid #e5e7eb" }}>
                    Category
                  </th>
                  <th style={{ padding: "12px 16px", textAlign: "center", fontWeight: 600, color: "#374151", borderBottom: "2px solid #e5e7eb" }}>
                    Scope
                  </th>
                  <th style={{ padding: "12px 16px", textAlign: "right", fontWeight: 600, color: "#374151", borderBottom: "2px solid #e5e7eb" }}>
                    Emissions (t CO₂e)
                  </th>
                  <th style={{ padding: "12px 16px", textAlign: "right", fontWeight: 600, color: "#374151", borderBottom: "2px solid #e5e7eb" }}>
                    Data Points
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.category_breakdown?.map((cat, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "12px 16px", color: "#111827" }}>{cat.category_name}</td>
                    <td style={{ padding: "12px 16px", textAlign: "center" }}>
                      <Chip
                        label={`Scope ${cat.scope}`}
                        size="small"
                        sx={{
                          bgcolor: `${scopeColors[cat.scope]}20`,
                          color: scopeColors[cat.scope],
                          fontWeight: 600,
                        }}
                      />
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right", fontWeight: 600, color: "#111827" }}>
                      {cat.co2e_tonnes.toLocaleString()}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right", color: "#6b7280" }}>
                      {cat.count.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
        </CardContent>
      </GlassCard>

      {/* CSS for spinning animation */}
      <style>
        {`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </Box>
  );
}
