// File: src/pages/dashboards/AnalyticsDashboard.jsx
// Analytics Dashboard - Full date range analysis with comparison features

import React, { useState, useEffect } from "react";
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { DatePicker, LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import { useTranslation, Trans } from "react-i18next";
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
import useDocumentTitle from '../../hooks/useDocumentTitle';
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
import PageContainer from "../../components/layout/PageContainer";
import { FONT } from "../../theme/themeTokens";

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
      bgcolor: "background.paper",
      border: "1px solid",
      borderColor: "divider",
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

const QUICK_SELECT_OPTIONS = [
  { labelKey: "qsYtd", value: "ytd" },
  { labelKey: "qsLast12", value: "last12" },
  { labelKey: "qsLastQuarter", value: "lastQuarter" },
  { labelKey: "qsLastYear", value: "lastYear" },
  { labelKey: "qsCustom", value: "custom" },
];

// ============ Date Range Picker Component ============

const DateRangeSelector = ({ startDate, endDate, onStartChange, onEndChange, quickSelect, onQuickSelectChange }) => {
  const { t } = useTranslation('common');
  return (
  <Paper
    elevation={0}
    sx={{
      p: 2,
      borderRadius: 1.5,
      bgcolor: "background.dark",
      border: "1px solid",
      borderColor: "divider",
      display: "flex",
      alignItems: "center",
      gap: 2,
      flexWrap: "wrap",
    }}
  >
    <CalendarMonth sx={{ color: 'text.secondary' }} />
    
    <FormControl size="small" sx={{ minWidth: 140 }}>
      <InputLabel>{t('quickSelect')}</InputLabel>
      <Select
        value={quickSelect}
        label={t('quickSelect')}
        onChange={(e) => onQuickSelectChange(e.target.value)}
        sx={{ bgcolor: 'background.default' }}
      >
        {QUICK_SELECT_OPTIONS.map((opt) => (
          <MenuItem key={opt.value} value={opt.value}>
            {t(opt.labelKey)}
          </MenuItem>
        ))}
      </Select>
    </FormControl>

    <Divider orientation="vertical" flexItem />
    
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <DatePicker
        label={t('startDate')}
        value={startDate}
        onChange={onStartChange}
        slotProps={{
          textField: { size: "small", sx: { width: 160, bgcolor: "background.default" } },
        }}
      />
      <Typography color="text.secondary">{t('to')}</Typography>
      <DatePicker
        label={t('endDate')}
        value={endDate}
        onChange={onEndChange}
        slotProps={{
          textField: { size: "small", sx: { width: 160, bgcolor: "background.default" } },
        }}
      />
    </LocalizationProvider>
    
    <Box sx={{ flex: 1 }} />
    
    <Tooltip title={t('compareWithPrevious')}>
      <Button
        variant="outlined"
        size="small"
        startIcon={<Compare />}
        sx={{
          borderColor: "divider",
          color: "text.primary",
          "&:hover": { bgcolor: "action.hover", borderColor: "divider" },
        }}
      >
        {t('compare')}
      </Button>
    </Tooltip>
    
    <Tooltip title={t('exportData')}>
      <IconButton size="small" sx={{ color: 'text.secondary' }}>
        <Download />
      </IconButton>
    </Tooltip>
  </Paper>
  );
};

// ============ Metric Cards ============

const MetricCard = ({ title, value, unit, change, changeLabel, icon: _Icon, color = null }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const accent = color || theme.palette.primary.light;
  const isPositive = change < 0; // For emissions, reduction is positive
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <Box
            sx={{
              width: 5,
              height: 5,
              borderRadius: 1,
              bgcolor: `${accent}15`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <_Icon sx={{ color: accent, fontSize: '1.375rem' }} />
          </Box>
          <Typography variant="subtitle2" color="text.secondary" fontWeight={500}>
            {title}
          </Typography>
        </Box>
        
        <Typography variant="h4" sx={{ mb: 1 }}>
          {value.toLocaleString()}
          <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
            {unit}
          </Typography>
        </Typography>
        
        {change !== undefined && (
          <Chip
            size="small"
            icon={isPositive ? <TrendingDown fontSize="small" /> : <TrendingUp fontSize="small" />}
            label={`${isPositive ? "" : "+"}${change.toFixed(1)}% ${changeLabel || t("vsLastPeriod")}`}
            sx={{
              bgcolor: isPositive ? "success.light" : "error.light",
              color: isPositive ? "success.dark" : "error.dark",
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

const MonthlyTrendChart = ({ monthlyTrend, showComparison: _showComparison }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const scopeColors = {
    1: theme.palette.success.main,
    2: theme.palette.primary.light,
    3: theme.palette.warning.main,
  };
  // Use real monthly data from API
  const months = monthlyTrend?.map(m => m.month_name) || ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthlyTotals = monthlyTrend?.map(m => m.total) || [];
  
  const chartData = {
    labels: months,
    datasets: [
      {
        label: t("chartTotalEmissions"),
        data: monthlyTotals,
        borderColor: theme.palette.primary.light,
        backgroundColor: `${theme.palette.primary.light}1A`,
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: theme.palette.primary.light,
      },
      // Scope breakdown lines
      {
        label: "Scope 1",
        data: monthlyTrend?.map(m => m.scope1) || [],
        borderColor: scopeColors[1],
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
      },
      {
        label: "Scope 2",
        data: monthlyTrend?.map(m => m.scope2) || [],
        borderColor: scopeColors[2],
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
        borderDash: [5, 5],
      },
      {
        label: "Scope 3",
        data: monthlyTrend?.map(m => m.scope3) || [],
        borderColor: scopeColors[3],
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
        grid: { color: theme.palette.divider },
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
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {t('monthlyEmissionsTrend')}
        </Typography>
        <Box sx={{ height: 300 }}>
          <Line data={chartData} options={options} />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const ScopeDistributionChart = ({ scope1, scope2, scope3 }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const total = scope1 + scope2 + scope3;
  const scopeColors = {
    scope1: { main: theme.palette.success.main, label: t("anScope1Direct") },
    scope2: { main: theme.palette.primary.light, label: t("anScope2Energy") },
    scope3: { main: theme.palette.warning.main, label: t("anScope3ValueChain") },
  };
  
  const data = {
    labels: ["Scope 1", "Scope 2", "Scope 3"],
    datasets: [{
      data: [scope1, scope2, scope3],
      backgroundColor: [scopeColors.scope1.main, scopeColors.scope2.main, scopeColors.scope3.main],
      borderColor: theme.palette.background.paper,
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
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {t('scopeDistribution')}
        </Typography>
        
        <Grid container spacing={2}>
          <Grid size={5}>
            <Box sx={{ height: 180 }}>
              <Doughnut data={data} options={options} />
            </Box>
          </Grid>
          <Grid size={7}>
            <Stack spacing={2} sx={{ height: "100%", justifyContent: "center" }}>
              {Object.entries(scopeColors).map(([key, config]) => {
                const value = key === "scope1" ? scope1 : key === "scope2" ? scope2 : scope3;
                const pct = ((value / total) * 100).toFixed(1);
                return (
                  <Box key={key}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Box sx={{ width: 1.5, height: 1.5, borderRadius: "50%", bgcolor: config.main }} />
                        <Typography variant="body2" fontWeight={500} color="text.primary">
                          {config.label}
                        </Typography>
                      </Box>
                      <Typography variant="body2" fontWeight={600} color="text.primary">
                        {pct}%
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
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
  const theme = useTheme();
  const { t } = useTranslation('common');
  const data = {
    labels: categories.map((c) => c.name),
    datasets: [{
      label: t("chartEmissions"),
      data: categories.map((c) => c.value),
      backgroundColor: [
        theme.palette.primary.light,
        theme.palette.success.main,
        theme.palette.warning.main,
        theme.palette.error.main,
        theme.palette.secondary.light,
        theme.palette.info.main,
        theme.palette.secondary.main,
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
        grid: { color: theme.palette.divider },
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
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {t('emissionsByCategory')}
        </Typography>
        <Box sx={{ height: 280 }}>
          <Bar data={data} options={options} />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const DetailedTable = ({ data }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const scopeChipColors = {
    1: { bg: theme.palette.success.light, fg: theme.palette.success.dark },
    2: { bg: theme.palette.primary.light, fg: theme.palette.primary.dark },
    3: { bg: theme.palette.warning.light, fg: theme.palette.warning.dark },
  };
  return (
    <GlassCard>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {t('detailedBreakdown')}
        </Typography>
        <TableContainer
          component={Paper}
          elevation={0}
          sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}
        >
          <Table size="small" sx={{ "& th, & td": { textAlign: "left" } }}>
            <TableHead>
              <TableRow sx={{ bgcolor: "background.dark" }}>
                <TableCell sx={{ fontWeight: 600, color: "text.primary" }}>{t('colCategory')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.primary" }}>{t('colScope')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.primary" }}>{t('colEmissions')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.primary" }}>{t('colPercentOfTotal')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.primary" }}>{t('colVsLastPeriod')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((row, idx) => (
                <TableRow key={idx} sx={{ "&:last-child td": { borderBottom: "none" } }}>
                  <TableCell>{row.category}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={t('anScopeChip', { scope: row.scope })}
                      sx={{
                        bgcolor: scopeChipColors[row.scope]?.bg || theme.palette.secondary.light,
                        color: scopeChipColors[row.scope]?.fg || theme.palette.secondary.main,
                        fontWeight: 600,
                      }}
                    />
                  </TableCell>
                  <TableCell>{row.value.toLocaleString()}</TableCell>
                  <TableCell>{row.percentage}%</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      icon={row.change < 0 ? <TrendingDown fontSize="small" /> : <TrendingUp fontSize="small" />}
                      label={`${row.change < 0 ? "" : "+"}${row.change}%`}
                      sx={{
                        bgcolor: row.change < 0 ? "success.light" : "error.light",
                        color: row.change < 0 ? "success.dark" : "error.dark",
                        fontWeight: 600,
                        "& .MuiChip-icon": { color: "inherit" },
                      }}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </GlassCard>
  );
};

// ============ Main Component ============

export default function AnalyticsDashboard() {
  const { t } = useTranslation('common');
  useDocumentTitle(t("analyticsTitle"));
  const theme = useTheme();
  const { user, context } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  
  // Date range state
  const [quickSelect, setQuickSelect] = useState("ytd");
  const [startDate, setStartDate] = useState(dayjs().startOf("year"));
  const [endDate, setEndDate] = useState(dayjs());
  const [_showComparison, _setShowComparison] = useState(false);
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
      <PageContainer>
        <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 1.5, mb: 3 }} />
        <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 1.5, mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid size={{ xs: 12, md: 6, lg: 3 }} key={i}>
              <Skeleton variant="rectangular" height={160} sx={{ borderRadius: 1.5 }} />
            </Grid>
          ))}
        </Grid>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <Alert severity="error">{t('anLoadFailed')}{error}</Alert>
      </PageContainer>
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
    <PageContainer sx={{ maxWidth: 1400, mx: "auto", overflow: "auto" }}>
      {/* Header */}
      <Box sx={{ mb: 2.5, pb: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'flex-start' }} justifyContent="space-between" gap={1.5}>
          <Box>
            <Typography variant="h5" fontWeight={700} gutterBottom>
              {t('analyticsTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 680, lineHeight: 1.6 }}>
              {t('anDescription')}{" "}
              <Trans i18nKey="anDescriptionKpis" ns="common">For board-level KPIs see <strong>Chairman Overview</strong>.</Trans>
            </Typography>
          </Box>
          {/* Export toolbar */}
          <Stack direction="row" gap={1} flexShrink={0} alignItems="center">
            <Tooltip title={t('exportCurrentView')}>
              <Button size="small" variant="outlined" startIcon={<Download fontSize="small" />}
                sx={{ fontSize: '0.7rem', borderColor: 'divider', color: 'text.secondary', height: 30 }}>
                {t('exportCsv')}
              </Button>
            </Tooltip>
            <Tooltip title={t('refreshData')}>
              <Button size="small" variant="outlined" startIcon={<Refresh fontSize="small" />}
                onClick={() => { setData(null); }}
                sx={{ fontSize: '0.7rem', borderColor: 'divider', color: 'text.secondary', height: 30 }}>
                {t('refresh')}
              </Button>
            </Tooltip>
          </Stack>
        </Stack>
      </Box>

      {/* Scope filter chips */}
      <Box sx={{ mb: 2.5 }}>
        <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.disabled', mb: 0.75 }}>
          {t('filterByScope')}
        </Typography>
        <Stack direction="row" gap={0.75} flexWrap="wrap">
          {[
            { label: t('allScopes'), value: 'all', color: undefined },
            { label: t('scope1Combustion'), value: '1', color: theme.palette.success.main },
            { label: t('scope2Purchased'), value: '2', color: theme.palette.primary.main },
            { label: t('scope3Chain'), value: '3', color: theme.palette.warning.main },
          ].map((s) => (
            <Chip key={s.value} label={s.label} size="small" variant="outlined"
              sx={{ fontSize: '0.7rem', cursor: 'pointer',
                borderColor: s.color || 'divider',
                color: s.color ? s.color : 'text.secondary',
                '&:hover': { bgcolor: s.color ? `${s.color}12` : 'action.hover' },
              }} />
          ))}
        </Stack>
      </Box>

      {/* Date Range Selector */}
      <Box sx={{ mb: 2 }}>
        <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.disabled', mb: 0.75 }}>
          {t('dateRange')}
        </Typography>
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
      <Box sx={{ mb: 2, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Chip
          label={`${startDate.format("MMM D, YYYY")} — ${endDate.format("MMM D, YYYY")}`}
          size="small"
          icon={<CalendarMonth fontSize="small" />}
          sx={{ bgcolor: 'background.dark', color: 'text.secondary', fontWeight: 500, fontSize: '0.72rem' }}
        />
        
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={(e, v) => v && setViewMode(v)}
          size="small"
        >
          <ToggleButton value="charts">
            <BarChartIcon fontSize="small" sx={{ mr: 0.5 }} /> {t('charts')}
          </ToggleButton>
          <ToggleButton value="table">
            <TableChart fontSize="small" sx={{ mr: 0.5 }} /> {t('table')}
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Key Metrics — section label */}
      <Box sx={{ mb: 1 }}>
        <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.disabled' }}>
          {t('periodTotals')}
        </Typography>
        <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>{t('periodTotalsDesc')}</Typography>
      </Box>
      {/* Key Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricTotalEmissions')}
            value={emissions.total}
            unit="t CO₂e"
            icon={TrendingDown}
            color={theme.palette.success.main}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricScope1')}
            value={emissions.scope1}
            unit="t CO₂e"
            icon={ShowChart}
            color={theme.palette.success.main}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricScope2')}
            value={emissions.scope2}
            unit="t CO₂e"
            icon={ShowChart}
            color={theme.palette.primary.light}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricScope3')}
            value={emissions.scope3}
            unit="t CO₂e"
            icon={ShowChart}
            color={theme.palette.warning.main}
          />
        </Grid>
      </Grid>

      {/* Charts or Table View */}
      {viewMode === "charts" ? (
        <>
          {/* Trend Analysis section */}
          <Box sx={{ mb: 1, mt: 1 }}>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.disabled' }}>
              {t('trendAnalysis')}
            </Typography>
            <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>{t('trendAnalysisDesc')}</Typography>
          </Box>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, lg: 8 }}>
              <MonthlyTrendChart monthlyTrend={data?.monthly_trend} showComparison={_showComparison} />
            </Grid>
            <Grid size={{ xs: 12, lg: 4 }}>
              <ScopeDistributionChart
                scope1={emissions.scope1}
                scope2={emissions.scope2}
                scope3={emissions.scope3}
              />
            </Grid>
          </Grid>

          {/* Category Breakdown section */}
          <Box sx={{ mb: 1 }}>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.disabled' }}>
              {t('categoryBreakdown')}
            </Typography>
            <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>{t('categoryBreakdownDesc')}</Typography>
          </Box>
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
      <Box sx={{ mt: 4, pt: 3, borderTop: '1px solid', borderColor: 'divider' }}>
        <Typography variant="body2" color="text.disabled" textAlign="center">
          {t('dataRefreshed')}{dayjs().format("MMM D, YYYY h:mm A")} • 
          <Button size="small" startIcon={<Refresh fontSize="small" />} sx={{ ml: 1 }}>
            {t('refresh')}
          </Button>
        </Typography>
      </Box>
    </PageContainer>
  );
}
