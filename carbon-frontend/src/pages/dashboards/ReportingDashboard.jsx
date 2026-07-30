// File: src/pages/dashboards/ReportingDashboard.jsx
// Reporting Dashboard - Compliance frameworks and report generation

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
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Divider,
  IconButton,
  Tooltip,
  Tab,
  Tabs,
} from "@mui/material";
import {
  CheckCircle,
  Warning,
  ErrorOutline,
  Description,
  Download,
  Visibility,
  CalendarToday,
  Business,
  Gavel,
  Public,
  Assessment,
  Timeline,
  Schedule,
  PlayArrow,
  CloudDownload,
  ArticleOutlined,
  FactCheck,
} from "@mui/icons-material";
import { useDashboardData } from "../../components/dashboard/useDashboardData";
import { useAuth } from "../../auth/AuthContext";

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

// ============ Framework Data ============

const FRAMEWORKS = [
  {
    id: "ghg",
    name: "GHG Protocol",
    fullName: "Greenhouse Gas Protocol Corporate Standard",
    icon: Public,
    color: "#16a34a",
    status: "compliant",
    readiness: 100,
    lastReport: "Dec 2025",
    nextDue: "Dec 2026",
    description: "Foundation standard for corporate GHG accounting",
  },
  {
    id: "cdp",
    name: "CDP",
    fullName: "Carbon Disclosure Project",
    icon: Assessment,
    color: "#3b82f6",
    status: "in-progress",
    readiness: 85,
    lastReport: "Jul 2025",
    nextDue: "Jul 2026",
    description: "Global environmental disclosure platform",
  },
  {
    id: "csrd",
    name: "CSRD/ESRS",
    fullName: "Corporate Sustainability Reporting Directive",
    icon: Gavel,
    color: "#8b5cf6",
    status: "in-progress",
    readiness: 72,
    lastReport: "N/A",
    nextDue: "Jan 2027",
    description: "EU mandatory sustainability reporting",
  },
  {
    id: "tcfd",
    name: "TCFD",
    fullName: "Task Force on Climate-related Financial Disclosures",
    icon: Business,
    color: "#f59e0b",
    status: "partial",
    readiness: 65,
    lastReport: "Mar 2025",
    nextDue: "Mar 2026",
    description: "Climate risk and opportunity disclosure",
  },
  {
    id: "gri",
    name: "GRI Standards",
    fullName: "Global Reporting Initiative",
    icon: ArticleOutlined,
    color: "#06b6d4",
    status: "compliant",
    readiness: 95,
    lastReport: "Jun 2025",
    nextDue: "Jun 2026",
    description: "Comprehensive sustainability reporting",
  },
];

// ============ Framework Card Component ============

const FrameworkCard = ({ framework, onSelect, selected }) => {
  const Icon = framework.icon;
  
  const getStatusChip = (status) => {
    switch (status) {
      case "compliant":
        return { label: "Compliant", color: "#16a34a", bg: "#d1fae5", icon: <CheckCircle fontSize="small" /> };
      case "in-progress":
        return { label: "In Progress", color: "#3b82f6", bg: "#dbeafe", icon: <Schedule fontSize="small" /> };
      case "partial":
        return { label: "Partial", color: "#f59e0b", bg: "#fef3c7", icon: <Warning fontSize="small" /> };
      default:
        return { label: "Not Started", color: "#6b7280", bg: "#f3f4f6", icon: <ErrorOutline fontSize="small" /> };
    }
  };

  const statusInfo = getStatusChip(framework.status);

  return (
    <GlassCard
      sx={{
        height: "100%",
        cursor: "pointer",
        border: selected ? `2px solid ${framework.color}` : "1px solid rgba(0,0,0,0.06)",
        "&:hover": {
          borderColor: framework.color,
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
        },
      }}
      onClick={() => onSelect(framework.id)}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 2 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: `${framework.color}15`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon sx={{ color: framework.color, fontSize: 26 }} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle1" fontWeight={700} color="#111827">
              {framework.name}
            </Typography>
            <Typography variant="caption" color="#6b7280" display="block" sx={{ mb: 1 }}>
              {framework.description}
            </Typography>
            <Chip
              size="small"
              icon={statusInfo.icon}
              label={statusInfo.label}
              sx={{
                bgcolor: statusInfo.bg,
                color: statusInfo.color,
                fontWeight: 600,
                "& .MuiChip-icon": { color: "inherit" },
              }}
            />
          </Box>
        </Box>

        <Box sx={{ mt: 2 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
            <Typography variant="caption" color="#6b7280">
              Readiness
            </Typography>
            <Typography variant="caption" fontWeight={600} color="#111827">
              {framework.readiness}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={framework.readiness}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: "#e5e7eb",
              "& .MuiLinearProgress-bar": {
                borderRadius: 3,
                bgcolor: framework.color,
              },
            }}
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        <Grid container spacing={1}>
          <Grid size={{ xs: 6 }}>
            <Typography variant="caption" color="#9ca3af" display="block">
              Last Report
            </Typography>
            <Typography variant="body2" fontWeight={500} color="#374151">
              {framework.lastReport}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }}>
            <Typography variant="caption" color="#9ca3af" display="block">
              Next Due
            </Typography>
            <Typography variant="body2" fontWeight={500} color="#374151">
              {framework.nextDue}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </GlassCard>
  );
};

// ============ Framework Detail Panel ============

const FrameworkDetailPanel = ({ framework }) => {
  const Icon = framework.icon;
  
  const requirements = [
    { name: "Scope 1 Emissions", status: "complete", notes: "All categories covered" },
    { name: "Scope 2 Emissions", status: "complete", notes: "Market & location-based" },
    { name: "Scope 3 Categories", status: "partial", notes: "8 of 15 categories complete" },
    { name: "Emission Factors", status: "complete", notes: "Using latest regional factors" },
    { name: "Methodology Documentation", status: "complete", notes: "GHG Protocol aligned" },
    { name: "Third-party Verification", status: "pending", notes: "Scheduled for Q2 2026" },
    { name: "Historical Data (3 years)", status: "complete", notes: "2023-2025 available" },
  ];

  const getStatusIcon = (status) => {
    switch (status) {
      case "complete":
        return <CheckCircle sx={{ color: "#16a34a", fontSize: 18 }} />;
      case "partial":
        return <Warning sx={{ color: "#f59e0b", fontSize: 18 }} />;
      case "pending":
        return <Schedule sx={{ color: "#3b82f6", fontSize: 18 }} />;
      default:
        return <ErrorOutline sx={{ color: "#dc2626", fontSize: 18 }} />;
    }
  };

  return (
    <GlassCard sx={{ height: "100%" }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 3 }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: 2,
              bgcolor: `${framework.color}15`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon sx={{ color: framework.color, fontSize: 30 }} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" fontWeight={700} color="#111827">
              {framework.fullName}
            </Typography>
            <Typography variant="body2" color="#6b7280">
              {framework.description}
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            sx={{
              bgcolor: framework.color,
              "&:hover": { bgcolor: framework.color, filter: "brightness(0.9)" },
            }}
          >
            Generate Report
          </Button>
        </Box>

        <Typography variant="subtitle2" fontWeight={600} color="#374151" sx={{ mb: 2 }}>
          Requirements Checklist
        </Typography>

        <Stack spacing={1}>
          {requirements.map((req, idx) => (
            <Paper
              key={idx}
              elevation={0}
              sx={{
                p: 1.5,
                borderRadius: 2,
                bgcolor:
                  req.status === "complete"
                    ? "#f0fdf4"
                    : req.status === "partial"
                    ? "#fffbeb"
                    : req.status === "pending"
                    ? "#eff6ff"
                    : "#fef2f2",
                border: `1px solid ${
                  req.status === "complete"
                    ? "#bbf7d0"
                    : req.status === "partial"
                    ? "#fde68a"
                    : req.status === "pending"
                    ? "#bfdbfe"
                    : "#fecaca"
                }`,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                {getStatusIcon(req.status)}
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" fontWeight={500} color="#111827">
                    {req.name}
                  </Typography>
                  <Typography variant="caption" color="#6b7280">
                    {req.notes}
                  </Typography>
                </Box>
                {req.status !== "complete" && (
                  <Button size="small" sx={{ minWidth: "auto" }}>
                    Complete
                  </Button>
                )}
              </Box>
            </Paper>
          ))}
        </Stack>

        <Divider sx={{ my: 3 }} />

        <Box sx={{ display: "flex", gap: 2 }}>
          <Button variant="outlined" startIcon={<Visibility />} fullWidth>
            Preview Report
          </Button>
          <Button variant="outlined" startIcon={<CloudDownload />} fullWidth>
            Download Template
          </Button>
        </Box>
      </CardContent>
    </GlassCard>
  );
};

// ============ Recent Reports Component ============

const RecentReportsCard = ({ reports }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
        Recent Reports
      </Typography>

      <Stack spacing={1.5}>
        {reports.map((report, idx) => (
          <Paper
            key={idx}
            elevation={0}
            sx={{
              p: 2,
              borderRadius: 2,
              bgcolor: "#f9fafb",
              border: "1px solid #e5e7eb",
              display: "flex",
              alignItems: "center",
              gap: 2,
            }}
          >
            <Description sx={{ color: "#6b7280" }} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" fontWeight={600} color="#111827">
                {report.name}
              </Typography>
              <Typography variant="caption" color="#6b7280">
                {report.framework} • {report.date} • {report.size}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              <Tooltip title="View">
                <IconButton size="small">
                  <Visibility fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Download">
                <IconButton size="small">
                  <Download fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </CardContent>
  </GlassCard>
);

// ============ Reporting Calendar Component ============

const ReportingCalendarCard = ({ deadlines }) => (
  <GlassCard sx={{ height: "100%" }}>
    <CardContent sx={{ p: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} color="#111827" sx={{ mb: 2 }}>
        Upcoming Deadlines
      </Typography>

      <Stack spacing={1.5}>
        {deadlines.map((deadline, idx) => {
          const daysUntil = Math.ceil(
            (new Date(deadline.date) - new Date()) / (1000 * 60 * 60 * 24)
          );
          const isUrgent = daysUntil <= 30;
          const isWarning = daysUntil <= 60;

          return (
            <Paper
              key={idx}
              elevation={0}
              sx={{
                p: 2,
                borderRadius: 2,
                bgcolor: isUrgent ? "#fef2f2" : isWarning ? "#fffbeb" : "#f9fafb",
                border: `1px solid ${isUrgent ? "#fecaca" : isWarning ? "#fde68a" : "#e5e7eb"}`,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                <Box
                  sx={{
                    width: 44,
                    height: 44,
                    borderRadius: 2,
                    bgcolor: isUrgent ? "#fee2e2" : isWarning ? "#fef3c7" : "#f3f4f6",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Typography variant="caption" fontWeight={700} color={isUrgent ? "#dc2626" : isWarning ? "#d97706" : "#374151"}>
                    {new Date(deadline.date).toLocaleDateString("en", { month: "short" })}
                  </Typography>
                  <Typography variant="body2" fontWeight={700} color={isUrgent ? "#dc2626" : isWarning ? "#d97706" : "#374151"}>
                    {new Date(deadline.date).getDate()}
                  </Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" fontWeight={600} color="#111827">
                    {deadline.name}
                  </Typography>
                  <Typography variant="caption" color="#6b7280">
                    {deadline.framework} • {daysUntil} days remaining
                  </Typography>
                </Box>
                <Chip
                  size="small"
                  label={isUrgent ? "Urgent" : isWarning ? "Upcoming" : "Scheduled"}
                  sx={{
                    bgcolor: isUrgent ? "#fee2e2" : isWarning ? "#fef3c7" : "#f3f4f6",
                    color: isUrgent ? "#dc2626" : isWarning ? "#d97706" : "#374151",
                    fontWeight: 600,
                  }}
                />
              </Box>
            </Paper>
          );
        })}
      </Stack>
    </CardContent>
  </GlassCard>
);

// ============ Main Component ============

export default function ReportingDashboard() {
  const { user, context } = useAuth();
  const { _data, loading, error } = useDashboardData(context?.projectId, user?.token);
  const [selectedFramework, setSelectedFramework] = useState("cdp");
  const [reportingPeriod, setReportingPeriod] = useState("2025");

  if (loading) {
    return (
      <Box sx={{ p: 4 }}>
        <Skeleton variant="rectangular" height={60} sx={{ borderRadius: 2, mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Grid size={{ xs: 12, md: 4, lg: 2.4 }} key={i}>
              <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 3 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">Failed to load reporting data: {error}</Alert>
      </Box>
    );
  }

  const selectedFw = FRAMEWORKS.find((f) => f.id === selectedFramework);

  const recentReports = [
    { name: "2025 GHG Inventory Report", framework: "GHG Protocol", date: "Dec 15, 2025", size: "2.4 MB" },
    { name: "CDP Climate Response 2025", framework: "CDP", date: "Jul 31, 2025", size: "1.8 MB" },
    { name: "GRI Sustainability Report", framework: "GRI", date: "Jun 30, 2025", size: "5.2 MB" },
  ];

  const deadlines = [
    { name: "CDP Climate Questionnaire", framework: "CDP", date: "2026-07-31" },
    { name: "TCFD Annual Disclosure", framework: "TCFD", date: "2026-03-31" },
    { name: "GRI Sustainability Report", framework: "GRI", date: "2026-06-30" },
    { name: "CSRD First Submission", framework: "CSRD", date: "2027-01-31" },
  ];

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Box>
          <Typography variant="h4" fontWeight={700} color="#111827" gutterBottom>
            Reporting
          </Typography>
          <Typography variant="body2" color="#6b7280">
            Manage compliance with global sustainability reporting frameworks
          </Typography>
        </Box>

        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Reporting Period</InputLabel>
          <Select
            value={reportingPeriod}
            label="Reporting Period"
            onChange={(e) => setReportingPeriod(e.target.value)}
          >
            <MenuItem value="2026">FY 2026</MenuItem>
            <MenuItem value="2025">FY 2025</MenuItem>
            <MenuItem value="2024">FY 2024</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Framework Cards */}
      <Typography variant="subtitle2" fontWeight={600} color="#374151" sx={{ mb: 2 }}>
        Reporting Frameworks
      </Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {FRAMEWORKS.map((framework) => (
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 2.4 }} key={framework.id}>
            <FrameworkCard
              framework={framework}
              selected={selectedFramework === framework.id}
              onSelect={setSelectedFramework}
            />
          </Grid>
        ))}
      </Grid>

      {/* Framework Detail */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, lg: 8 }}>
          <FrameworkDetailPanel framework={selectedFw} />
        </Grid>
        <Grid size={{ xs: 12, lg: 4 }}>
          <Stack spacing={3}>
            <RecentReportsCard reports={recentReports} />
          </Stack>
        </Grid>
      </Grid>

      {/* Deadlines */}
      <ReportingCalendarCard deadlines={deadlines} />

      {/* Quick Actions Footer */}
      <Paper
        elevation={0}
        sx={{
          mt: 3,
          p: 2.5,
          bgcolor: "#f9fafb",
          border: "1px solid #e5e7eb",
          borderRadius: 2,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <FactCheck sx={{ color: "#6b7280" }} />
            <Typography variant="body2" color="#374151">
              <strong>Quick Actions:</strong>
            </Typography>
          </Box>
          <Button size="small" startIcon={<Description />}>
            Generate All Reports
          </Button>
          <Button size="small" startIcon={<Download />}>
            Export Data Package
          </Button>
          <Button size="small" startIcon={<CalendarToday />}>
            Schedule Reports
          </Button>
          <Button size="small" startIcon={<Assessment />}>
            Gap Analysis
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
