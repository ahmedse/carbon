// src/pages/data-owner/DataOwnerDashboardPage.jsx
// Data owner emissions dashboard - KPI tiles, DQ summary, submission status

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchOwnerDashboard, fetchReportingPeriodsFiltered, fetchOwnerSummary } from '../../api/emissions';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  Paper,
  Stack,
  Chip,
  LinearProgress,
  useTheme,
  Divider,
} from '@mui/material';
import {
  TrendingDown as TrendingDownIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as PassIcon,
  Error as FailIcon,
  TrendingUp as TrendingIcon,
  Cloud as CloudIcon,
} from '@mui/icons-material';
import MetricCard from '../../components/dashboard/MetricCard';



const DataQualitySummary = ({ data: _dqData, theme }) => {
  if (!_dqData) return null;
  const total = (_dqData.passing_count || 0) + (_dqData.warning_count || 0) + (_dqData.failing_count || 0) + (_dqData.unknown_count || 0);
  const _passingPct = total > 0 ? Math.round((_dqData.passing_count / total) * 100) : 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
          Data Quality Summary
        </Typography>
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="caption">Overall Score</Typography>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              {Math.round(_dqData.avg_quality_score || 0)}%
            </Typography>
          </Stack>
          <LinearProgress variant="determinate" value={Math.min(_dqData.avg_quality_score || 0, 100)} sx={{ height: 8, borderRadius: 4, bgcolor: theme.palette.action.disabledBackground, '& .MuiLinearProgress-bar': { bgcolor: theme.palette.success.main } }} />
        </Box>

        <Grid container spacing={1}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: `${theme.palette.success.main}15`, borderLeft: `3px solid ${theme.palette.success.main}` }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: theme.palette.success.dark }}>
                {_dqData.passing_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Passing
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: `${theme.palette.warning.main}15`, borderLeft: `3px solid ${theme.palette.warning.main}` }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: theme.palette.warning.dark }}>
                {_dqData.warning_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Warning
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: `${theme.palette.error.main}15`, borderLeft: `3px solid ${theme.palette.error.main}` }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: theme.palette.error.dark }}>
                {_dqData.failing_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Failing
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: theme.palette.action.disabledBackground, borderLeft: `3px solid ${theme.palette.divider}` }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: theme.palette.text.secondary }}>
                {_dqData.unknown_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Unknown
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

const SubmissionStatusCard = ({ _data, modulesData, theme }) => {
  if (!modulesData) return null;
  const { total = 0, with_data = 0, without_data_names = [] } = modulesData;
  const dataCompleteness = total > 0 ? Math.round((with_data / total) * 100) : 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
          Submission Status
        </Typography>

        <Box sx={{ mb: 3 }}>
          <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="caption">Data Completeness</Typography>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              {dataCompleteness}%
            </Typography>
          </Stack>
          <LinearProgress variant="determinate" value={dataCompleteness} sx={{ height: 8, borderRadius: 4, bgcolor: theme.palette.action.disabledBackground, '& .MuiLinearProgress-bar': { bgcolor: theme.palette.success.main } }} />
        </Box>

        <Paper sx={{ p: 2, bgcolor: `${theme.palette.success.main}15`, borderLeft: `4px solid ${theme.palette.success.main}`, mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <PassIcon sx={{ color: theme.palette.success.main, fontSize: 20 }} />
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.success.dark }}>
                {with_data} of {total} modules with data
              </Typography>
            </Box>
          </Stack>
        </Paper>

        {without_data_names && without_data_names.length > 0 && (
          <Paper sx={{ p: 2, bgcolor: `${theme.palette.warning.main}15`, borderLeft: `4px solid ${theme.palette.warning.main}` }}>
            <Stack direction="row" spacing={1} alignItems="flex-start" sx={{ mb: 1 }}>
              <WarningIcon sx={{ color: theme.palette.warning.main, fontSize: 20, mt: 0.25, flexShrink: 0 }} />
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.warning.dark }}>
                  Missing data:
                </Typography>
                <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                  {without_data_names.join(', ')}
                </Typography>
              </Box>
            </Stack>
          </Paper>
        )}
      </CardContent>
    </Card>
  );
};

export default function DataOwnerDashboardPage() {
  const { user: _ownerUser, context, token } = useAuth();
  const { showNotification } = useNotification();
  const theme = useTheme();

  const [dashboardData, setDashboardData] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState(null);
  const [selectedOrgUnit, setSelectedOrgUnit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);

        // Check org unit scope
        if (!context?.org_units || context.org_units.length === 0) {
          setError('no-scope');
          setLoading(false);
          return;
        }

        // Use first org unit as default
        const defaultOrgUnit = context.org_units[0]?.id;
        setSelectedOrgUnit(defaultOrgUnit);

        // Load reporting periods
        try {
          const perRes = await fetchReportingPeriodsFiltered(token, 'open');
          const periodsList = Array.isArray(perRes) ? perRes : perRes.results || [];
          setPeriods(periodsList);
          if (periodsList.length > 0) {
            setSelectedPeriod(periodsList[0].id);
          }
        } catch (e) {
          console.warn('Could not load periods:', e);
        }

        // Load dashboard data
        const [dashRes, summaryRes] = await Promise.all([
          fetchOwnerDashboard(token, defaultOrgUnit, selectedPeriod),
          fetchOwnerSummary(token),
        ]);

        setDashboardData({
          ...dashRes,
          summary: summaryRes?.summary || null,
          org_unit: dashRes?.org_unit || summaryRes?.org_unit || null,
        });
        setError(null);
      } catch (err) {
        console.error('Error loading dashboard:', err);
        setError('load-failed');
        showNotification({
          message: 'Failed to load dashboard data',
          type: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    if (token && context) {
      loadData();
    }
  }, [token, context, showNotification]);

  // Reload when period changes
  useEffect(() => {
    if (selectedPeriod && selectedOrgUnit && token) {
      const loadData = async () => {
        try {
          const dashRes = await fetchOwnerDashboard(token, selectedOrgUnit, selectedPeriod);
          setDashboardData(dashRes);
        } catch (err) {
          console.error('Error reloading dashboard:', err);
        }
      };
      loadData();
    }
  }, [selectedPeriod, selectedOrgUnit, token]);

  if (loading) {
    return (
      <Container>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error === 'no-scope') {
    return (
      <Container>
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Alert severity="info">No data scope assigned. Contact your administrator.</Alert>
        </Box>
      </Container>
    );
  }

  const emissions = dashboardData?.emissions || {};
  const dq = dashboardData?.data_quality || {};
  const _orgUnit = dashboardData?.org_unit || context?.org_units[0];

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 4 } }}>
      {/* Header with Selectors */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>
          My Emissions Dashboard
        </Typography>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Reporting Period</InputLabel>
              <Select
                value={selectedPeriod || ''}
                onChange={(e) => setSelectedPeriod(e.target.value)}
                label="Reporting Period"
              >
                {periods.map(p => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.name} ({p.start_date} - {p.end_date})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Organization Unit</InputLabel>
              <Select
                value={selectedOrgUnit || ''}
                onChange={(e) => setSelectedOrgUnit(e.target.value)}
                label="Organization Unit"
              >
                {context?.org_units?.map(ou => (
                  <MenuItem key={ou.id} value={ou.id}>
                    {ou.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Box>

      {/* Emissions KPI Tiles */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
        Total Emissions
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Total CO2e"
            value={emissions.total_co2e_tonne?.toLocaleString('en-US', { maximumFractionDigits: 1 }) || '0'}
            target="tonnes"
            icon={<CloudIcon sx={{ fontSize: 28 }} />}
            change={emissions.change_pct ? `${Math.abs(emissions.change_pct)}%` : undefined}
            changeColor={emissions.change_pct < 0 ? 'success' : 'error'}
            barColor={theme.palette.info.main}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Scope 1 - Direct"
            value={emissions.scope1_co2e_tonne?.toLocaleString('en-US', { maximumFractionDigits: 1 }) || '0'}
            target="tonnes"
            barColor={theme.palette.error.main}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Scope 2 - Energy"
            value={emissions.scope2_co2e_tonne?.toLocaleString('en-US', { maximumFractionDigits: 1 }) || '0'}
            target="tonnes"
            barColor={theme.palette.warning.main}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Scope 3 - Value Chain"
            value={emissions.scope3_co2e_tonne?.toLocaleString('en-US', { maximumFractionDigits: 1 }) || '0'}
            target="tonnes"
            barColor={theme.palette.secondary.main}
          />
        </Grid>
      </Grid>

      {/* DQ & Submission */}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
        Data Quality & Submission
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <DataQualitySummary data={dq} theme={theme} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <SubmissionStatusCard data={dashboardData} modulesData={dashboardData?.modules} theme={theme} />
        </Grid>
      </Grid>
    </Container>
  );
}
