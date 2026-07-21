import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Grid, Card, CardContent, Typography, Button, Chip, CircularProgress, Alert, Stack, Tooltip } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { DataGrid } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { getOrgDQMetrics, getDQResults, executeDQRule } from '../../api/dq';

function MetricCard({ label, value, suffix, status, color }) {
  return (
    <Card sx={{ height: '100%', borderRadius: 2, boxShadow: 'none', border: '1px solid', borderColor: 'divider' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
          {label}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1 }}>
          <Typography variant="h4" fontWeight={700} color="text.primary">
            {value}
          </Typography>
          {suffix && (
            <Typography variant="subtitle2" color="text.secondary">
              {suffix}
            </Typography>
          )}
        </Box>
        {status && (
          <Chip
            label={status}
            size="small"
            sx={{ mt: 2, bgcolor: `${color}20`, color, fontWeight: 600 }}
          />
        )}
      </CardContent>
    </Card>
  );
}

function getQualityStatus(score) {
  if (score >= 95) return { label: 'Excellent', color: '#16a34a' };
  if (score >= 80) return { label: 'Good', color: '#0288d1' };
  if (score >= 60) return { label: 'Fair', color: '#f59e0b' };
  return { label: 'Needs Improvement', color: '#d32f2f' };
}

function statusLabel(result) {
  if (result?.passed !== undefined) {
    return result.passed ? 'Passed' : 'Failed';
  }
  if (typeof result?.status === 'string') {
    return result.status;
  }
  return 'Unknown';
}

export default function DQDashboardPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { notify } = useNotification();

  const [metrics, setMetrics] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [executingRuleIds, setExecutingRuleIds] = useState([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [metricsData, resultsData] = await Promise.all([
        getOrgDQMetrics(token),
        getDQResults({ limit: 50, ordering: '-executed_at' }, token),
      ]);
      setMetrics(metricsData || null);
      setResults(Array.isArray(resultsData) ? resultsData : resultsData?.results || []);
    } catch (err) {
      const message = err.message || 'Unable to load DQ dashboard data';
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  useEffect(() => {
    if (!token) return;
    loadData();
  }, [token, loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleExecuteRule = async (ruleId) => {
    if (!ruleId) return;
    setExecutingRuleIds((prev) => [...prev, ruleId]);
    try {
      await executeDQRule(token, ruleId);
      notify({ message: 'Rule execution started successfully', type: 'success' });
      await loadData();
    } catch (err) {
      notify({ message: err.message || 'Unable to execute rule', type: 'error' });
    } finally {
      setExecutingRuleIds((prev) => prev.filter((id) => id !== ruleId));
    }
  };

  const rows = useMemo(() => results || [], [results]);

  const columns = [
    {
      field: 'rule_name',
      headerName: 'Rule',
      flex: 1.3,
      minWidth: 190,
      sortable: true,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {params.value || params.row.name || '—'}
        </Typography>
      ),
    },
    {
      field: 'table_name',
      headerName: 'Table',
      flex: 1,
      minWidth: 160,
      sortable: true,
      renderCell: (params) => (
        <Typography variant="body2">{params.value || params.row.data_table_name || '—'}</Typography>
      ),
    },
    {
      field: 'executed_at',
      headerName: 'Executed At',
      width: 180,
      sortable: true,
      valueGetter: (value, row) => value || row.created_at || row.updated_at,
      renderCell: (params) => (
        <Typography variant="body2">{params.value ? new Date(params.value).toLocaleString() : '—'}</Typography>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      sortable: true,
      renderCell: (params) => {
        const result = statusLabel(params.row);
        const passed = params.row.passed === true || result.toLowerCase() === 'passed';
        return (
          <Chip
            label={result}
            size="small"
            color={passed ? 'success' : 'error'}
            variant="outlined"
          />
        );
      },
    },
    {
      field: 'failed_rows',
      headerName: 'Failed Rows',
      width: 120,
      sortable: true,
      renderCell: (params) => <Typography variant="body2">{params.value ?? params.row.row_failure_count ?? '—'}</Typography>,
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 170,
      sortable: false,
      renderCell: (params) => {
        const ruleId = params.row.rule || params.row.rule_id || params.row.dq_rule_id;
        const executing = executingRuleIds.includes(ruleId);
        return (
          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              size="small"
              variant="outlined"
              disabled={!ruleId || executing}
              onClick={() => handleExecuteRule(ruleId)}
              startIcon={<PlayArrowIcon />}
            >
              {executing ? 'Running' : 'Run'}
            </Button>
            <Tooltip title="View rule">
              <Button
                size="small"
                variant="text"
                onClick={() => {
                  if (ruleId) {
                    navigate(`/catalog/dq-rules?rule=${ruleId}`);
                  }
                }}
              >
                View
              </Button>
            </Tooltip>
          </Stack>
        );
      },
    },
  ];

  const summary = {
    qualityScore: metrics?.quality_score ?? metrics?.overall_score ?? metrics?.score ?? 0,
    rulesPassing: metrics?.rules_passing ?? metrics?.rules_passed ?? metrics?.passing_rules ?? 0,
    rulesTotal: metrics?.rules_total ?? metrics?.rule_count ?? metrics?.active_rules ?? 0,
    tablesProfiled: metrics?.tables_profiled ?? metrics?.table_count ?? metrics?.tables_monitored ?? 0,
    failedChecks: metrics?.failed_checks ?? metrics?.failed_rules ?? metrics?.failed_count ?? 0,
  };

  const scoreStatus = getQualityStatus(Number(summary.qualityScore));

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Box sx={{ mb: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-between', gap: 2 }}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Data Quality Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Organization-level data quality metrics and recent validation results.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing || loading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            label="Quality Score"
            value={summary.qualityScore}
            suffix="/100"
            status={scoreStatus.label}
            color={scoreStatus.color}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            label="Rules Passing"
            value={`${summary.rulesPassing}/${summary.rulesTotal}`}
            status="Live"
            color="#0288d1"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            label="Tables Profiled"
            value={summary.tablesProfiled}
            status="Tracked"
            color="#16a34a"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            label="Failed Checks"
            value={summary.failedChecks}
            status="Action needed"
            color="#d32f2f"
          />
        </Grid>
      </Grid>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexDirection: { xs: 'column', sm: 'row' }, gap: 1 }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>
                Recent Data Quality Results
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Showing the latest rule evaluations across your catalog.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <Tooltip title="Create or update DQ rules in Rule Management">
                <Button variant="contained" onClick={() => navigate('/catalog/dq-rules')}>
                  Go to DQ Rules
                </Button>
              </Tooltip>
            </Stack>
          </Box>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box sx={{ width: '100%' }}>
              <div style={{ width: '100%' }}>
                <DataGrid
                  rows={rows}
                  columns={columns}
                  getRowId={(row) => row.id ?? `${row.rule || row.rule_id || row.table_name}-${row.executed_at}`}
                  autoHeight
                  pageSizeOptions={[10, 25, 50]}
                  initialState={{ pagination: { paginationModel: { pageSize: 25, page: 0 } } }}
                  density="compact"
                  disableRowSelectionOnClick
                  sx={{ border: 'none' }}
                />
              </div>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
