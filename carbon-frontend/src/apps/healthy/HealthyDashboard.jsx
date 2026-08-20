// src/apps/healthy/HealthyDashboard.jsx
// Healthy Foods Factory — overview dashboard (pipeline status + summary KPIs).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Chip, Grid, Paper, Stack, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import DashboardIcon from '@mui/icons-material/Dashboard';
import InsightsIcon from '@mui/icons-material/Insights';
import PeopleIcon from '@mui/icons-material/People';
import StorageIcon from '@mui/icons-material/Storage';
import TableChartIcon from '@mui/icons-material/TableChart';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import StatCard from '../../components/Cards/StatCard';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchHealthySummary } from '../../api/healthy';

// The five Healthy pipelines (keys mirror the backend PIPELINES map).
const PIPELINES = [
  { key: 'returns', name: 'Returns / load-out demand', outcome: 'Forecast ready', path: '/apps/healthy/loadout' },
  { key: 'churn', name: 'Rep retention & churn', outcome: 'Forecast ready', path: '/apps/healthy/reps' },
  { key: 'sales-lines', name: 'Demand & dead-stock', outcome: 'Alerts available', path: '/apps/healthy/inventory' },
  { key: 'ar-aging', name: 'AR collections', outcome: 'Queue ready', path: '/apps/healthy/collections' },
  { key: 'transaction-classifier', name: 'Transaction data integrity', outcome: 'Protected', path: null },
];

export default function HealthyDashboard() {
  useDocumentTitle('Healthy Foods Factory');
  const navigate = useNavigate();
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchHealthySummary(token)
      .then((data) => setSummary(data))
      .catch((err) => setError(err?.message || 'Unable to load the Healthy dashboard.'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const pipelines = summary?.pipelines && typeof summary.pipelines === 'object' ? summary.pipelines : {};

  const kpis = useMemo(
    () => [
      { title: 'Data pipelines', value: Object.keys(pipelines).length, color: 'primary', icon: <DashboardIcon /> },
      { title: 'Snapshots complete', value: summary?.snapshots_done ?? 0, color: 'success', icon: <CheckCircleOutlineIcon /> },
      { title: 'Forecasts ready', value: summary?.predictions ?? 0, color: 'info', icon: <InsightsIcon /> },
      { title: 'Loadout sheets', value: summary?.loadout_sheets ?? 0, color: 'warning', icon: <TableChartIcon /> },
      { title: 'Rep health cards', value: summary?.rep_health_cards ?? 0, color: 'primary', icon: <PeopleIcon /> },
      { title: 'Dataset versions', value: summary?.dataset_versions ?? 0, color: 'success', icon: <StorageIcon /> },
    ],
    [pipelines, summary],
  );

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={DashboardIcon} title="Healthy Foods Factory" subtitle="Operational health overview" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={DashboardIcon} title="Healthy Foods Factory" subtitle="Operational health overview" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  if (!summary) {
    return (
      <PageContainer>
        <PageHeader icon={DashboardIcon} title="Healthy Foods Factory" subtitle="Operational health overview" />
        <EmptyState
          icon={<DashboardIcon />}
          title="No dashboard data yet"
          description="Once Healthy pipelines complete their first run, operational health metrics will appear here."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={DashboardIcon}
        title="Healthy Foods Factory"
        subtitle="Operational health overview"
        description="A single view of forecast, collections, and inventory health across the Healthy Foods operation."
      />

      <Stack spacing={2}>
        <Grid container spacing={2}>
          {kpis.map((kpi) => (
            <Grid key={kpi.title} size={{ xs: 12, sm: 6, md: 4 }}>
              <StatCard title={kpi.title} value={kpi.value} icon={kpi.icon} color={kpi.color} />
            </Grid>
          ))}
        </Grid>

        <Box>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>Pipelines</Typography>
          <Stack spacing={1}>
            {PIPELINES.map((pipeline) => {
              const count = pipelines[pipeline.key] ?? 0;
              const ready = count > 0;
              return (
                <Paper
                  key={pipeline.key}
                  variant="outlined"
                  sx={{ p: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{pipeline.name}</Typography>
                    <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
                      {ready ? `${count} snapshot${count === 1 ? '' : 's'} completed` : 'No snapshots yet'}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={ready ? pipeline.outcome : 'Awaiting data'}
                    color={ready ? 'success' : 'default'}
                    variant="outlined"
                  />
                  {pipeline.path && (
                    <Button
                      size="small"
                      endIcon={<ArrowForwardIcon />}
                      onClick={() => navigate(pipeline.path)}
                      sx={{ whiteSpace: 'nowrap' }}
                    >
                      Open
                    </Button>
                  )}
                </Paper>
              );
            })}
          </Stack>
        </Box>
      </Stack>
    </PageContainer>
  );
}
