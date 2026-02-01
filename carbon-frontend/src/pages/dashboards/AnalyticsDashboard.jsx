// File: src/pages/dashboards/AnalyticsDashboard.jsx
// Analytics Dashboard - Full date range analysis with comparison features

import React, { useState, useMemo, useEffect } from "react";
import {
  Box,
  Grid,
  Typography,
  Card,
  CardContent,
  Skeleton,
  Alert,
  Chip,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stack,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Divider,
  IconButton,
  Tooltip,
} from "@mui/material";
import { DatePicker, LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import {
  TrendingDown,
  TrendingUp,
  Compare,
  FilterList,
  Download,
  Refresh,
  CalendarMonth,
  BarChart as BarChartIcon,
  ShowChart,
  PieChart as PieChartIcon,
  TableChart,
} from "@mui/icons-material";
import { Line, Bar, Doughnut } from "react-chartjs-2";
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
  Filler,
} from "chart.js";
import { fetchEmissionsDashboard } from "../../api/emissions";
import { useAuth } from "../../auth/AuthContext";
import { useEmissionsData } from "./useEmissionsData";

Chart.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ChartTooltip,
  Legend,
  Filler
);

// ============ Styled Components ============

const GlassCard = ({ children, sx = {}, ...props }) => (
  <Card
    elevation={0}
    sx={{
      background: "rgba(255, 255, 255, 0.98)",
      backdropFilter: "blur(10px)",
      border: "1px solid rgba(0, 0, 0, 0.06)",
      borderRadius: 3,
      transition: "all 0.3s ease",
      "&:hover": {
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.06)",
      },
      ...sx,
    }}
    {...props}
  >
    {children}
  </Card>
);

const QUICK_SELECT_OPTIONS = [
  { label: "Year to Date", value: "ytd" },
  { label: "Last 12 Months", value: "last12" },
  { label: "Last Quarter", value: "lastQuarter" },
  { label: "Last Year", value: "lastYear" },
  { label: "Custom Range", value: "custom" },
];

const SCOPE_COLORS = {
  scope1: { main: "#10b981", light: "#d1fae5", label: "Scope 1 (Direct)" },
  scope2: { main: "#3b82f6", light: "#dbeafe", label: "Scope 2 (Energy)" },
  scope3: { main: "#f59e0b", light: "#fef3c7", label: "Scope 3 (Value Chain)" },
};

// ============ Date Range Picker Component ============

const DateRangeSelector = ({ startDate, endDate, onStartChange, onEndChange, quickSelect, onQuickSelectChange }) => (
  <Paper
    elevation={0}
    sx={{
      p: 2,
      borderRadius: 2,
      bgcolor: "#f9fafb",
      border: "1px solid #e5e7eb",
      display: "flex",
      alignItems: "center",
      gap: 2,
      flexWrap: "wrap",
    }}
  >
    <CalendarMonth sx={{ color: "#6b7280" }} />
    
    <FormControl size="small" sx={{ minWidth: 140 }}>
      <InputLabel>Quick Select</InputLabel>
      <Select
        value={quickSelect}
        label="Quick Select"
        onChange={(e) => onQuickSelectChange(e.target.value)}
        sx={{ bgcolor: "#fff" }}
      >
        {QUICK_SELECT_OPTIONS.map((opt) => (
          <MenuItem key={opt.value} value={opt.value}>
            {opt.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>

    <Divider orientation="vertical" flexItem />
    
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <DatePicker
        label="Start Date"
        value={startDate}
        onChange={onStartChange}
        slotProps={{
          textField: { size: "small", sx: { width: 160, bgcolor: "#fff" } },
        }}
      />
      <Typography color="#6b7280">to</Typography>
      <DatePicker
        label="End Date"
        value={endDate}
        onChange={onEndChange}
        slotProps={{
          textField: { size: "small", sx: { width: 160, bgcolor: "#fff" } },
        }}
      />
    </LocalizationProvider>
    
    <Box sx={{ flex: 1 }} />
    
    <Tooltip title="Compare with previous period">
      <Button
        variant="outlined"
        size="small"
        startIcon={<Compare />}
        sx={{
          borderColor: "#e5e7eb",
          color: "#374151",
          "&:hover": { bgcolor: "#f3f4f6", borderColor: "#d1d5db" },
        }}
      >
        Compare
      </Button>
    </Tooltip>
    
    <Tooltip title="Export data">
      <IconButton size="small" sx={{ color: "#6b7280" }}>
        <Download />
      </IconButton>
    </Tooltip>
  </Paper>
);

// ============ Metric Cards ============

const MetricCard = ({ title, value, unit, change, changeLabel, icon: Icon, color = "#3b82f6" }) => {
  const isPositive = change < 0; // For emissions, reduction is positive
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2,
              bgcolor: `${color}15`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon sx={{ color, fontSize: 22 }} />
          </Box>
          <Typography variant="subtitle2" color="#6b7280" fontWeight={500}>
            {title}
          </Typography>
        </Box>
        
        <Typography variant="h4" fontWeight={700} color="#111827" sx={{ mb: 1 }}>
          {value.toLocaleString()}
          <Typography component="span" variant="body2" color="#6b7280" sx={{ ml: 1 }}>
            {unit}
          </Typography>
        </Typography>
        
        {change !== undefined && (
          <Chip
            size="small"
            icon={isPositive ? <TrendingDown fontSize="small" /> : <TrendingUp fontSize="small" />}
            label={`${isPositive ? "" : "+"}${change.toFixed(1)}% ${changeLabel || "vs last period"}`}
            sx={{
              bgcolor: isPositive ? "#d1fae5" : "#fee2e2",
              color: isPositive ? "#059669" : "#dc2626",
              fontWeight: 600,
              "& .MuiChip-icon": { color: "inherit" },
            }}
          />
        )}
      </CardContent>
    </GlassCard>
  );
};

// ============ Chart Components ============

const MonthlyTrendChart = ({ monthlyTrend, showComparison }) => {
  // Use real monthly data from API
  const months = monthlyTrend?.map(m => m.month_name) || ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthlyTotals = monthlyTrend?.map(m => m.total) || [];
  
  const chartData = {
    labels: months,
    datasets: [
      {
        label: "Total Emissions (tonnes)",
        data: monthlyTotals,
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: "#3b82f6",
      },
      // Scope breakdown lines
      {
        label: "Scope 1",
        data: monthlyTrend?.map(m => m.scope1) || [],
        borderColor: "#10b981",
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
      },
      {
        label: "Scope 2",
        data: monthlyTrend?.map(m => m.scope2) || [],
        borderColor: "#3b82f6",
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
        borderDash: [5, 5],
      },
      {
        label: "Scope 3",
        data: monthlyTrend?.map(m => m.scope3) || [],
        borderColor: "#f59e0b",
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
        borderDash: [2, 2],
      },
    ],
  };
  
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top",
        align: "end",
        labels: { usePointStyle: true, padding: 20 },
      },
      tooltip: {
        mode: "index",
        intersect: false,
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()} t CO₂e`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: "#f3f4f6" },
        ticks: { callback: (v) => v.toLocaleString() },
      },
      x: {
        grid: { display: false },
      },
    },
    interaction: {
      mode: "nearest",
      axis: "x",
      intersect: false,
    },
  };
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
          Monthly Emissions Trend
        </Typography>
        <Box sx={{ height: 300 }}>
          <Line data={chartData} options={options} />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const ScopeDistributionChart = ({ scope1, scope2, scope3 }) => {
  const total = scope1 + scope2 + scope3;
  
  const data = {
    labels: ["Scope 1", "Scope 2", "Scope 3"],
    datasets: [{
      data: [scope1, scope2, scope3],
      backgroundColor: [SCOPE_COLORS.scope1.main, SCOPE_COLORS.scope2.main, SCOPE_COLORS.scope3.main],
      borderColor: "#fff",
      borderWidth: 3,
    }],
  };
  
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "60%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.label}: ${ctx.parsed.toLocaleString()} t (${((ctx.parsed / total) * 100).toFixed(1)}%)`,
        },
      },
    },
  };
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
          Scope Distribution
        </Typography>
        
        <Grid container spacing={2}>
          <Grid size={5}>
            <Box sx={{ height: 180 }}>
              <Doughnut data={data} options={options} />
            </Box>
          </Grid>
          <Grid size={7}>
            <Stack spacing={2} sx={{ height: "100%", justifyContent: "center" }}>
              {Object.entries(SCOPE_COLORS).map(([key, config]) => {
                const value = key === "scope1" ? scope1 : key === "scope2" ? scope2 : scope3;
                const pct = ((value / total) * 100).toFixed(1);
                return (
                  <Box key={key}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: config.main }} />
                        <Typography variant="body2" fontWeight={500} color="#374151">
                          {config.label}
                        </Typography>
                      </Box>
                      <Typography variant="body2" fontWeight={600} color="#111827">
                        {pct}%
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="#6b7280">
                      {value.toLocaleString()} t CO₂e
                    </Typography>
                  </Box>
                );
              })}
            </Stack>
          </Grid>
        </Grid>
      </CardContent>
    </GlassCard>
  );
};

const CategoryBreakdownChart = ({ categories }) => {
  const data = {
    labels: categories.map((c) => c.name),
    datasets: [{
      label: "Emissions",
      data: categories.map((c) => c.value),
      backgroundColor: [
        "#3b82f6",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#06b6d4",
        "#ec4899",
      ],
      borderRadius: 6,
      barThickness: 24,
    }],
  };
  
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.parsed.x.toLocaleString()} t CO₂e`,
        },
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: { color: "#f3f4f6" },
        ticks: { callback: (v) => v.toLocaleString() },
      },
      y: {
        grid: { display: false },
      },
    },
  };
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
          Emissions by Category
        </Typography>
        <Box sx={{ height: 280 }}>
          <Bar data={data} options={options} />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const DetailedTable = ({ data }) => (
  <GlassCard>
    <CardContent sx={{ p: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
        Detailed Breakdown
      </Typography>
      <Paper
        elevation={0}
        sx={{
          border: "1px solid #e5e7eb",
          borderRadius: 2,
          overflow: "hidden",
        }}
      >
        <Box
          component="table"
          sx={{
            width: "100%",
            borderCollapse: "collapse",
            "& th, & td": {
              p: 1.5,
              textAlign: "left",
              borderBottom: "1px solid #e5e7eb",
            },
            "& th": {
              bgcolor: "#f9fafb",
              fontWeight: 600,
              color: "#374151",
              fontSize: 13,
            },
            "& td": {
              color: "#111827",
              fontSize: 14,
            },
            "& tr:last-child td": {
              borderBottom: "none",
            },
          }}
        >
          <thead>
            <tr>
              <th>Category</th>
              <th>Scope</th>
              <th>Emissions (t CO₂e)</th>
              <th>% of Total</th>
              <th>vs Last Period</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr key={idx}>
                <td>{row.category}</td>
                <td>
                  <Chip
                    size="small"
                    label={`Scope ${row.scope}`}
                    sx={{
                      bgcolor: row.scope === 1 ? "#d1fae5" : row.scope === 2 ? "#dbeafe" : "#fef3c7",
                      color: row.scope === 1 ? "#059669" : row.scope === 2 ? "#2563eb" : "#d97706",
                      fontWeight: 600,
                    }}
                  />
                </td>
                <td>{row.value.toLocaleString()}</td>
                <td>{row.percentage}%</td>
                <td>
                  <Chip
                    size="small"
                    icon={row.change < 0 ? <TrendingDown fontSize="small" /> : <TrendingUp fontSize="small" />}
                    label={`${row.change < 0 ? "" : "+"}${row.change}%`}
                    sx={{
                      bgcolor: row.change < 0 ? "#d1fae5" : "#fee2e2",
                      color: row.change < 0 ? "#059669" : "#dc2626",
                      fontWeight: 600,
                      "& .MuiChip-icon": { color: "inherit" },
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </Box>
      </Paper>
    </CardContent>
  </GlassCard>
);

// ============ Main Component ============

export default function AnalyticsDashboard() {
  const { user, context } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  
  // Date range state
  const [quickSelect, setQuickSelect] = useState("ytd");
  const [startDate, setStartDate] = useState(dayjs().startOf("year"));
  const [endDate, setEndDate] = useState(dayjs());
  const [showComparison, setShowComparison] = useState(false);
  const [viewMode, setViewMode] = useState("charts");

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const year = endDate.year();
        const result = await fetchEmissionsDashboard(
          { project_id: context?.projectId, year },
          user?.token
        );
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [endDate, user?.token, context?.projectId]);

  const handleQuickSelectChange = (value) => {
    setQuickSelect(value);
    const now = dayjs();
    
    switch (value) {
      case "ytd":
        setStartDate(now.startOf("year"));
        setEndDate(now);
        break;
      case "last12":
        setStartDate(now.subtract(12, "month"));
        setEndDate(now);
        break;
      case "lastQuarter":
        setStartDate(now.subtract(3, "month"));
        setEndDate(now);
        break;
      case "lastYear":
        setStartDate(now.subtract(1, "year").startOf("year"));
        setEndDate(now.subtract(1, "year").endOf("year"));
        break;
      default:
        break;
    }
  };

  if (loading) {
    return (
      <Box sx={{ p: 4 }}>
        <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 2, mb: 3 }} />
        <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 2, mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid size={{ xs: 12, md: 6, lg: 3 }} key={i}>
              <Skeleton variant="rectangular" height={160} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">Failed to load analytics data: {error}</Alert>
      </Box>
    );
  }

  // Transform real API data for dashboard components
  // API returns: total_co2e_tonnes, scope_breakdown, category_breakdown, monthly_trend
  const scopeMap = {};
  (data?.scope_breakdown || []).forEach(s => {
    scopeMap[`scope${s.scope}`] = s.co2e_tonnes || 0;
  });
  
  const emissions = {
    total: data?.total_co2e_tonnes || 0,
    scope1: scopeMap.scope1 || 0,
    scope2: scopeMap.scope2 || 0,
    scope3: scopeMap.scope3 || 0,
  };
  
  // Transform category_breakdown from API
  const categories = (data?.category_breakdown || []).map(cat => ({
    name: cat.category_name || cat.category,
    value: cat.co2e_tonnes || 0,
    scope: cat.scope,
    count: cat.count || 0,
  })).sort((a, b) => b.value - a.value);

  // Build table data from real categories
  const tableData = categories.map(cat => {
    const pct = emissions.total > 0 ? Math.round((cat.value / emissions.total) * 1000) / 10 : 0;
    return {
      category: cat.name,
      scope: cat.scope,
      value: cat.value,
      percentage: pct,
      change: 0, // Would need historical comparison
    };
  });

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={700} color="#111827" gutterBottom>
          Analytics
        </Typography>
        <Typography variant="body2" color="#6b7280">
          Deep dive into your emissions data with full date range analysis
        </Typography>
      </Box>

      {/* Date Range Selector */}
      <Box sx={{ mb: 3 }}>
        <DateRangeSelector
          startDate={startDate}
          endDate={endDate}
          onStartChange={setStartDate}
          onEndChange={setEndDate}
          quickSelect={quickSelect}
          onQuickSelectChange={handleQuickSelectChange}
        />
      </Box>

      {/* View Toggle */}
      <Box sx={{ mb: 3, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Chip
          label={`Showing: ${startDate.format("MMM D, YYYY")} - ${endDate.format("MMM D, YYYY")}`}
          sx={{ bgcolor: "#f3f4f6", color: "#374151", fontWeight: 500 }}
        />
        
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={(e, v) => v && setViewMode(v)}
          size="small"
        >
          <ToggleButton value="charts">
            <BarChartIcon fontSize="small" sx={{ mr: 0.5 }} /> Charts
          </ToggleButton>
          <ToggleButton value="table">
            <TableChart fontSize="small" sx={{ mr: 0.5 }} /> Table
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Key Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title="Total Emissions"
            value={emissions.total}
            unit="t CO₂e"
            icon={TrendingDown}
            color="#16a34a"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title="Scope 1 - Direct"
            value={emissions.scope1}
            unit="t CO₂e"
            icon={ShowChart}
            color="#10b981"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title="Scope 2 - Energy"
            value={emissions.scope2}
            unit="t CO₂e"
            icon={ShowChart}
            color="#3b82f6"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title="Scope 3 - Value Chain"
            value={emissions.scope3}
            unit="t CO₂e"
            icon={ShowChart}
            color="#f59e0b"
          />
        </Grid>
      </Grid>

      {/* Charts or Table View */}
      {viewMode === "charts" ? (
        <>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, lg: 8 }}>
              <MonthlyTrendChart monthlyTrend={data?.monthly_trend} showComparison={showComparison} />
            </Grid>
            <Grid size={{ xs: 12, lg: 4 }}>
              <ScopeDistributionChart
                scope1={emissions.scope1}
                scope2={emissions.scope2}
                scope3={emissions.scope3}
              />
            </Grid>
          </Grid>
          
          <Grid container spacing={3}>
            <Grid size={12}>
              <CategoryBreakdownChart categories={categories} />
            </Grid>
          </Grid>
        </>
      ) : (
        <DetailedTable data={tableData} />
      )}

      {/* Footer */}
      <Box sx={{ mt: 4, pt: 3, borderTop: "1px solid #e5e7eb" }}>
        <Typography variant="body2" color="#9ca3af" textAlign="center">
          Data refreshed: {dayjs().format("MMM D, YYYY h:mm A")} • 
          <Button size="small" startIcon={<Refresh fontSize="small" />} sx={{ ml: 1 }}>
            Refresh
          </Button>
        </Typography>
      </Box>
    </Box>
  );
}
