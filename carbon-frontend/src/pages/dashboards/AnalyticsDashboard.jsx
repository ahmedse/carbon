// File: src/pages/dashboards/AnalyticsDashboard.jsx
// Analytics Dashboard - Full date range analysis with comparison features

import React, { useState, useEffect } from "react";
import {
  Box,
  Grid,
  Typography,
  Card,
  CardContent,
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
import { alpha, useTheme } from "@mui/material/styles";
import { DatePicker, LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import { useTranslation, Trans } from "react-i18next";
import { MarketBasedAbsentAlert, Scope2MethodChip, scope2MethodLabel } from "../carbon/Scope2Labels";
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
import PageHeader from "../../components/Page/PageHeader";
import LoadingSkeleton from "../../components/Page/LoadingSkeleton";

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

const MetricCard = ({ title, value, unit, change, changeLabel, icon: _Icon, color = null, extra }) => {
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
              bgcolor: alpha(accent, 0.08),
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <_Icon sx={{ color: accent }} fontSize="medium" />
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
        
        {extra}
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

const MonthlyTrendChart = ({ monthlyTrend, showComparison: _showComparison, scopeFilter = 'all', scope2Method = '' }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const { t: te } = useTranslation('emissions');
  const showScope = (n) => scopeFilter === 'all' || scopeFilter === String(n);
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
      ...(scopeFilter === 'all' ? [{
        label: t("chartTotalEmissions"),
        data: monthlyTotals,
        borderColor: theme.palette.primary.light,
        backgroundColor: alpha(theme.palette.primary.light, 0.1),
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: theme.palette.primary.light,
      }] : []),
      // Scope breakdown lines
      ...(showScope(1) ? [{
        label: te("scope1"),
        data: monthlyTrend?.map(m => m.scope1) || [],
        borderColor: scopeColors[1],
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
      }] : []),
      ...(showScope(2) ? [{
        label: `${te("scope2")} (${scope2MethodLabel(scope2Method, te)})`,
        data: monthlyTrend?.map(m => m.scope2) || [],
        borderColor: scopeColors[2],
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
        borderDash: [5, 5],
      }] : []),
      ...(showScope(3) ? [{
        label: te("scope3"),
        data: monthlyTrend?.map(m => m.scope3) || [],
        borderColor: scopeColors[3],
        backgroundColor: "transparent",
        tension: 0.4,
        pointRadius: 2,
        borderWidth: 2,
        borderDash: [2, 2],
      }] : []),
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

const ScopeDistributionChart = ({ scope1, scope2, scope3, scopeFilter = 'all', scope2Method = '' }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const { t: te } = useTranslation('emissions');
  const showScope = (n) => scopeFilter === 'all' || scopeFilter === String(n);
  const rows = [
    showScope(1) ? { key: 'scope1', value: scope1, main: theme.palette.success.main, label: t('anScope1Direct') } : null,
    showScope(2) ? {
      key: 'scope2',
      value: scope2,
      main: theme.palette.primary.light,
      label: `${t('anScope2Energy')} (${scope2MethodLabel(scope2Method, te)})`,
    } : null,
    showScope(3) ? { key: 'scope3', value: scope3, main: theme.palette.warning.main, label: t('anScope3ValueChain') } : null,
  ].filter(Boolean);
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  
  const data = {
    labels: rows.map((row) => row.label),
    datasets: [{
      data: rows.map((row) => row.value),
      backgroundColor: rows.map((row) => row.main),
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
          label: (ctx) => `${ctx.label}: ${ctx.parsed.toLocaleString()} ${te('tCo2eUnit')} (${total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : '0.0'}%)`,
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
              {rows.map((row) => {
                const pct = total > 0 ? ((row.value / total) * 100).toFixed(1) : '0.0';
                return (
                  <Box key={row.key}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Box sx={{ width: 1.5, height: 1.5, borderRadius: "50%", bgcolor: row.main }} />
                        <Typography variant="body2" fontWeight={500} color="text.primary">
                          {row.label}
                        </Typography>
                      </Box>
                      <Typography variant="body2" fontWeight={600} color="text.primary">
                        {pct}%
                      </Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {row.value.toLocaleString()} {te('tCo2eUnit')}
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
  const { t: te } = useTranslation('emissions');
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
          label: (ctx) => `${ctx.parsed.x.toLocaleString()} ${te('tCo2eUnit')}`,
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

const DetailedTable = ({ data, scope2Method = '' }) => {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const { t: te } = useTranslation('emissions');
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
                      label={Number(row.scope) === 2
                        ? `${t('anScopeChip', { scope: row.scope })} (${scope2MethodLabel(scope2Method, te)})`
                        : t('anScopeChip', { scope: row.scope })}
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

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadVisibleCsv(rows) {
  const header = ['category', 'scope', 'co2e_tonnes', 'percent_of_period'];
  const body = rows.map((row) => [row.category, row.scope, row.value, row.percentage].map(csvCell).join(','));
  const blob = new Blob([[header.join(','), ...body].join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'carbon-analytics.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}

// ============ Main Component ============

export default function AnalyticsDashboard() {
  const { t } = useTranslation('common');
  const { t: te } = useTranslation('emissions');
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
  const [scopeFilter, setScopeFilter] = useState('all');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
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
  }, [endDate, user?.token, context?.projectId, reloadKey]);

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
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <Alert
          severity="error"
          action={<Button size="small" onClick={() => setReloadKey((n) => n + 1)}>{te('common:retry', { defaultValue: 'Retry' })}</Button>}
        >
          {t('anLoadFailed')}{error}
        </Alert>
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
  const scope2Method = (data?.scope_breakdown || []).find((row) => Number(row.scope) === 2)?.scope2_method || '';
  const showScope = (n) => scopeFilter === 'all' || scopeFilter === String(n);
  const visibleCategories = categories.filter((cat) => showScope(cat.scope));
  const visibleTable = tableData.filter((row) => showScope(row.scope));

  return (
    <PageContainer sx={{ maxWidth: 1400, mx: "auto", overflow: "auto" }}>
      <PageHeader
        title={t('analyticsTitle')}
        subtitle={t('anDescription')}
        actions={(
          <Stack direction="row" gap={1} flexShrink={0} alignItems="center">
            <Tooltip title={t('exportCurrentView')}>
              <Button size="small" variant="outlined" startIcon={<Download fontSize="small" />}
                onClick={() => downloadVisibleCsv(visibleTable)}>
                {t('exportCsv')}
              </Button>
            </Tooltip>
            <Tooltip title={t('refreshData')}>
              <Button size="small" variant="outlined" startIcon={<Refresh fontSize="small" />}
                onClick={() => setReloadKey((n) => n + 1)}>
                {t('refresh')}
              </Button>
            </Tooltip>
          </Stack>
        )}
      />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: 680 }}>
        <Trans i18nKey="anDescriptionKpis" ns="common">For board-level KPIs see <strong>Chairman Overview</strong>.</Trans>
      </Typography>

      {/* Scope filter chips */}
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="overline" color="text.disabled" display="block" sx={{ mb: 0.75 }}>
          {t('filterByScope')}
        </Typography>
        <Stack direction="row" gap={0.75} flexWrap="wrap">
          {[
            { label: t('allScopes'), value: 'all', color: 'default' },
            { label: t('scope1Combustion'), value: '1', color: 'success' },
            { label: `${t('scope2Purchased')} (${scope2MethodLabel(scope2Method, te)})`, value: '2', color: 'primary' },
            { label: t('scope3Chain'), value: '3', color: 'warning' },
          ].map((s) => (
            <Chip
              key={s.value}
              label={s.label}
              size="small"
              color={s.color}
              variant={scopeFilter === s.value ? 'filled' : 'outlined'}
              onClick={() => setScopeFilter(s.value)}
            />
          ))}
        </Stack>
      </Box>

      {/* Date Range Selector */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="overline" color="text.disabled" display="block" sx={{ mb: 0.75 }}>
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
          sx={{ bgcolor: 'action.hover', color: 'text.secondary', fontWeight: 500 }}
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

      <MarketBasedAbsentAlert payload={data} />

      {/* Key Metrics — section label */}
      <Box sx={{ mb: 1 }}>
        <Typography variant="overline" color="text.disabled" display="block">
          {t('periodTotals')}
        </Typography>
        <Typography variant="caption" color="text.disabled">{t('periodTotalsDesc')}</Typography>
      </Box>
      {/* Key Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {showScope('all') && scopeFilter === 'all' && (
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricTotalEmissions')}
            value={emissions.total}
            unit={te('tCo2eUnit')}
            icon={TrendingDown}
            color={theme.palette.success.main}
          />
        </Grid>
        )}
        {showScope(1) && (
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricScope1')}
            value={emissions.scope1}
            unit={te('tCo2eUnit')}
            icon={ShowChart}
            color={theme.palette.success.main}
          />
        </Grid>
        )}
        {showScope(2) && (
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricScope2')}
            value={emissions.scope2}
            unit={te('tCo2eUnit')}
            icon={ShowChart}
            color={theme.palette.primary.light}
            extra={<Scope2MethodChip method={scope2Method} scope={2} />}
          />
        </Grid>
        )}
        {showScope(3) && (
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            title={t('metricScope3')}
            value={emissions.scope3}
            unit={te('tCo2eUnit')}
            icon={ShowChart}
            color={theme.palette.warning.main}
          />
        </Grid>
        )}
      </Grid>

      {/* Charts or Table View */}
      {viewMode === "charts" ? (
        <>
          {/* Trend Analysis section */}
          <Box sx={{ mb: 1, mt: 1 }}>
            <Typography variant="overline" color="text.disabled" display="block">
              {t('trendAnalysis')}
            </Typography>
            <Typography variant="caption" color="text.disabled">{t('trendAnalysisDesc')}</Typography>
          </Box>
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, lg: 8 }}>
              <MonthlyTrendChart
                monthlyTrend={data?.monthly_trend}
                showComparison={_showComparison}
                scopeFilter={scopeFilter}
                scope2Method={scope2Method}
              />
            </Grid>
            <Grid size={{ xs: 12, lg: 4 }}>
              <ScopeDistributionChart
                scope1={emissions.scope1}
                scope2={emissions.scope2}
                scope3={emissions.scope3}
                scopeFilter={scopeFilter}
                scope2Method={scope2Method}
              />
            </Grid>
          </Grid>

          {/* Category Breakdown section */}
          <Box sx={{ mb: 1 }}>
            <Typography variant="overline" color="text.disabled" display="block">
              {t('categoryBreakdown')}
            </Typography>
            <Typography variant="caption" color="text.disabled">{t('categoryBreakdownDesc')}</Typography>
          </Box>
          <Grid container spacing={3}>
            <Grid size={12}>
              <CategoryBreakdownChart categories={visibleCategories} />
            </Grid>
          </Grid>
        </>
      ) : (
        <DetailedTable data={visibleTable} scope2Method={scope2Method} />
      )}

      {/* Footer */}
      <Box sx={{ mt: 4, pt: 3, borderTop: '1px solid', borderColor: 'divider' }}>
        <Typography variant="body2" color="text.disabled" textAlign="center">
          {t('dataRefreshed')}{dayjs().format("MMM D, YYYY h:mm A")} • 
          <Button size="small" startIcon={<Refresh fontSize="small" />} sx={{ ml: 1 }} onClick={() => setReloadKey((n) => n + 1)}>
            {t('refresh')}
          </Button>
        </Typography>
      </Box>
    </PageContainer>
  );
}
