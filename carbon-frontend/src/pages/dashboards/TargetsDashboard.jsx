// File: src/pages/dashboards/TargetsDashboard.jsx
// Targets & Progress Dashboard - SBTi tracking and reduction goals

import React, { useState } from "react";
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
  Stack,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Divider,
  Button,
  IconButton,
  Tooltip,
} from "@mui/material";
import {
  TrendingDown,
  TrendingUp,
  CheckCircle,
  Warning,
  ErrorOutline,
  TrackChanges,
  Flag,
  Timeline,
  Speed,
  EmojiEvents,
  Info,
  Edit,
  Add,
} from "@mui/icons-material";
import { Line, Bar } from "react-chartjs-2";
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from "chart.js";
import { useDashboardData } from "../../components/dashboard/useDashboardData";
import { useYearlyComparison } from "./useEmissionsData";
import { useAuth } from "../../auth/AuthContext";

Chart.register(
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

// ============ Target Card Components ============

const MainTargetCard = ({ target, current, baseYear, targetYear, baselineValue, onEdit: _onEdit }) => {
  const totalReduction = ((baselineValue - target) / baselineValue) * 100;
  const achievedReduction = ((baselineValue - current) / baselineValue) * 100;
  const progressPercent = (achievedReduction / totalReduction) * 100;
  
  const yearsTotal = targetYear - baseYear;
  const yearsElapsed = new Date().getFullYear() - baseYear;
  const expectedProgress = (yearsElapsed / yearsTotal) * 100;
  
  const isOnTrack = progressPercent >= expectedProgress;
  const gapPercent = Math.abs(progressPercent - expectedProgress).toFixed(1);

  return (
    <GlassCard sx={{ height: "100%", border: "2px solid #16a34a" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Flag sx={{ color: "#16a34a" }} />
            <Typography variant="h6" fontWeight={700} color="#111827">
              Net-Zero Target
            </Typography>
          </Box>
          <Chip
            size="small"
            label="Primary"
            sx={{ bgcolor: "#d1fae5", color: "#059669", fontWeight: 600 }}
          />
        </Box>

        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="body2" color="#6b7280">
              Baseline ({baseYear}): {baselineValue.toLocaleString()} t
            </Typography>
            <Typography variant="body2" color="#6b7280">
              Target ({targetYear}): {target.toLocaleString()} t
            </Typography>
          </Box>
          
          <Box sx={{ position: "relative", mb: 1 }}>
            <LinearProgress
              variant="determinate"
              value={Math.min(progressPercent, 100)}
              sx={{
                height: 20,
                borderRadius: 10,
                bgcolor: "#e5e7eb",
                "& .MuiLinearProgress-bar": {
                  borderRadius: 10,
                  bgcolor: isOnTrack ? "#16a34a" : "#f59e0b",
                },
              }}
            />
            {/* Expected progress marker */}
            <Box
              sx={{
                position: "absolute",
                left: `${Math.min(expectedProgress, 100)}%`,
                top: -4,
                transform: "translateX(-50%)",
                width: 2,
                height: 28,
                bgcolor: "#374151",
              }}
            />
            <Typography
              variant="caption"
              sx={{
                position: "absolute",
                left: `${Math.min(expectedProgress, 100)}%`,
                top: -18,
                transform: "translateX(-50%)",
                color: "#6b7280",
                whiteSpace: "nowrap",
              }}
            >
              Expected
            </Typography>
          </Box>
        </Box>

        <Grid container spacing={2}>
          <Grid size={{ xs: 4 }}>
            <Paper elevation={0} sx={{ p: 1.5, bgcolor: "#f9fafb", borderRadius: 2, textAlign: "center" }}>
              <Typography variant="caption" color="#6b7280">
                Target Reduction
              </Typography>
              <Typography variant="h5" fontWeight={700} color="#111827">
                -{totalReduction.toFixed(0)}%
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 4 }}>
            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                bgcolor: isOnTrack ? "#f0fdf4" : "#fef3c7",
                borderRadius: 2,
                textAlign: "center",
              }}
            >
              <Typography variant="caption" color="#6b7280">
                Achieved
              </Typography>
              <Typography variant="h5" fontWeight={700} color={isOnTrack ? "#16a34a" : "#d97706"}>
                -{achievedReduction.toFixed(1)}%
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 4 }}>
            <Paper elevation={0} sx={{ p: 1.5, bgcolor: "#f9fafb", borderRadius: 2, textAlign: "center" }}>
              <Typography variant="caption" color="#6b7280">
                Remaining
              </Typography>
              <Typography variant="h5" fontWeight={700} color="#374151">
                {(totalReduction - achievedReduction).toFixed(1)}%
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        <Box sx={{ mt: 2, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Chip
            icon={isOnTrack ? <CheckCircle fontSize="small" /> : <Warning fontSize="small" />}
            label={isOnTrack ? `On Track - ${gapPercent}% ahead` : `Behind Target by ${gapPercent}%`}
            sx={{
              bgcolor: isOnTrack ? "#d1fae5" : "#fef3c7",
              color: isOnTrack ? "#059669" : "#d97706",
              fontWeight: 600,
              "& .MuiChip-icon": { color: "inherit" },
            }}
          />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const ScopeTargetCard = ({ name, color, target, current, baselineValue, targetYear }) => {
  const reductionTarget = ((baselineValue - target) / baselineValue) * 100;
  const achieved = ((baselineValue - current) / baselineValue) * 100;
  const progress = Math.min((achieved / reductionTarget) * 100, 100);
  const _isOnTrack = progress >= 50;

  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 2.5 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: color }} />
          <Typography variant="subtitle1" fontWeight={600} color="#111827">
            {name}
          </Typography>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
            <Typography variant="caption" color="#6b7280">
              Progress to {targetYear}
            </Typography>
            <Typography variant="caption" fontWeight={600} color="#374151">
              {achieved.toFixed(1)}% of {reductionTarget.toFixed(0)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 8,
              borderRadius: 4,
              bgcolor: "#e5e7eb",
              "& .MuiLinearProgress-bar": {
                borderRadius: 4,
                bgcolor: color,
              },
            }}
          />
        </Box>

        <Stack direction="row" spacing={1} justifyContent="space-between">
          <Box>
            <Typography variant="caption" color="#9ca3af">
              Current
            </Typography>
            <Typography variant="body2" fontWeight={600} color="#111827">
              {current.toLocaleString()} t
            </Typography>
          </Box>
          <Box textAlign="right">
            <Typography variant="caption" color="#9ca3af">
              Target
            </Typography>
            <Typography variant="body2" fontWeight={600} color="#111827">
              {target.toLocaleString()} t
            </Typography>
          </Box>
        </Stack>
      </CardContent>
    </GlassCard>
  );
};

// ============ Chart Components ============

const TrajectoryChart = ({ yearlyData, targets, baselineTotal }) => {
  // Build data from real API data
  const years = (yearlyData || []).map(y => y.year);
  const actuals = (yearlyData || []).map(y => y.total);
  const targetValues = (targets || []).map(t => t.targetTotal);
  
  // Extend years to 2030 for projection
  const allYears = [...years];
  const projectedData = actuals.map(() => null);
  const lastYear = Math.max(...years);
  const lastTotal = actuals[actuals.length - 1] || 0;
  
  // Project forward to 2030 if we haven't reached it
  for (let y = lastYear + 1; y <= 2030; y++) {
    allYears.push(y);
    actuals.push(null);
    // Assume continued 5% annual reduction for projection
    const yearsAhead = y - lastYear;
    projectedData.push(Math.round(lastTotal * Math.pow(0.95, yearsAhead)));
    targetValues.push((baselineTotal || 3493) * (1 - 0.05 * (y - 2020)));
  }
  
  // Mark last actual point for projection start
  if (projectedData.length > years.length) {
    projectedData[years.length - 1] = actuals[years.length - 1];
  }
  
  const chartData = {
    labels: allYears,
    datasets: [
      {
        label: "Actual Emissions",
        data: actuals,
        borderColor: "#16a34a",
        backgroundColor: "#16a34a",
        pointRadius: 6,
        pointBackgroundColor: "#16a34a",
        tension: 0.3,
      },
      {
        label: "Target Pathway (1.5°C aligned)",
        data: targetValues,
        borderColor: "#3b82f6",
        borderDash: [8, 4],
        pointRadius: 0,
        tension: 0.1,
      },
      {
        label: "Projected (current trajectory)",
        data: projectedData,
        borderColor: "#f59e0b",
        borderDash: [4, 4],
        pointRadius: 0,
        tension: 0.3,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top",
        labels: { usePointStyle: true, padding: 15 },
      },
      tooltip: {
        mode: "index",
        intersect: false,
        callbacks: {
          label: (ctx) =>
            ctx.parsed.y !== null
              ? `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()} t CO₂e`
              : null,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        grid: { color: "#f3f4f6" },
        ticks: { callback: (v) => `${(v / 1000).toFixed(1)}k` },
        title: { display: true, text: "Emissions (t CO₂e)" },
      },
      x: {
        grid: { display: false },
        title: { display: true, text: "Year" },
      },
    },
  };

  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} color="#111827">
            Emissions Trajectory
          </Typography>
          <Chip size="small" label="SBTi 1.5°C Aligned" sx={{ bgcolor: "#dbeafe", color: "#2563eb" }} />
        </Box>
        <Box sx={{ height: 320 }}>
          <Line data={chartData} options={options} />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const AnnualProgressChart = ({ yearlyData }) => {
  // Use real year-over-year change data from API
  const years = (yearlyData || []).map(y => String(y.year));
  const reductions = (yearlyData || []).map(y => Math.abs(y.yoyChange || 0));
  const currentYear = new Date().getFullYear();
  
  const chartData = {
    labels: years,
    datasets: [
      {
        label: "Annual Reduction",
        data: reductions,
        backgroundColor: years.map((y) => (parseInt(y) <= currentYear ? "#16a34a" : "#3b82f6")),
        borderRadius: 6,
        barThickness: 32,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `Reduction: ${ctx.parsed.y.toFixed(1)}%`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: "#f3f4f6" },
        ticks: { callback: (v) => `${v}%` },
        title: { display: true, text: "Year-over-Year Reduction (%)"},
      },
      x: {
        grid: { display: false },
      },
    },
  };

  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
          Annual Reduction Progress
        </Typography>
        <Box sx={{ height: 280 }}>
          <Bar data={chartData} options={options} />
        </Box>
      </CardContent>
    </GlassCard>
  );
};

// ============ Milestones Component ============

const MilestonesCard = ({ milestones }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827">
          Key Milestones
        </Typography>
        <Button size="small" startIcon={<Add fontSize="small" />}>
          Add
        </Button>
      </Box>

      <Stack spacing={2}>
        {milestones.map((milestone, idx) => (
          <Paper
            key={idx}
            elevation={0}
            sx={{
              p: 2,
              borderRadius: 2,
              bgcolor: milestone.completed ? "#f0fdf4" : "#f9fafb",
              border: `1px solid ${milestone.completed ? "#bbf7d0" : "#e5e7eb"}`,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
              {milestone.completed ? (
                <CheckCircle sx={{ color: "#16a34a", fontSize: 20 }} />
              ) : (
                <Box
                  sx={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    border: "2px solid #d1d5db",
                  }}
                />
              )}
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2" fontWeight={600} color="#111827">
                  {milestone.title}
                </Typography>
                <Typography variant="caption" color="#6b7280">
                  {milestone.date} • {milestone.description}
                </Typography>
              </Box>
              {milestone.completed && (
                <EmojiEvents sx={{ color: "#f59e0b", fontSize: 18 }} />
              )}
            </Box>
          </Paper>
        ))}
      </Stack>
    </CardContent>
  </GlassCard>
);

// ============ Main Component ============

export default function TargetsDashboard() {
  const { user, context } = useAuth();
  const { _data, loading, error } = useDashboardData(context?.projectId, user?.token);
  const { data: yearlyData, loading: yearlyLoading, error: yearlyError } = useYearlyComparison();
  const [targetScenario, setTargetScenario] = useState("1.5c");

  if (loading || yearlyLoading) {
    return (
      <Box sx={{ p: 4 }}>
        <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 2, mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid size={{ xs: 12, md: 6 }} key={i}>
              <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (error || yearlyError) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">Failed to load targets data: {error || yearlyError}</Alert>
      </Box>
    );
  }

  // Use real data from API
  const baselineYear = yearlyData?.baselineYear || 2020;
  const baselineTotal = yearlyData?.baselineTotal || 3493;
  const currentTotal = yearlyData?.currentTotal || 2516;
  const target2030 = yearlyData?.target2030 || baselineTotal * 0.5;
  
  // Get scope breakdown from yearly data
  const currentYearRecord = (yearlyData?.yearlyData || []).find(y => y.year === yearlyData?.currentYear) || {};
  const baselineYearRecord = (yearlyData?.yearlyData || []).find(y => y.year === baselineYear) || {};
  
  const emissions = {
    total: currentTotal,
    scope1: currentYearRecord.scope1 || 0,
    scope2: currentYearRecord.scope2 || 0,
    scope3: currentYearRecord.scope3 || 0,
  };
  
  const baselineEmissions = {
    scope1: baselineYearRecord.scope1 || 0,
    scope2: baselineYearRecord.scope2 || 0,
    scope3: baselineYearRecord.scope3 || 0,
  };
  
  const milestones = [
    { title: "50% Renewable Energy", date: "Q2 2024", description: "Switch headquarters to 50% renewable", completed: true },
    { title: "Fleet Electrification", date: "Q4 2024", description: "30% of fleet converted to EV", completed: true },
    { title: "Supply Chain Engagement", date: "Q2 2025", description: "Top 50 suppliers committed to SBTi", completed: false },
    { title: "Carbon Neutral Operations", date: "Q4 2026", description: "Scope 1 & 2 net-zero", completed: false },
  ];

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Box>
          <Typography variant="h4" fontWeight={700} color="#111827" gutterBottom>
            Targets & Progress
          </Typography>
          <Typography variant="body2" color="#6b7280">
            Track your journey towards net-zero and SBTi commitments • Baseline Year: {baselineYear}
          </Typography>
        </Box>
        
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Target Scenario</InputLabel>
          <Select
            value={targetScenario}
            label="Target Scenario"
            onChange={(e) => setTargetScenario(e.target.value)}
          >
            <MenuItem value="1.5c">1.5°C Pathway (SBTi)</MenuItem>
            <MenuItem value="2c">Well-below 2°C</MenuItem>
            <MenuItem value="custom">Custom Target</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Main Target */}
      <Box sx={{ mb: 3 }}>
        <MainTargetCard
          target={target2030}
          current={currentTotal}
          baseYear={baselineYear}
          targetYear={2030}
          baselineValue={baselineTotal}
        />
      </Box>

      {/* Scope Targets */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <ScopeTargetCard
            scope={1}
            name="Scope 1 - Direct Emissions"
            color="#10b981"
            target={baselineEmissions.scope1 * 0.5}
            current={emissions.scope1}
            baselineValue={baselineEmissions.scope1}
            targetYear={2030}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <ScopeTargetCard
            scope={2}
            name="Scope 2 - Energy"
            color="#3b82f6"
            target={baselineEmissions.scope2 * 0.5}
            current={emissions.scope2}
            baselineValue={baselineEmissions.scope2}
            targetYear={2030}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <ScopeTargetCard
            scope={3}
            name="Scope 3 - Value Chain"
            color="#f59e0b"
            target={baselineEmissions.scope3 * 0.5}
            current={emissions.scope3}
            baselineValue={baselineEmissions.scope3}
            targetYear={2030}
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, lg: 8 }}>
          <TrajectoryChart 
            yearlyData={yearlyData?.yearlyData} 
            targets={yearlyData?.targets}
            baselineTotal={baselineTotal}
          />
        </Grid>
        <Grid size={{ xs: 12, lg: 4 }}>
          <MilestonesCard milestones={milestones} />
        </Grid>
      </Grid>

      {/* Annual Progress */}
      <Grid container spacing={3}>
        <Grid size={{ xs: 12 }}>
          <AnnualProgressChart yearlyData={yearlyData?.yearlyData} />
        </Grid>
      </Grid>

      {/* Footer Info */}
      <Paper
        elevation={0}
        sx={{ mt: 3, p: 2, bgcolor: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 2 }}
      >
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
          <Info sx={{ color: "#0284c7", fontSize: 20 }} />
          <Box>
            <Typography variant="body2" fontWeight={600} color="#0369a1">
              About SBTi Targets
            </Typography>
            <Typography variant="caption" color="#0369a1">
              Science Based Targets initiative (SBTi) validates corporate emissions reduction targets against climate science.
              1.5°C-aligned targets require approximately 4.2% annual reduction in absolute emissions.
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
}
