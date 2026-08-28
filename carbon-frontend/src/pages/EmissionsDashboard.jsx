// File: src/pages/EmissionsDashboard.jsx
// Professional Carbon Emissions Dashboard with beautiful visualizations

import React, { useState, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
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
import { useEnabledApps } from "../hooks/useEnabledApps";
import { useNotes } from "../notes/NotesContext";
import PageContainer from "../components/layout/PageContainer";
import { FONT, SPACING } from "../theme/themeTokens";
import { chartPalette } from "../theme/carbonTheme";

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
    variant="outlined"
    sx={{
      borderRadius: 1.5,
      transition: "box-shadow 0.15s ease",
      "&:hover": { boxShadow: 2 },
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
            icon={trend === "up" ? <TrendingUp sx={{ fontSize: '0.75rem' }} /> : <TrendingDown sx={{ fontSize: '0.75rem' }} />}
            label={trendValue}
            sx={{ ...FONT.chip, bgcolor: trend === "up" ? "error.light" : "success.light", color: trend === "up" ? "error.dark" : "success.dark" }}
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

const ScopeCard = ({ name, value, percentage, color }) => {
  const { t } = useTranslation("emissions");
  return (
    <Box sx={{ flex: 1, minWidth: 180 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
        <Box sx={{ width: 1.25, height: 1.25, borderRadius: "50%", bgcolor: color }} />
        <Typography sx={{ ...FONT.cardTitle, color: "text.primary" }}>
          {name}
        </Typography>
      </Box>
      <Typography sx={{ ...FONT.statValue, color: "text.primary", mb: 0.25 }}>
        {value.toLocaleString()}
        <Typography component="span" sx={{ ml: 0.5, ...FONT.bodySmall, color: "text.secondary" }}>
          {t("tCo2eUnit")}
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
};

// ============ Main Component ============

export default function EmissionsDashboard({ projectId }) {
  const { t } = useTranslation("emissions");
  useDocumentTitle(t("emissionsDashboardTitle"));
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [selectedYear, setSelectedYear] = useState(2026); // Demo data year
  const [recalculating, setRecalculating] = useState(false);
  
  const token = localStorage.getItem("access");

  // ── Notes entity context ──────────────────────────────────────────────────
  // Notes are entity-anchored: the Notes drawer only shows the composer when a
  // page registers one or more entities via setContexts. This dashboard anchors
  // notes to the reporting period it displays when one is present, else to the
  // selected reporting year (the API returns reporting_period only when called
  // with reporting_period_id; this page queries by year, so the period is usually
  // null → fall back to "Year N", which matches the header the user sees).
  // The Carbon Footprint domain app is attached as a SECOND anchor, so notes
  // about the whole app surface here too — while each app's thread stays
  // isolated (Option B: NoteAnchor, one note, many contexts).
  const { setContexts } = useNotes();
  const { apps: enabledApps } = useEnabledApps();
  const carbonApp = useMemo(
    () => enabledApps?.find((a) => a.app_id === "carbon") || null,
    [enabledApps]
  );
  const notesEntity = useMemo(() => {
    if (!data) return null;
    const rp = data.reporting_period;
    const primary = rp?.id
      ? {
          entityType: "reporting_period",
          entityId: rp.id,
          label: rp.name || t("yearN", { year: selectedYear }),
        }
      : {
          entityType: "reporting_year",
          entityId: selectedYear,
          label: t("yearN", { year: selectedYear }),
        };
    const appAnchor = {
      entityType: "app",
      entityId: carbonApp?.id ?? 1,
      label: carbonApp?.name || "Carbon Footprint",
    };
    return [primary, appAnchor];
  }, [data, selectedYear, carbonApp, t]);

  useEffect(() => {
    setContexts(notesEntity);
  }, [notesEntity, setContexts]);
  useEffect(() => () => setContexts(null), [setContexts]);

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
        setError(err.message || t("failedToLoadEmissions"));
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [projectId, selectedYear, token, t]);

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

  // Scope colors — theme palette (same model as EmissionsReport)
  const scopeColors = useMemo(() => ({
    1: theme.palette.success.main,   // Green - Scope 1
    2: theme.palette.primary.light,  // Blue - Scope 2
    3: theme.palette.warning.main,   // Orange - Scope 3
  }), [theme]);

  // Chart configurations
  const monthlyTrendChart = useMemo(() => {
    if (!data?.monthly_trend) return null;

    return {
      labels: data.monthly_trend.map((m) => m.month_name),
      datasets: [
        {
          label: t("scope1"),
          data: data.monthly_trend.map((m) => m.scope1),
          borderColor: scopeColors[1],
          backgroundColor: `${scopeColors[1]}20`,
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: t("scope2"),
          data: data.monthly_trend.map((m) => m.scope2),
          borderColor: scopeColors[2],
          backgroundColor: `${scopeColors[2]}20`,
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: t("scope3"),
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
  }, [data, scopeColors, t]);

  const scopePieChart = useMemo(() => {
    if (!data?.scope_breakdown) return null;

    return {
      labels: data.scope_breakdown.map((s) => s.scope_name),
      datasets: [
        {
          data: data.scope_breakdown.map((s) => s.co2e_tonnes),
          backgroundColor: data.scope_breakdown.map((s) => scopeColors[s.scope]),
          borderColor: theme.palette.background.paper,
          borderWidth: 3,
          hoverOffset: 8,
        },
      ],
    };
  }, [data, scopeColors, theme]);

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
          label: t("chartEmissionsLabel"),
          data: sortedCategories.map(([, value]) => value),
          backgroundColor: [
            theme.palette.success.main,
            theme.palette.primary.light,
            theme.palette.warning.main,
            theme.palette.secondary.light,
            theme.palette.error.main,
            theme.palette.info.main,
            theme.palette.warning.light,
            theme.palette.success.light,
          ],
          borderRadius: 8,
          maxBarThickness: 50,
        },
      ],
    };
  }, [data, theme, t]);

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
        backgroundColor: theme.palette.grey[900],
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (context) => `${context.dataset.label}: ${context.parsed.y.toLocaleString()} ${t("tCo2eUnit")}`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: theme.palette.divider },
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
        backgroundColor: theme.palette.grey[900],
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (context) => `${context.parsed.x.toLocaleString()} ${t("tCo2eUnit")}`,
        },
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: { color: theme.palette.divider },
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
        backgroundColor: theme.palette.grey[900],
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (context) => {
            const total = context.dataset.data.reduce((a, b) => a + b, 0);
            const percentage = ((context.parsed / total) * 100).toFixed(1);
            return `${context.label}: ${context.parsed.toLocaleString()} ${t("tCo2eUnit")} (${percentage}%)`;
          },
        },
      },
    },
  };

  // Loading state
  if (loading) {
    return (
      <PageContainer sx={{ alignItems: "center", justifyContent: "center" }}>
        <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 400 }}>
          <CircularProgress size={48} sx={{ color: "success.main" }} />
        </Box>
      </PageContainer>
    );
  }

  // Error state
  if (error) {
    return (
      <PageContainer>
        <Alert severity="error" sx={{ m: 2 }}>
          {error}
        </Alert>
      </PageContainer>
    );
  }

  // No data state
  if (!data || data.calculation_count === 0) {
    return (
      <PageContainer>
        <Paper variant="outlined" sx={{ p: 2.5, textAlign: "center", borderRadius: 1.5 }}>
          <CloudQueue sx={{ fontSize: '3rem', color: "text.disabled", mb: SPACING.md }} />
          <Typography sx={{ ...FONT.cardTitle, color: "text.secondary", mb: 0.5 }}>
            {t("noEmissionsData")}
          </Typography>
          <Typography sx={{ ...FONT.bodySmall, color: "text.disabled", mb: SPACING.lg }}>
            {t("noEmissionsSubtext")}
          </Typography>
          <Button
            variant="contained"
            startIcon={<Refresh />}
            onClick={handleRecalculate}
            sx={{ borderRadius: 1.5, px: SPACING.lg }}
          >
            {t("calculateEmissions")}
          </Button>
        </Paper>
      </PageContainer>
    );
  }

  return (
    <PageContainer sx={{ height: '100%', overflow: 'auto' }}>
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: SPACING.lg }}>
        <Box>
          <Typography variant="h2" sx={{ mb: 0.25 }}>
            {t("emissionsDashboard")}
          </Typography>
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>
            {data.reporting_period?.name || t("yearN", { year: selectedYear })} {t("lastUpdated")}{" "}
            {data.last_updated
              ? new Date(data.last_updated).toLocaleDateString()
              : "N/A"}
          </Typography>
        </Box>
        <Stack direction="row" spacing={2}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>{t("yearLabel")}</InputLabel>
            <Select
              value={selectedYear}
              label={t("yearLabel")}
              onChange={(e) => setSelectedYear(e.target.value)}
            >
              {[2023, 2024, 2025, 2026].map((y) => (
                <MenuItem key={y} value={y}>
                  {y}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tooltip title={t("recalculateEmissions")}>
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
          <Tooltip title={t("downloadReport")}>
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
            title={t("totalCarbonEmissions")}
            value={data.total_co2e_tonnes}
            unit={t("tCo2eUnit")}
            subtitle={t("dataPoints", { count: data.calculation_count })}
            icon={<Nature sx={{ fontSize: '1.75rem' }} />}
            color={scopeColors[1]}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard
            title={t("dataQualityScore")}
            value={data.data_quality_score}
            unit="%"
            subtitle={t("basedOnCompleteness")}
            icon={<Speed sx={{ fontSize: '1.75rem' }} />}
            color={scopeColors[2]}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard
            title={t("reportingPeriodLabel")}
            value={data.reporting_period?.name || selectedYear}
            unit=""
            subtitle={
              data.reporting_period
                ? t("periodRange", {
                    start: data.reporting_period.start_date,
                    end: data.reporting_period.end_date,
                  })
                : t("calendarYear")
            }
            icon={<CalendarMonth sx={{ fontSize: '1.75rem' }} />}
            color={chartPalette.purple}
          />
        </Grid>
      </Grid>

      {/* Scope Breakdown */}
      <GlassCard sx={{ mb: 4, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          {t("scopeBreakdownTitle")}
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
              <Typography variant="h6" sx={{ mb: 3 }}>
                {t("monthlyTrendTitle")}
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
              <Typography variant="h6" sx={{ mb: 3 }}>
                {t("scopeDistributionTitle")}
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
          <Typography variant="h6" sx={{ mb: 3 }}>
            {t("byCategoryTitle")}
          </Typography>
          <Box sx={{ height: 400 }}>
            {categoryBarChart && <Bar data={categoryBarChart} options={barChartOptions} />}
          </Box>
        </CardContent>
      </GlassCard>

      {/* Category Details Table */}
      <GlassCard>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ mb: 3 }}>
            {t("detailedCategoryBreakdown")}
          </Typography>
          <Box sx={{ overflowX: "auto" }}>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1.5 }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: "background.default" }}>
                    <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600, color: "text.secondary" }}>
                      {t("categoryCol")}
                    </TableCell>
                    <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600, color: "text.secondary" }}>
                      {t("scopeCol")}
                    </TableCell>
                    <TableCell align="right" sx={{ ...FONT.bodySmall, fontWeight: 600, color: "text.secondary" }}>
                      {t("emissionsCol")}
                    </TableCell>
                    <TableCell align="right" sx={{ ...FONT.bodySmall, fontWeight: 600, color: "text.secondary" }}>
                      {t("dataPointsCol")}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.category_breakdown?.map((cat, idx) => (
                    <TableRow key={idx} sx={{ "&:last-child th, &:last-child td": { border: 0 } }}>
                      <TableCell sx={{ ...FONT.body }}>{cat.category_name}</TableCell>
                      <TableCell align="center">
                        <Chip
                          label={t("scopeChip", { scope: cat.scope })}
                          size="small"
                          sx={{
                            bgcolor: `${scopeColors[cat.scope]}20`,
                            color: scopeColors[cat.scope],
                            fontWeight: 600,
                          }}
                        />
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                        {cat.co2e_tonnes.toLocaleString()}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body, color: "text.secondary" }}>
                        {cat.count.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
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
    </PageContainer>
  );
}
