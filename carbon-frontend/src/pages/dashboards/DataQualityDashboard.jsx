// File: src/pages/dashboards/DataQualityDashboard.jsx
// Data Quality Dashboard - Audit readiness and data completeness tracking

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
  Button,
  IconButton,
  Tooltip,
  Divider,
  Collapse,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
} from "@mui/material";
import {
  CheckCircle,
  Warning,
  ErrorOutline,
  Speed,
  VerifiedUser,
  DataUsage,
  Storage,
  Description,
  ExpandMore,
  ExpandLess,
  Refresh,
  Download,
  PlaylistAddCheck,
  Calculate,
  Link as LinkIcon,
  Schedule,
} from "@mui/icons-material";
import { Doughnut, Bar } from "react-chartjs-2";
import {
  Chart,
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip as ChartTooltip,
  Legend,
} from "chart.js";
import { useDashboardData } from "../../components/dashboard/useDashboardData";
import { useAuth } from "../../auth/AuthContext";

Chart.register(ArcElement, CategoryScale, LinearScale, BarElement, ChartTooltip, Legend);

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

// ============ Quality Score Components ============

const OverallScoreCard = ({ score, breakdown }) => {
  const getScoreStatus = (s) => {
    if (s >= 95) return { label: "Excellent", color: "#16a34a", bg: "#d1fae5" };
    if (s >= 80) return { label: "Good", color: "#3b82f6", bg: "#dbeafe" };
    if (s >= 60) return { label: "Fair", color: "#f59e0b", bg: "#fef3c7" };
    return { label: "Needs Work", color: "#dc2626", bg: "#fee2e2" };
  };

  const status = getScoreStatus(score);

  return (
    <GlassCard sx={{ height: "100%", border: `2px solid ${status.color}20` }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 3 }}>
          <Speed sx={{ color: status.color }} />
          <Typography variant="h6" fontWeight={700} color="#111827">
            Data Quality Score
          </Typography>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 4 }}>
          {/* Circular Score */}
          <Box sx={{ position: "relative", width: 140, height: 140 }}>
            <Box
              sx={{
                width: 140,
                height: 140,
                borderRadius: "50%",
                background: `conic-gradient(${status.color} ${score * 3.6}deg, #e5e7eb 0deg)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Box
                sx={{
                  width: 110,
                  height: 110,
                  borderRadius: "50%",
                  bgcolor: "#fff",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Typography variant="h3" fontWeight={700} color={status.color}>
                  {score}
                </Typography>
                <Typography variant="caption" color="#6b7280">
                  out of 100
                </Typography>
              </Box>
            </Box>
          </Box>

          {/* Breakdown */}
          <Box sx={{ flex: 1 }}>
            <Chip
              label={status.label}
              sx={{ bgcolor: status.bg, color: status.color, fontWeight: 600, mb: 2 }}
            />
            <Stack spacing={1.5}>
              {breakdown.map((item) => (
                <Box key={item.label}>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                    <Typography variant="body2" color="#374151">
                      {item.label}
                    </Typography>
                    <Typography variant="body2" fontWeight={600} color="#111827">
                      {item.score}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={item.score}
                    sx={{
                      height: 6,
                      borderRadius: 3,
                      bgcolor: "#e5e7eb",
                      "& .MuiLinearProgress-bar": {
                        borderRadius: 3,
                        bgcolor: item.score >= 90 ? "#16a34a" : item.score >= 70 ? "#3b82f6" : "#f59e0b",
                      },
                    }}
                  />
                </Box>
              ))}
            </Stack>
          </Box>
        </Box>
      </CardContent>
    </GlassCard>
  );
};

const MetricCard = ({ icon: _Icon, title, value, status, description, color }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 2.5 }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", gap: 2 }}>
        <Box
          sx={{
            width: 44,
            height: 44,
            borderRadius: 2,
            bgcolor: `${color}15`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <_Icon sx={{ color, fontSize: 24 }} />
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="caption" color="#6b7280">
            {title}
          </Typography>
          <Typography variant="h5" fontWeight={700} color="#111827">
            {value}
          </Typography>
          <Chip
            size="small"
            label={status}
            sx={{
              mt: 0.5,
              bgcolor:
                status === "Complete" || status === "Verified"
                  ? "#d1fae5"
                  : status === "Pending"
                  ? "#fef3c7"
                  : "#fee2e2",
              color:
                status === "Complete" || status === "Verified"
                  ? "#059669"
                  : status === "Pending"
                  ? "#d97706"
                  : "#dc2626",
              fontWeight: 600,
              fontSize: 11,
            }}
          />
        </Box>
      </Box>
      {description && (
        <Typography variant="caption" color="#9ca3af" sx={{ mt: 1.5, display: "block" }}>
          {description}
        </Typography>
      )}
    </CardContent>
  </GlassCard>
);

// ============ Data Coverage Component ============

const DataCoverageChart = ({ coverage }) => {
  const data = {
    labels: ["Actual Data", "Estimated", "Missing"],
    datasets: [
      {
        data: [coverage.actual, coverage.estimated, coverage.missing],
        backgroundColor: ["#16a34a", "#f59e0b", "#ef4444"],
        borderColor: "#fff",
        borderWidth: 3,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "65%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.label}: ${ctx.parsed}%`,
        },
      },
    },
  };

  const items = [
    { label: "Actual Data", value: coverage.actual, color: "#16a34a", desc: "Primary source verified" },
    { label: "Estimated", value: coverage.estimated, color: "#f59e0b", desc: "Calculated using proxies" },
    { label: "Missing", value: coverage.missing, color: "#ef4444", desc: "Data gaps to address" },
  ];

  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
          Data Coverage
        </Typography>

        <Grid container spacing={2}>
          <Grid size={{ xs: 5 }}>
            <Box sx={{ height: 160 }}>
              <Doughnut data={data} options={options} />
            </Box>
          </Grid>
          <Grid size={{ xs: 7 }}>
            <Stack spacing={1.5} sx={{ height: "100%", justifyContent: "center" }}>
              {items.map((item) => (
                <Box key={item.label}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: item.color }} />
                    <Typography variant="body2" fontWeight={500} color="#374151">
                      {item.label}
                    </Typography>
                    <Typography variant="body2" fontWeight={700} color="#111827" sx={{ ml: "auto" }}>
                      {item.value}%
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="#9ca3af">
                    {item.desc}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Grid>
        </Grid>
      </CardContent>
    </GlassCard>
  );
};

// ============ Validation Issues Component ============

const ValidationIssuesCard = ({ issues }) => {
  const [expanded, setExpanded] = useState(false);
  
  const criticalCount = issues.filter((i) => i.severity === "critical").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;
  const _infoCount = issues.filter((i) => i.severity === "info").length;

  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} color="#111827">
            Validation Issues
          </Typography>
          <Stack direction="row" spacing={1}>
            {criticalCount > 0 && (
              <Chip
                size="small"
                icon={<ErrorOutline fontSize="small" />}
                label={criticalCount}
                sx={{ bgcolor: "#fee2e2", color: "#dc2626", fontWeight: 600, "& .MuiChip-icon": { color: "inherit" } }}
              />
            )}
            {warningCount > 0 && (
              <Chip
                size="small"
                icon={<Warning fontSize="small" />}
                label={warningCount}
                sx={{ bgcolor: "#fef3c7", color: "#d97706", fontWeight: 600, "& .MuiChip-icon": { color: "inherit" } }}
              />
            )}
            <Chip
              size="small"
              label={`${issues.length} total`}
              sx={{ bgcolor: "#f3f4f6", color: "#374151", fontWeight: 600 }}
            />
          </Stack>
        </Box>

        <Stack spacing={1}>
          {issues.slice(0, expanded ? issues.length : 3).map((issue, idx) => (
            <Paper
              key={idx}
              elevation={0}
              sx={{
                p: 1.5,
                borderRadius: 2,
                bgcolor:
                  issue.severity === "critical"
                    ? "#fef2f2"
                    : issue.severity === "warning"
                    ? "#fffbeb"
                    : "#f9fafb",
                border: `1px solid ${
                  issue.severity === "critical"
                    ? "#fecaca"
                    : issue.severity === "warning"
                    ? "#fde68a"
                    : "#e5e7eb"
                }`,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
                {issue.severity === "critical" ? (
                  <ErrorOutline sx={{ color: "#dc2626", fontSize: 18 }} />
                ) : issue.severity === "warning" ? (
                  <Warning sx={{ color: "#d97706", fontSize: 18 }} />
                ) : (
                  <CheckCircle sx={{ color: "#6b7280", fontSize: 18 }} />
                )}
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" fontWeight={500} color="#111827">
                    {issue.title}
                  </Typography>
                  <Typography variant="caption" color="#6b7280">
                    {issue.description} • {issue.location}
                  </Typography>
                </Box>
                <Button size="small" sx={{ minWidth: "auto", fontSize: 12 }}>
                  Fix
                </Button>
              </Box>
            </Paper>
          ))}
        </Stack>

        {issues.length > 3 && (
          <Button
            size="small"
            endIcon={expanded ? <ExpandLess /> : <ExpandMore />}
            onClick={() => setExpanded(!expanded)}
            sx={{ mt: 1.5, color: "#6b7280" }}
          >
            {expanded ? "Show Less" : `Show ${issues.length - 3} More`}
          </Button>
        )}
      </CardContent>
    </GlassCard>
  );
};

// ============ Scope Completeness Component ============

const ScopeCompletenessCard = ({ scopes }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
        Scope Completeness
      </Typography>

      <Stack spacing={2}>
        {scopes.map((scope) => (
          <Box key={scope.name}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 0.5 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: scope.color }} />
                <Typography variant="body2" fontWeight={500} color="#374151">
                  {scope.name}
                </Typography>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography variant="body2" fontWeight={600} color="#111827">
                  {scope.completeness}%
                </Typography>
                {scope.completeness === 100 ? (
                  <CheckCircle sx={{ color: "#16a34a", fontSize: 16 }} />
                ) : scope.completeness >= 80 ? (
                  <Warning sx={{ color: "#f59e0b", fontSize: 16 }} />
                ) : (
                  <ErrorOutline sx={{ color: "#dc2626", fontSize: 16 }} />
                )}
              </Box>
            </Box>
            <LinearProgress
              variant="determinate"
              value={scope.completeness}
              sx={{
                height: 8,
                borderRadius: 4,
                bgcolor: "#e5e7eb",
                "& .MuiLinearProgress-bar": {
                  borderRadius: 4,
                  bgcolor: scope.color,
                },
              }}
            />
            <Typography variant="caption" color="#9ca3af" sx={{ mt: 0.5, display: "block" }}>
              {scope.categories} categories • {scope.entries} data entries
            </Typography>
          </Box>
        ))}
      </Stack>
    </CardContent>
  </GlassCard>
);

// ============ Audit Trail Component ============

const AuditTrailCard = ({ entries }) => (
  <GlassCard>
    <CardContent sx={{ p: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} color="#111827">
          Recent Activity
        </Typography>
        <Button size="small" endIcon={<Download fontSize="small" />}>
          Export Log
        </Button>
      </Box>

      <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid #e5e7eb", borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: "#f9fafb" }}>
              <TableCell sx={{ fontWeight: 600, color: "#374151" }}>Action</TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#374151" }}>User</TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#374151" }}>Category</TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#374151" }}>Time</TableCell>
              <TableCell sx={{ fontWeight: 600, color: "#374151" }}>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {entries.map((entry, idx) => (
              <TableRow key={idx}>
                <TableCell>{entry.action}</TableCell>
                <TableCell>{entry.user}</TableCell>
                <TableCell>{entry.category}</TableCell>
                <TableCell>
                  <Typography variant="caption" color="#6b7280">
                    {entry.time}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={entry.status}
                    sx={{
                      bgcolor: entry.status === "Verified" ? "#d1fae5" : "#dbeafe",
                      color: entry.status === "Verified" ? "#059669" : "#2563eb",
                      fontWeight: 600,
                      fontSize: 11,
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

// ============ Main Component ============

export default function DataQualityDashboard() {
  const { user: _user, context } = useAuth();
  const { data: _data, loading, error } = useDashboardData(context?.projectId, _user?.token);

  if (loading) {
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

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">Failed to load data quality metrics: {error}</Alert>
      </Box>
    );
  }

  // Mock data for demonstration
  const qualityBreakdown = [
    { label: "Completeness", score: 92 },
    { label: "Accuracy", score: 88 },
    { label: "Timeliness", score: 95 },
    { label: "Consistency", score: 85 },
  ];

  const coverage = { actual: 72, estimated: 23, missing: 5 };

  const issues = [
    { severity: "critical", title: "Missing Scope 3 Category 6", description: "Business travel data incomplete", location: "Q3 2025" },
    { severity: "warning", title: "High estimation ratio", description: "Employee commuting >60% estimated", location: "Category 7" },
    { severity: "warning", title: "Emission factor update needed", description: "Grid factor outdated (2023)", location: "Scope 2" },
    { severity: "info", title: "Data validation pending", description: "Awaiting third-party verification", location: "Scope 1" },
  ];

  const scopes = [
    { name: "Scope 1 - Direct", color: "#10b981", completeness: 100, categories: 3, entries: 156 },
    { name: "Scope 2 - Energy", color: "#3b82f6", completeness: 100, categories: 2, entries: 48 },
    { name: "Scope 3 - Value Chain", color: "#f59e0b", completeness: 78, categories: 12, entries: 892 },
  ];

  const auditEntries = [
    { action: "Data Import", user: "admin@org.com", category: "Electricity", time: "2 hours ago", status: "Verified" },
    { action: "EF Update", user: "analyst@org.com", category: "Natural Gas", time: "1 day ago", status: "Pending" },
    { action: "Calculation", user: "System", category: "All Scopes", time: "1 day ago", status: "Verified" },
    { action: "Export", user: "admin@org.com", category: "Full Report", time: "3 days ago", status: "Verified" },
  ];

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Box>
          <Typography variant="h4" fontWeight={700} color="#111827" gutterBottom>
            Data Quality
          </Typography>
          <Typography variant="body2" color="#6b7280">
            Monitor data completeness, accuracy, and audit readiness
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<Refresh />} sx={{ borderColor: "#e5e7eb", color: "#374151" }}>
          Refresh
        </Button>
      </Box>

      {/* Overall Score */}
      <Box sx={{ mb: 3 }}>
        <OverallScoreCard score={90} breakdown={qualityBreakdown} />
      </Box>

      {/* Metric Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            icon={DataUsage}
            title="Data Entries"
            value="1,096"
            status="Complete"
            description="Across all emission categories"
            color="#3b82f6"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            icon={Calculate}
            title="Estimation Ratio"
            value="23%"
            status="Pending"
            description="Target: <15% for assurance"
            color="#f59e0b"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            icon={LinkIcon}
            title="Source Links"
            value="847"
            status="Verified"
            description="Evidence documents attached"
            color="#16a34a"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <MetricCard
            icon={Schedule}
            title="Data Age"
            value="12 days"
            status="Complete"
            description="Since last data update"
            color="#8b5cf6"
          />
        </Grid>
      </Grid>

      {/* Middle Row */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <DataCoverageChart coverage={coverage} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <ScopeCompletenessCard scopes={scopes} />
        </Grid>
      </Grid>

      {/* Validation Issues */}
      <Box sx={{ mb: 3 }}>
        <ValidationIssuesCard issues={issues} />
      </Box>

      {/* Audit Trail */}
      <AuditTrailCard entries={auditEntries} />

      {/* Audit Ready Banner */}
      <Paper
        elevation={0}
        sx={{
          mt: 3,
          p: 2.5,
          bgcolor: "#f0fdf4",
          border: "1px solid #bbf7d0",
          borderRadius: 2,
          display: "flex",
          alignItems: "center",
          gap: 2,
        }}
      >
        <VerifiedUser sx={{ color: "#16a34a", fontSize: 32 }} />
        <Box sx={{ flex: 1 }}>
          <Typography variant="body1" fontWeight={600} color="#15803d">
            Audit Ready Status: 90%
          </Typography>
          <Typography variant="body2" color="#166534">
            Address 4 outstanding issues to achieve full audit readiness for third-party verification.
          </Typography>
        </Box>
        <Button variant="contained" sx={{ bgcolor: "#16a34a", "&:hover": { bgcolor: "#15803d" } }}>
          View Checklist
        </Button>
      </Paper>
    </Box>
  );
}
