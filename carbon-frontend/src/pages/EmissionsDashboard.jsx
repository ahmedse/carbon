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
import useDocumentTitle from "../hooks/useDocumentTitle";

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

// ── Compact Design System (aligned with carbonDesign.js) ────────────────────
const SPACING = { sm: 1.5, md: 2, lg: 3 };
const FONT = {
  statValue: { fontSize: '1.5rem', fontWeight: 700, lineHeight: 1.2 },
  statLabel: { fontSize: '0.6875rem', fontWeight: 500, letterSpacing: '0.02em', textTransform: 'uppercase' },
  cardTitle: { fontSize: '0.875rem', fontWeight: 600 },
  bodySmall: { fontSize: '0.75rem', lineHeight: 1.5 },
  chip: { fontSize: '0.6875rem', fontWeight: 500 },
};

const GlassCard = ({ children, sx = {}, ...props }) => (
  <Card
    variant="outlined"
    sx={{
      borderRadius: 1.5,
      transition: "box-shadow 0.15s ease",
      "&:hover": { boxShadow: "0 2px 12px rgba(0, 0, 0, 0.06)" },
      ...sx,
    }}
    {...props}
  >
    {children}
  </Card>
);

const StatCard = ({ title, value, unit, subtitle, icon, color, trend, trendValue }) => (
  <GlassCard>
    <CardContent sx={{ p: SPACING.md, '&:last-child': { pb: SPACING.md } }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", mb: 1.5 }}>
        <Box
          sx={{
            width: 36, height: 36, borderRadius: 1,
            display: "flex", alignItems: "center", justifyContent: "center",
            bgcolor: `${color}18`, color,
          }}
        >
          {icon}
        </Box>
        {trend && (
          <Chip
            size="small"
            icon={trend === "up" ? <TrendingUp sx={{ fontSize: 12 }} /> : <TrendingDown sx={{ fontSize: 12 }} />}
            label={trendValue}
            sx={{ ...FONT.chip, height: 20, bgcolor: trend === "up" ? "error.light" : "success.light", color: trend === "up" ? "error.dark" : "success.dark" }}
          />
        )}
      </Box>
      <Typography sx={{ ...FONT.statValue, color: "text.primary", mb: 0.25 }}>
        {typeof value === "number" ? value.toLocaleString() : value}
        <Typography component="span" sx={{ ml: 0.75, ...FONT.bodySmall, color: "text.secondary" }}>
          {unit}
        </Typography>
      </Typography>
      <Typography sx={{ ...FONT.statLabel, color: "text.secondary" }}>
        {title}
      </Typography>
      {subtitle && (
        <Typography sx={{ ...FONT.chip, color: "text.disabled", mt: 0.25 }}>
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </GlassCard>
);

const ScopeCard = ({ name, value, percentage, color }) => (
  <Box sx={{ flex: 1, minWidth: 180 }}>
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
      <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: color }} />
      <Typography sx={{ ...FONT.cardTitle, color: "text.primary" }}>
        {name}
      </Typography>
    </Box>
    <Typography sx={{ ...FONT.statValue, color: "text.primary", mb: 0.25 }}>
      {value.toLocaleString()}
      <Typography component="span" sx={{ ml: 0.5, ...FONT.bodySmall, color: "text.secondary" }}>
        t CO₂e
      </Typography>
    </Typography>
    <Box sx={{ mt: 0.75, display: "flex", alignItems: "center", gap: 1 }}>
      <LinearProgress
        variant="determinate"
        value={percentage}
        sx={{
          flex: 1, height: 4, borderRadius: 2,
          bgcolor: `${color}20`,
          "& .MuiLinearProgress-bar": { bgcolor: color, borderRadius: 2 },
        }}
      />
      <Typography sx={{ ...FONT.chip, color: "text.secondary", minWidth: 36 }}>
        {percentage.toFixed(1)}%
      </Typography>
    </Box>
  </Box>
);

// ============ Main Component ============

export default function EmissionsDashboard({ projectId }) {
  useDocumentTitle("Emissions");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [selectedYear, setSelectedYear] = useState(2026); // Demo data year
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

  // Handle recalculation — triggers all active calculation rules
  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      await triggerCalculations({ recalculate: true }, token);
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
  const scopeColors = useMemo(() => ({
    1: "#10b981", // Green - Scope 1
    2: "#3b82f6", // Blue - Scope 2
    3: "#f59e0b", // Orange - Scope 3
  }), []);

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
  }, [data, scopeColors]);

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
  }, [data, scopeColors]);

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
        <CircularProgress size={48} sx={{ color: "success.main" }} />
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
      <Box sx={{ px: SPACING.lg, py: SPACING.md, height: '100%', overflow: 'auto' }}>
        <Paper variant="outlined" sx={{ p: SPACING.lg * 2, textAlign: "center", borderRadius: 1.5 }}>
          <CloudQueue sx={{ fontSize: 48, color: "text.disabled", mb: SPACING.md }} />
          <Typography sx={{ ...FONT.cardTitle, color: "text.secondary", mb: 0.5 }}>
            No Emissions Data Yet
          </Typography>
          <Typography sx={{ ...FONT.bodySmall, color: "text.disabled", mb: SPACING.lg }}>
            Run calculations to see your carbon emissions dashboard
          </Typography>
          <Button
            variant="contained"
            startIcon={<Refresh />}
            onClick={handleRecalculate}
            sx={{ borderRadius: 1.5, px: SPACING.lg }}
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
        px: SPACING.lg,
        py: SPACING.md,
        height: '100%',
        overflow: 'auto',
      }}
    >
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: SPACING.lg }}>
        <Box>
          <Typography sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary', mb: 0.25 }}>
            Emissions Dashboard
          </Typography>
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>
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
                bgcolor: "background.default",
                border: "1px solid",
                borderColor: "divider",
                "&:hover": { bgcolor: "background.paper" },
              }}
            >
              <Refresh sx={{ animation: recalculating ? "spin 1s linear infinite" : "none" }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Download report">
            <IconButton
              sx={{
                bgcolor: "background.default",
                border: "1px solid",
                borderColor: "divider",
                "&:hover": { bgcolor: "background.paper" },
              }}
            >
              <Download />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Top Stats */}
      <Grid container spacing={SPACING.sm} sx={{ mb: SPACING.lg }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard
            title="Total Carbon Emissions"
            value={data.total_co2e_tonnes}
            unit="t CO₂e"
            subtitle={`${data.calculation_count.toLocaleString()} data points`}
            icon={<Nature sx={{ fontSize: 28 }} />}
            color="#10b981"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard
            title="Data Quality Score"
            value={data.data_quality_score}
            unit="%"
            subtitle="Based on completeness"
            icon={<Speed sx={{ fontSize: 28 }} />}
            color="#3b82f6"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
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
        <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", mb: 3 }}>
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
      <Grid container spacing={SPACING.sm} sx={{ mb: SPACING.lg }}>
        {/* Monthly Trend */}
        <Grid size={{ xs: 12, lg: 8 }}>
          <GlassCard sx={{ height: "100%" }}>
            <CardContent sx={{ height: "100%", p: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", mb: 3 }}>
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
        <Grid size={{ xs: 12, lg: 4 }}>
          <GlassCard sx={{ height: "100%" }}>
            <CardContent sx={{ height: "100%", p: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", mb: 3 }}>
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
          <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", mb: 3 }}>
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
          <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", mb: 3 }}>
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
