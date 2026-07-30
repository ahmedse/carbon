// File: src/pages/dashboards/ExecutiveSummary.jsx
// Executive Summary Dashboard - Current state overview for leadership

import React from "react";
import {
  Box,
  Grid,
  Typography,
  Card,
  CardContent,
  Skeleton,
  Alert,
  Chip,
  LinearProgress,
  Divider,
  Stack,
  Paper,
} from "@mui/material";
import {
  TrendingDown,
  TrendingUp,
  CheckCircle,
  Warning,
  ErrorOutline,
  Nature,
  Bolt,
  Factory,
  LocalShipping,
  CalendarToday,
  Speed,
  TrackChanges,
} from "@mui/icons-material";
import { Doughnut, Line } from "react-chartjs-2";
import {
  Chart,
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from "chart.js";
import { useEmissionsData, useEmissionsComparison } from "./useEmissionsData";
import { useAuth } from "../../auth/AuthContext";

Chart.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ChartTooltip,
  Legend,
  Filler
);

// ============ Components ============

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

const TargetProgressCard = ({ current, target, baseYear, targetYear, title }) => {
  const progress = Math.min((1 - current / target) * 100, 100);
  const onTrack = progress >= ((new Date().getFullYear() - baseYear) / (targetYear - baseYear)) * 100;
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <TrackChanges sx={{ color: "#16a34a" }} />
          <Typography variant="subtitle1" fontWeight={600} color="#111827">
            {title || "Net-Zero Progress"}
          </Typography>
        </Box>
        
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="body2" color="#6b7280">
              Base Year ({baseYear})
            </Typography>
            <Typography variant="body2" color="#6b7280">
              Target ({targetYear})
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={Math.max(0, progress)}
            sx={{
              height: 12,
              borderRadius: 6,
              bgcolor: "#e5e7eb",
              "& .MuiLinearProgress-bar": {
                borderRadius: 6,
                bgcolor: onTrack ? "#16a34a" : "#f59e0b",
              },
            }}
          />
          <Box sx={{ display: "flex", justifyContent: "center", mt: 1 }}>
            <Chip
              size="small"
              icon={onTrack ? <CheckCircle fontSize="small" /> : <Warning fontSize="small" />}
              label={onTrack ? "On Track" : "Behind Target"}
              sx={{
                bgcolor: onTrack ? "#d1fae5" : "#fef3c7",
                color: onTrack ? "#059669" : "#d97706",
                fontWeight: 600,
              }}
            />
          </Box>
        </Box>
        
        <Grid container spacing={2}>
          <Grid size={4}>
            <Typography variant="caption" color="#9ca3af" display="block">
              Target
            </Typography>
            <Typography variant="h6" fontWeight={700} color="#111827">
              -50%
            </Typography>
          </Grid>
          <Grid size={4}>
            <Typography variant="caption" color="#9ca3af" display="block">
              Achieved
            </Typography>
            <Typography variant="h6" fontWeight={700} color={onTrack ? "#16a34a" : "#f59e0b"}>
              -{progress.toFixed(0)}%
            </Typography>
          </Grid>
          <Grid size={4}>
            <Typography variant="caption" color="#9ca3af" display="block">
              Remaining
            </Typography>
            <Typography variant="h6" fontWeight={700} color="#6b7280">
              {(50 - progress).toFixed(0)}%
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </GlassCard>
  );
};

const EmissionsSummaryCard = ({ total, previousTotal, changePercent, unit = "t CO₂e" }) => {
  // Use provided changePercent if available, otherwise calculate from previousTotal
  const change = changePercent !== undefined 
    ? changePercent 
    : (previousTotal ? ((total - previousTotal) / previousTotal * 100) : 0);
  const isReduction = change < 0;
  const _hasComparison = previousTotal > 0 || changePercent !== undefined;
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <Nature sx={{ color: "#16a34a" }} />
          <Typography variant="subtitle1" fontWeight={600} color="#111827">
            Total Emissions
          </Typography>
        </Box>
        
        <Typography variant="h3" fontWeight={700} color="#111827" sx={{ mb: 1 }}>
          {total.toLocaleString()}
          <Typography component="span" variant="h6" fontWeight={400} color="#6b7280" sx={{ ml: 1 }}>
            {unit}
          </Typography>
        </Typography>
        
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Chip
            size="small"
            icon={isReduction ? <TrendingDown fontSize="small" /> : <TrendingUp fontSize="small" />}
            label={`${isReduction ? "" : "+"}${change.toFixed(1)}% vs last period`}
            sx={{
              bgcolor: isReduction ? "#d1fae5" : "#fee2e2",
              color: isReduction ? "#059669" : "#dc2626",
              fontWeight: 600,
              "& .MuiChip-icon": { color: "inherit" },
            }}
          />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const ScopeBreakdownCard = ({ scope1, scope2, scope3 }) => {
  const total = scope1 + scope2 + scope3;
  const data = {
    labels: ["Scope 1", "Scope 2", "Scope 3"],
    datasets: [{
      data: [scope1, scope2, scope3],
      backgroundColor: ["#10b981", "#3b82f6", "#f59e0b"],
      borderColor: "#fff",
      borderWidth: 3,
      hoverOffset: 4,
    }],
  };
  
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "65%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.label}: ${ctx.parsed.toLocaleString()} t (${((ctx.parsed / total) * 100).toFixed(1)}%)`,
        },
      },
    },
  };
  
  const scopes = [
    { label: "Scope 1", value: scope1, color: "#10b981", desc: "Direct" },
    { label: "Scope 2", value: scope2, color: "#3b82f6", desc: "Energy" },
    { label: "Scope 3", value: scope3, color: "#f59e0b", desc: "Value chain" },
  ];
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
          Scope Breakdown
        </Typography>
        
        <Box sx={{ display: "flex", gap: 3, alignItems: "center" }}>
          <Box sx={{ width: 120, height: 120 }}>
            <Doughnut data={data} options={options} />
          </Box>
          
          <Stack spacing={1.5} sx={{ flex: 1 }}>
            {scopes.map((s) => (
              <Box key={s.label} sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: s.color }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" fontWeight={600} color="#374151">
                    {s.label}
                  </Typography>
                  <Typography variant="caption" color="#9ca3af">
                    {s.desc}
                  </Typography>
                </Box>
                <Typography variant="body2" fontWeight={600} color="#111827">
                  {s.value.toLocaleString()} t
                </Typography>
              </Box>
            ))}
          </Stack>
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const DataCompletenessCard = ({ completeness, lastUpdate }) => {
  const getStatus = (value) => {
    if (value >= 95) return { label: "Excellent", color: "#16a34a", icon: <CheckCircle /> };
    if (value >= 80) return { label: "Good", color: "#3b82f6", icon: <CheckCircle /> };
    if (value >= 60) return { label: "Needs Attention", color: "#f59e0b", icon: <Warning /> };
    return { label: "Critical", color: "#dc2626", icon: <ErrorOutline /> };
  };
  
  const status = getStatus(completeness);
  
  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <Speed sx={{ color: "#8b5cf6" }} />
          <Typography variant="subtitle1" fontWeight={600} color="#111827">
            Data Quality
          </Typography>
        </Box>
        
        <Box sx={{ display: "flex", alignItems: "center", gap: 3 }}>
          <Box sx={{ position: "relative", display: "inline-flex" }}>
            <Box
              sx={{
                width: 80,
                height: 80,
                borderRadius: "50%",
                background: `conic-gradient(${status.color} ${completeness * 3.6}deg, #e5e7eb 0deg)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Box
                sx={{
                  width: 60,
                  height: 60,
                  borderRadius: "50%",
                  bgcolor: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Typography variant="h6" fontWeight={700} color={status.color}>
                  {completeness}%
                </Typography>
              </Box>
            </Box>
          </Box>
          
          <Box>
            <Chip
              size="small"
              icon={status.icon}
              label={status.label}
              sx={{
                bgcolor: `${status.color}15`,
                color: status.color,
                fontWeight: 600,
                mb: 1,
                "& .MuiChip-icon": { color: "inherit" },
              }}
            />
            <Typography variant="caption" color="#6b7280" display="block">
              <CalendarToday sx={{ fontSize: 12, mr: 0.5, verticalAlign: "middle" }} />
              Data through {lastUpdate}
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const TopEmissionSourcesCard = ({ sources }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
        Top Emission Sources
      </Typography>
      
      <Stack spacing={2}>
        {sources.map((source, idx) => (
          <Box key={source.name}>
            <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography
                  variant="caption"
                  sx={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    bgcolor: idx === 0 ? "#dc2626" : idx === 1 ? "#f59e0b" : "#6b7280",
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                  }}
                >
                  {idx + 1}
                </Typography>
                <Typography variant="body2" fontWeight={500} color="#374151">
                  {source.name}
                </Typography>
              </Box>
              <Typography variant="body2" fontWeight={600} color="#111827">
                {source.value.toLocaleString()} t
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={source.percentage}
              sx={{
                height: 6,
                borderRadius: 3,
                bgcolor: "#e5e7eb",
                "& .MuiLinearProgress-bar": {
                  borderRadius: 3,
                  bgcolor: idx === 0 ? "#dc2626" : idx === 1 ? "#f59e0b" : "#6b7280",
                },
              }}
            />
          </Box>
        ))}
      </Stack>
    </CardContent>
  </GlassCard>
);

const QuickInsightsCard = ({ insights }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
        Key Insights
      </Typography>
      
      <Stack spacing={1.5}>
        {insights.map((insight, idx) => (
          <Paper
            key={idx}
            elevation={0}
            sx={{
              p: 1.5,
              borderRadius: 2,
              bgcolor: insight.type === "positive" ? "#f0fdf4" : insight.type === "warning" ? "#fef3c7" : "#f3f4f6",
              border: `1px solid ${insight.type === "positive" ? "#bbf7d0" : insight.type === "warning" ? "#fde68a" : "#e5e7eb"}`,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
              {insight.type === "positive" ? (
                <TrendingDown sx={{ color: "#16a34a", fontSize: 18 }} />
              ) : insight.type === "warning" ? (
                <Warning sx={{ color: "#d97706", fontSize: 18 }} />
              ) : (
                <Nature sx={{ color: "#6b7280", fontSize: 18 }} />
              )}
              <Typography variant="body2" color="#374151">
                {insight.text}
              </Typography>
            </Box>
          </Paper>
        ))}
      </Stack>
    </CardContent>
  </GlassCard>
);

// ============ Main Component ============

export default function ExecutiveSummary() {
  const { _context } = useAuth();
  const currentYear = new Date().getFullYear();
  const { data, loading, error } = useEmissionsData(currentYear);
  const { comparison } = useEmissionsComparison(currentYear, currentYear - 1);

  if (loading) {
    return (
      <Box sx={{ p: 4 }}>
        <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 3, mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid size={{ xs: 12, md: 6, lg: 3 }} key={i}>
              <Skeleton variant="rectangular" height={180} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">Failed to load dashboard data: {error}</Alert>
      </Box>
    );
  }

  // All data comes from the real API via useEmissionsData hook
  const emissions = data?.emissions || { total: 0, scope1: 0, scope2: 0, scope3: 0 };
  const topSources = data?.topSources || [];
  const insights = data?.insights || [];
  const dataQuality = data?.dataQuality || { score: 0, completeness: 0 };
  const lastUpdated = data?.lastUpdated || new Date().toLocaleDateString();
  
  // Period comparison from real API
  const previousTotal = comparison?.previousTotal || emissions.total;
  const changePercent = comparison?.changePercent || 0;

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} color="#111827" gutterBottom>
          Executive Summary
        </Typography>
        <Typography variant="body2" color="#6b7280" component="div" sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
          Your organization's carbon footprint at a glance • Data through {lastUpdated}
          {data?.dataQuality?.calculationCount > 0 && (
            <Chip
              size="small"
              label={`${data.dataQuality.calculationCount} calculations`}
              sx={{ bgcolor: "#f3f4f6", fontSize: 11 }}
            />
          )}
        </Typography>
      </Box>

      {/* Top Row - Key Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 6, lg: 3 }}>
          <EmissionsSummaryCard
            total={emissions.total}
            previousTotal={previousTotal}
            changePercent={changePercent}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6, lg: 3 }}>
          <ScopeBreakdownCard
            scope1={emissions.scope1}
            scope2={emissions.scope2}
            scope3={emissions.scope3}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6, lg: 3 }}>
          <TargetProgressCard
            current={emissions.total}
            target={emissions.total * 0.5}  // 50% reduction target - should come from settings
            baseYear={2020}
            targetYear={2030}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6, lg: 3 }}>
          <DataCompletenessCard
            completeness={dataQuality.score}
            lastUpdate={lastUpdated}
          />
        </Grid>
      </Grid>

      {/* Bottom Row */}
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <TopEmissionSourcesCard sources={topSources} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <QuickInsightsCard insights={insights} />
        </Grid>
      </Grid>

      {/* Footer */}
      <Box sx={{ mt: 4, pt: 3, borderTop: "1px solid #e5e7eb", textAlign: "center" }}>
        <Typography variant="body2" color="#9ca3af">
          Last updated: {lastUpdated} • 
          {data?.dataQuality?.calculationCount || 0} emission calculations • 
          For detailed analysis, visit Analytics Dashboard
        </Typography>
      </Box>
    </Box>
  );
}
