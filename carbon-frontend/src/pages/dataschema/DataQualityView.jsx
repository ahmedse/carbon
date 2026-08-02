// File: src/pages/dataschema/DataQualityView.jsx
// Data Quality view within Data Hub context (module-scoped version)

import React, { useState, useMemo } from "react";
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
  Tabs,
  Tab,
} from "@mui/material";
import useDocumentTitle from '../../hooks/useDocumentTitle';

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

const MetricCard = ({ icon: _Icon, title, value, subtitle, color, trend, loading }) => (
  <GlassCard>
    <CardContent>
      <Box display="flex" alignItems="flex-start" justifyContent="space-between" mb={1}>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: `linear-gradient(135deg, ${color}15 0%, ${color}05 100%)`,
            color: color,
          }}
        >
          <_Icon sx={{ fontSize: 24 }} />
        </Box>
        {trend && (
          <Chip
            size="small"
            label={trend > 0 ? `+${trend}%` : `${trend}%`}
            color={trend > 0 ? "success" : "error"}
            sx={{ fontWeight: 600, fontSize: "0.75rem" }}
          />
        )}
      </Box>
      <Typography variant="h4" fontWeight={700} mb={0.5}>
        {loading ? <Skeleton width={80} /> : value}
      </Typography>
      <Typography variant="body2" color="text.secondary" fontWeight={600} mb={0.5}>
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="caption" color="text.secondary">
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </GlassCard>
);

// ============ Main Component ============

export default function DataQualityView() {
  useDocumentTitle("Data Quality");
  const { context, availablePerspectives } = useAuth();
  const { data, loading, error, refreshData } = useDashboardData();
  const isAdmin = availablePerspectives?.includes("admin");
  
  const [_expandedModule, _setExpandedModule] = useState(null);
  const [scopeFilter, setScopeFilter] = useState("all");

  // Filter modules by user's context and scope
  const userModules = useMemo(() => {
    const modules = context?.modules || [];
    if (scopeFilter === "all") return modules;
    return modules.filter(m => String(m.scope || 1) === scopeFilter);
  }, [context, scopeFilter]);

  // Count modules per scope
  const scopeCounts = useMemo(() => {
    const counts = { 1: 0, 2: 0, 3: 0 };
    (context?.modules || []).forEach(m => {
      const s = m.scope || 1;
      if (counts[s] !== undefined) counts[s]++;
    });
    return counts;
  }, [context]);

  // Calculate aggregate metrics for user's modules
  const metrics = useMemo(() => {
    if (!data?.dataQuality || !userModules.length) {
      return {
        totalRows: 0,
        completeness: 0,
        validationScore: 0,
        evidenceRate: 0,
        auditReadiness: 0,
      };
    }

    // Aggregate from user's modules only
    const moduleIds = new Set(userModules.map(m => String(m.id)));
    const moduleData = data.dataQuality.modules?.filter(m => moduleIds.has(String(m.id))) || [];
    
    const totalRows = moduleData.reduce((sum, m) => sum + (m.totalRows || 0), 0);
    const totalScore = moduleData.reduce((sum, m) => sum + ((m.completeness || 0) * (m.totalRows || 0)), 0);
    const completeness = totalRows > 0 ? (totalScore / totalRows) : 0;
    
    return {
      totalRows,
      completeness: Math.round(completeness),
      validationScore: data.dataQuality.validationScore || 0,
      evidenceRate: data.dataQuality.evidenceRate || 0,
      auditReadiness: data.dataQuality.auditReadiness || 0,
    };
  }, [data, userModules]);

  if (error) {
    return (
      <Box p={3}>
        <Alert severity="error">
          Failed to load data quality metrics. {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box p={3}>
      {/* Header */}
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Data Quality
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Track completeness, validation, and audit readiness for your modules
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={refreshData}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Scope filter tabs */}
      {userModules.length > 1 && (
        <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}>
          <Tabs value={scopeFilter} onChange={(_, val) => setScopeFilter(val)}>
            <Tab value="all" label={`All (${userModules.length})`} />
            {scopeCounts[1] > 0 && <Tab value="1" label={`Scope 1 (${scopeCounts[1]})`} />}
            {scopeCounts[2] > 0 && <Tab value="2" label={`Scope 2 (${scopeCounts[2]})`} />}
            {scopeCounts[3] > 0 && <Tab value="3" label={`Scope 3 (${scopeCounts[3]})`} />}
          </Tabs>
        </Box>
      )}

      {/* Key Metrics */}
      <Grid container spacing={2} mb={4}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            icon={DataUsage}
            title="Data Completeness"
            value={`${metrics.completeness}%`}
            subtitle={`${metrics.totalRows} total rows`}
            color="#10b981"
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            icon={PlaylistAddCheck}
            title="Validation Score"
            value={`${metrics.validationScore}%`}
            subtitle="Rules passed"
            color="#3b82f6"
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            icon={Description}
            title="Evidence Rate"
            value={`${metrics.evidenceRate}%`}
            subtitle="With attachments"
            color="#f59e0b"
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            icon={VerifiedUser}
            title="Audit Readiness"
            value={`${metrics.auditReadiness}%`}
            subtitle="Overall score"
            color="#8b5cf6"
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Module Breakdown */}
      <GlassCard>
        <CardContent>
          <Typography variant="h6" fontWeight={600} gutterBottom>
            Module Quality Breakdown
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Detailed quality metrics for each module
          </Typography>

          {loading ? (
            <Stack spacing={2}>
              <Skeleton variant="rectangular" height={60} />
              <Skeleton variant="rectangular" height={60} />
              <Skeleton variant="rectangular" height={60} />
            </Stack>
          ) : userModules.length === 0 ? (
            <Alert severity="info">No modules assigned to your account.</Alert>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Module</TableCell>
                    <TableCell>Scope</TableCell>
                    <TableCell align="right">Rows</TableCell>
                    <TableCell align="right">Completeness</TableCell>
                    <TableCell align="right">Evidence</TableCell>
                    <TableCell align="right">Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {userModules.map((module) => {
                    const moduleMetrics = data?.dataQuality?.modules?.find(
                      m => String(m.id) === String(module.id)
                    ) || {};
                    
                    const completeness = moduleMetrics.completeness || 0;
                    const evidenceRate = moduleMetrics.evidenceRate || 0;
                    const status = completeness >= 90 ? "ready" : completeness >= 70 ? "warning" : "error";
                    
                    return (
                      <TableRow key={module.id}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600}>
                            {module.name}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={`Scope ${module.scope || 1}`}
                            size="small"
                            sx={{ fontSize: "0.7rem" }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          {moduleMetrics.totalRows || 0}
                        </TableCell>
                        <TableCell align="right">
                          <Box display="flex" alignItems="center" justifyContent="flex-end" gap={1}>
                            <LinearProgress
                              variant="determinate"
                              value={completeness}
                              sx={{ width: 60, height: 6, borderRadius: 3 }}
                            />
                            <Typography variant="caption" fontWeight={600}>
                              {completeness}%
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell align="right">
                          {evidenceRate}%
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            size="small"
                            label={status === "ready" ? "Ready" : status === "warning" ? "Review" : "Action Needed"}
                            color={status === "ready" ? "success" : status === "warning" ? "warning" : "error"}
                            icon={
                              status === "ready" ? <CheckCircle /> :
                              status === "warning" ? <Warning /> :
                              <ErrorOutline />
                            }
                          />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </GlassCard>

      {/* Admin note */}
      {isAdmin && (
        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Admin view:</strong> You're seeing quality metrics for all modules you have access to.
            For organization-wide quality reports, visit the{" "}
            <a href="/dashboards/data-quality">Executive Data Quality Dashboard</a>.
          </Typography>
        </Alert>
      )}
    </Box>
  );
}
