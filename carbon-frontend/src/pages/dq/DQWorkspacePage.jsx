// carbon-frontend/src/pages/dq/DQWorkspacePage.jsx
// Unified DQ Workspace — Overview | Rules | Jobs | Suggestions | Monitoring
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Grid,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  AutoAwesome,
  CheckCircle,
  Dashboard,
  ErrorOutline,
  History,
  Insights,
  Rule as RuleIcon,
  Visibility,
} from '@mui/icons-material';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { useOperationProgress } from '../../hooks/useOperationProgress';
import { useAITaskTransfer } from '../../shell/useAITaskTransfer';
import SystemDialog from '../../components/SystemDialog';
import PageContainer from '../../components/layout/PageContainer';
import DetailHeader from '../../components/detail/DetailHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import StatCard from '../../components/Cards/StatCard';
import CarbonDataGrid from '../../components/DataGrid/CarbonDataGrid';
import PanelTable from '../../components/panel/PanelTable';
import {
  getOrgDQMetrics,
  getDQResults,
  listDQJobs,
  listDQSuggestions,
  acceptDQSuggestion,
  rejectDQSuggestion,
  listDQAnomalies,
  getTableProfiles,
  getFreshnessChecks,
  getSchemaSnapshots,
  getSchemaChanges,
} from '../../api/dq';
import {
  ruleTypeLabel,
  dimensionLabel,
  jobTypeLabel,
  severityLabel,
  RESULT_STATUS_COLORS,
  SCHEMA_CHANGE_COLORS,
} from './constants';
import RulesTab from './tabs/RulesTab';
import JobsTab from './tabs/JobsTab';
import AIActionButton from '../../components/dq/AIActionButton';

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  return [];
}

const TAB_IDS = ['overview', 'rules', 'jobs', 'suggestions', 'monitoring'];
const TAB_LABELS = [
  { id: 'overview', labelKey: 'tab.overview', icon: <Dashboard fontSize="small" /> },
  { id: 'rules', labelKey: 'tab.rules', icon: <RuleIcon fontSize="small" /> },
  { id: 'jobs', labelKey: 'tab.jobs', icon: <History fontSize="small" /> },
  { id: 'suggestions', labelKey: 'tab.suggestions', icon: <AutoAwesome fontSize="small" /> },
  { id: 'monitoring', labelKey: 'tab.monitoring', icon: <Insights fontSize="small" /> },
];

function scoreColor(score) {
  if (score == null) return 'primary';
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'error';
}

// ─── Overview ────────────────────────────────────────────────────────────────

function OverviewTab({ metrics, results, loading, runningJobs, onGoJobs, onRefresh, onAskAI }) {
  const { t } = useTranslation('dq');
  const trendData = useMemo(() => {
    const sorted = [...results].sort((a, b) => new Date(a.run_at) - new Date(b.run_at));
    const buckets = new Map();
    sorted.forEach((r) => {
      if (!r.run_at) return;
      const day = String(r.run_at).slice(0, 10);
      const bucket = buckets.get(day) || { total: 0, passed: 0 };
      bucket.total += 1;
      if (r.passed === true) bucket.passed += 1;
      buckets.set(day, bucket);
    });
    return [...buckets.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-14)
      .map(([, bucket]) => (bucket.total ? Math.round((bucket.passed / bucket.total) * 100) : 0));
  }, [results]);

  const attentionResults = useMemo(
    () => results.filter((r) => r.status === 'failed' || r.status === 'skipped_unavailable'),
    [results]
  );

  const resultColumns = useMemo(
    () => [
      {
        field: 'rule_name',
        headerName: t('columns.rule'),
        flex: 1.4,
        minWidth: 200,
        renderCell: ({ row }) => (
          <Stack spacing={0.25}>
            <Typography sx={{ fontWeight: 600 }}>{row.rule_name || '–'}</Typography>
            <Typography sx={{ color: 'text.secondary' }}>
              {ruleTypeLabel(t, row.rule_type)}
            </Typography>
          </Stack>
        ),
      },
      {
        field: 'run_at',
        headerName: t('columns.runAt'),
        width: 160,
        renderCell: ({ row }) =>
          row.run_at ? new Date(row.run_at).toLocaleString() : '—',
      },
      {
        field: 'status',
        headerName: t('columns.status'),
        width: 140,
        renderCell: ({ row }) => (
          <Chip
            size="small"
            color={RESULT_STATUS_COLORS[row.status] || 'default'}
            label={
              row.status === 'skipped_unavailable'
                ? t('status.skippedUnavailable')
                : row.status === 'passed' || row.status === 'failed'
                  ? t(`status.${row.status}`)
                  : row.status || (row.passed ? t('status.passed') : t('status.failed'))
            }
          />
        ),
      },
      { field: 'checked_count', headerName: t('columns.checked'), width: 100, type: 'number' },
      {
        field: 'failed_count',
        headerName: t('columns.failed'),
        width: 90,
        type: 'number',
        renderCell: ({ row }) =>
          row.failed_count ? (
            <Typography sx={{ color: 'error.main', fontWeight: 600 }}>
              {row.failed_count}
            </Typography>
          ) : (
            <Typography>{row.failed_count ?? '—'}</Typography>
          ),
      },
      {
        field: 'score',
        headerName: t('columns.score'),
        width: 90,
        renderCell: ({ row }) =>
          row.score != null ? (
            <Typography>{Number(row.score).toFixed(1)}%</Typography>
          ) : (
            '—'
          ),
      },
    ],
    [t]
  );

  if (loading) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
        <Typography sx={{ color: 'text.secondary' }}>{t('overview.loading')}</Typography>
      </Paper>
    );
  }

  const metrics_ = metrics || {};
  const dimensionEntries = Object.entries(metrics_.scores_by_dimension || {});

  return (
    <Box>
      <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            title={t('overview.overallScore')}
            value={metrics_.overall_score != null ? metrics_.overall_score.toFixed(1) : '—'}
            unit="%"
            color={scoreColor(metrics_.overall_score)}
            sparkline={trendData}
            tooltip={t('overview.scoreTrendTooltip')}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title={t('overview.tablesProfiled')} value={metrics_.table_count ?? '—'} color="info" />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            title={t('overview.completeness')}
            value={metrics_.completeness_pct != null ? metrics_.completeness_pct.toFixed(1) : '—'}
            unit="%"
            color={scoreColor(metrics_.completeness_pct)}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard
            title={t('overview.rules')}
            value={metrics_.total_rules ?? '—'}
            color="primary"
            tooltip={t('overview.rulesBreakdown', { passing: metrics_.passing_rules ?? 0, failing: metrics_.failing_rules ?? 0, skipped: metrics_.skipped_rules ?? 0 })}
          />
        </Grid>
      </Grid>

      {runningJobs.length > 0 ? (
        <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5, borderRadius: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary' }}>
              {t('overview.runningJobs')}
            </Typography>
            {runningJobs.map((job) => (
              <Chip
                key={job.id}
                size="small"
                color="primary"
                label={`#${job.id} ${jobTypeLabel(t, job.job_type)}`}
                onClick={onGoJobs}
              />
            ))}
          </Stack>
        </Paper>
      ) : null}

      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 700 }}>
          {t('overview.recentFailures')}
          {attentionResults.length ? ` (${attentionResults.length})` : ''}
        </Typography>
        <Stack direction="row" spacing={1}>
          <AIActionButton title={t('overview.askAiAboutHealth')} onClick={onAskAI} />
          <Button size="small" variant="outlined" onClick={onRefresh}>
            {t('refresh')}
          </Button>
        </Stack>
      </Stack>
      <Paper variant="outlined" sx={{ borderRadius: 2 }}>
        <CarbonDataGrid
          columns={resultColumns}
          rows={attentionResults}
          loading={loading}
          getRowId={(row) => row.id || `${row.rule}-${row.run_at}`}
          emptyMessage={t('overview.emptyRecentFailures')}
          onRowClick={() => undefined}
        />
      </Paper>

      {dimensionEntries.length > 0 ? (
        <Box sx={{ mt: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>
            {t('overview.scoresByDimension')}
          </Typography>
          <Grid container spacing={1.5}>
            {dimensionEntries.map(([dim, score]) => (
              <Grid key={dim} size={{ xs: 6, md: 3 }}>
                <StatCard
                  title={dimensionLabel(t, dim)}
                  value={score != null ? Number(score).toFixed(1) : '—'}
                  unit="%"
                  color={scoreColor(score)}
                />
              </Grid>
            ))}
          </Grid>
        </Box>
      ) : null}
    </Box>
  );
}

// ─── Suggestions ─────────────────────────────────────────────────────────────

function SuggestionsTab() {
  const { t } = useTranslation('dq');
  const { token } = useAuth();
  const navigate = useNavigate();
  const { notify, notifyFromError } = useNotification();
  const { transferTask } = useAITaskTransfer();
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await listDQSuggestions(token, { status: 'pending' });
      setSuggestions(unwrap(payload));
    } catch (err) {
      notifyFromError(err, t('suggestions.loadError'));
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAccept = async (suggestion) => {
    setBusyId(`accept-${suggestion.id}`);
    try {
      const rule = await acceptDQSuggestion(token, suggestion.id);
      notify({ message: t('suggestions.accepted', { name: rule.name }), type: 'success' });
      navigate(`/dq/rules/${rule.id}`);
    } catch (err) {
      notifyFromError(err, t('suggestions.acceptError'));
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async () => {
    if (!rejectTarget) return;
    setBusyId(`reject-${rejectTarget.id}`);
    try {
      await rejectDQSuggestion(token, rejectTarget.id, rejectReason || undefined);
      notify({ message: t('suggestions.rejected'), type: 'info' });
      setRejectTarget(null);
      setRejectReason('');
      load();
    } catch (err) {
      notifyFromError(err, t('suggestions.rejectError'));
    } finally {
      setBusyId(null);
    }
  };

  const handleRefineWithAI = async (suggestion) => {
    await transferTask(
      'chat',
      {
        prompt: `Refine this DQ suggestion before applying it:\n${JSON.stringify(suggestion.payload || {}, null, 2)}`,
        suggestion_id: suggestion.id,
        table_name: suggestion.table_name,
      },
      {
        title: t('suggestions.refineTitle', { id: suggestion.id }),
        source_page: 'dq-workspace-suggestions',
        workspaceContext: {
          workspace: 'dq',
          current_view: 'suggestions',
          entity_type: 'table',
          entity_id: suggestion.table_id ?? suggestion.data_table ?? null,
          entity_name: suggestion.table_name ?? null,
          intent_signal: 'explore',
          recent_actions: [],
        },
      },
    );
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 700 }}>
          {t('suggestions.title')}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button size="small" variant="outlined" onClick={load}>
          {t('refresh')}
        </Button>
      </Stack>

      {loading ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <Typography sx={{ color: 'text.secondary' }}>{t('suggestions.loading')}</Typography>
        </Paper>
      ) : suggestions.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <AutoAwesome sx={{ fontSize: '1.75rem', color: 'text.disabled', mb: 1 }} />
          <Typography sx={{ color: 'text.secondary' }}>
            {t('suggestions.empty')}
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={1.5}>
          {suggestions.map((s) => (
            <Paper key={s.id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
              <Stack direction="row" alignItems="flex-start" spacing={1.5} flexWrap="wrap">
                <Box sx={{ flexGrow: 1, minWidth: 280 }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Chip size="small" color="primary" label={t('suggestions.tableChip', { table: s.table_name || s.data_table })} />
                    {s.confidence != null ? (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={t('suggestions.confidence', { value: Number(s.confidence).toFixed(0) })}
                        color={s.confidence >= 0.7 ? 'success' : s.confidence >= 0.4 ? 'warning' : 'default'}
                      />
                    ) : null}
                    <Typography sx={{ color: 'text.secondary' }}>
                      {t('suggestions.byLine', {
                        name: s.created_by_name || 'Pulse',
                        date: s.created_at ? new Date(s.created_at).toLocaleString() : '—',
                      })}
                    </Typography>
                  </Stack>
                  {s.rationale ? (
                    <Typography sx={{ mt: 1, color: 'text.secondary' }}>
                      {s.rationale}
                    </Typography>
                  ) : null}
                  <Box sx={{ mt: 1 }}>
                    <Button size="small" onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
                      {expanded === s.id ? t('suggestions.hidePayload') : t('suggestions.showPayload')}
                    </Button>
                  </Box>
                  {expanded === s.id ? (
                    <Box
                      component="pre"
                      sx={{
                        fontSize: '0.75rem',
                        p: 1.5,
                        mt: 1,
                        borderRadius: 1,
                        bgcolor: 'action.hover',
                        overflow: 'auto',
                        maxHeight: 300,
                        m: 0,
                      }}
                    >
                      {JSON.stringify(s.payload, null, 2)}
                    </Box>
                  ) : null}
                </Box>
                <Stack direction="row" spacing={1}>
                  <Button
                    size="small"
                    variant="contained"
                    startIcon={<CheckCircle />}
                    disabled={busyId === `accept-${s.id}`}
                    onClick={() => handleAccept(s)}
                  >
                    {t('suggestions.accept')}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="inherit"
                    disabled={busyId === `reject-${s.id}`}
                    onClick={() => {
                      setRejectTarget(s);
                      setRejectReason('');
                    }}
                  >
                    {t('suggestions.reject')}
                  </Button>
                  <AIActionButton
                    title={t('suggestions.refineWithAi')}
                    onClick={() => handleRefineWithAI(s)}
                  />
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      <SystemDialog
        open={!!rejectTarget}
        title={t('suggestions.rejectDialogTitle')}
        onClose={() => setRejectTarget(null)}
        onCancel={() => setRejectTarget(null)}
        cancelLabel={t('cancel')}
        width={480}
        height={280}
        minWidth={400}
        minHeight={220}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button variant="contained" color="error" size="small" onClick={handleReject} disabled={busyId}>
            {t('suggestions.rejectButton')}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={3}
            size="small"
            label={t('suggestions.reasonOptional')}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            sx={{ mt: 1 }}
          />
        </Box>
      </SystemDialog>
    </Box>
  );
}

// ─── Schema Snapshot Dialog ──────────────────────────────────────────────────

function SchemaDialog({ open, onClose, snapshot }) {
  const { t } = useTranslation('dq');
  if (!snapshot) return null;
  const cols = snapshot.column_schema || {};
  const entries = Object.entries(cols);
  return (
    <SystemDialog
      open={open}
      title={t('monitoring.schemaSnapshotTitle', { table: snapshot.table_name || snapshot.data_table })}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('close')}
      width={760}
      height={520}
      minWidth={560}
      minHeight={380}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Typography sx={{ color: 'text.secondary', mb: 1 }}>
          {t('monitoring.snapshotSummary', {
            at: snapshot.snapshot_at ? new Date(snapshot.snapshot_at).toLocaleString() : '—',
            rows: snapshot.row_count ?? '—',
            columns: entries.length,
          })}
        </Typography>
        <PanelTable
          title={t('monitoring.columnSchema')}
          subtitle={t('monitoring.columnsCount', { count: entries.length })}
          columns={[
            { key: 'col', header: t('columns.column') },
            { key: 'type', header: t('columns.type') },
          ]}
          rows={entries.map(([col, def]) => ({
            id: col,
            col,
            type: typeof def === 'object' ? def.type || JSON.stringify(def) : String(def),
          }))}
          emptyText={t('monitoring.noColumnSchema')}
        />
      </Box>
    </SystemDialog>
  );
}

// ─── Monitoring ──────────────────────────────────────────────────────────────

function MonitoringTab() {
  const { t } = useTranslation('dq');
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const { transferTask } = useAITaskTransfer();
  const [profiles, setProfiles] = useState([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profilesError, setProfilesError] = useState('');
  const [freshness, setFreshness] = useState([]);
  const [schemaSnapshots, setSchemaSnapshots] = useState([]);
  const [schemaChanges, setSchemaChanges] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [freshnessLoading, setFreshnessLoading] = useState(false);
  const [monitoringError, setMonitoringError] = useState('');
  const [anomalyBusyTableId, setAnomalyBusyTableId] = useState(null);
  const [schemaDialog, setSchemaDialog] = useState(null);

  const loadProfiles = useCallback(async () => {
    setProfilesLoading(true);
    setProfilesError('');
    try {
      const payload = await getTableProfiles({}, token);
      setProfiles(unwrap(payload));
    } catch (err) {
      setProfilesError(err?.message || t('monitoring.loadProfilesError'));
      notifyFromError(err, t('monitoring.loadProfilesError'));
    } finally {
      setProfilesLoading(false);
    }
  }, [token, notifyFromError, t]);

  const loadMonitoring = useCallback(async () => {
    setFreshnessLoading(true);
    setMonitoringError('');
    try {
      const [f, ss, sc, a] = await Promise.all([
        getFreshnessChecks({}, token),
        getSchemaSnapshots({}, token),
        getSchemaChanges({}, token),
        listDQAnomalies(token, { ordering: '-detected_at', limit: 100 }),
      ]);
      setFreshness(unwrap(f));
      setSchemaSnapshots(unwrap(ss));
      setSchemaChanges(unwrap(sc));
      setAnomalies(unwrap(a));
    } catch (err) {
      setMonitoringError(err?.message || t('monitoring.loadMonitoringError'));
      notifyFromError(err, t('monitoring.loadMonitoringNotifyError'));
    } finally {
      setFreshnessLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  useEffect(() => {
    loadMonitoring();
  }, [loadMonitoring]);

  const handleAnalyzeAnomaliesWithAI = useCallback(
    async (row) => {
      const tableId = row?.data_table || row?.table_id || row?.id;
      if (!tableId) return;
      setAnomalyBusyTableId(tableId);
      try {
        await transferTask(
          'anomaly',
          {
            table_id: tableId,
            table_name: row?.table_name || `Table #${tableId}`,
            profile_count_hint: row?.profile_count,
            prompt: `Analyze anomaly risk and recent profile drift for ${row?.table_name || `Table #${tableId}`}.`,
          },
          {
            title: t('monitoring.anomalyScanTitle', { table: row?.table_name || t('monitoring.tableNumber', { id: tableId }) }),
            source_page: 'dq-workspace-monitoring',
            workspaceContext: {
              workspace: 'dq',
              current_view: 'monitoring',
              entity_type: 'table',
              entity_id: tableId,
              entity_name: row?.table_name || `Table #${tableId}`,
              intent_signal: 'explore',
              recent_actions: [],
            },
          },
        );
      } finally {
        setAnomalyBusyTableId(null);
      }
    },
    [transferTask, t],
  );

  const profileColumns = useMemo(
    () => [
      {
        field: 'table_name',
        headerName: t('columns.table'),
        flex: 1.5,
        minWidth: 200,
        renderCell: ({ row }) => (
          <Typography sx={{ fontWeight: 600 }}>{row.table_name || '—'}</Typography>
        ),
      },
      { field: 'row_count', headerName: t('columns.rowCount'), width: 110, type: 'number' },
      { field: 'column_count', headerName: t('columns.columns'), width: 90, type: 'number' },
      {
        field: 'null_pct',
        headerName: t('columns.nullPct'),
        width: 90,
        type: 'number',
        renderCell: ({ row }) =>
          row.null_pct != null ? `${Number(row.null_pct).toFixed(1)}%` : '—',
      },
      {
        field: 'distinctness',
        headerName: t('columns.distinctness'),
        width: 110,
        type: 'number',
        renderCell: ({ row }) => (row.distinctness != null ? Number(row.distinctness).toFixed(2) : '—'),
      },
      {
        field: 'profiled_at',
        headerName: t('columns.profiledAt'),
        width: 170,
        renderCell: ({ row }) => (row.profiled_at ? new Date(row.profiled_at).toLocaleString() : '—'),
      },
      {
        field: 'actions',
        headerName: '',
        sortable: false,
        width: 170,
        renderCell: ({ row }) => {
          const tableId = row?.data_table || row?.table_id || row?.id;
          return (
            <AIActionButton
              title={t('monitoring.analyzeAnomalies')}
              disabled={!tableId}
              busy={anomalyBusyTableId === tableId}
              onClick={() => handleAnalyzeAnomaliesWithAI(row)}
            />
          );
        },
      },
    ],
    [handleAnalyzeAnomaliesWithAI, anomalyBusyTableId, t]
  );

  const freshnessColumns = useMemo(
    () => [
      {
        field: 'table_name',
        headerName: t('columns.table'),
        flex: 1.5,
        minWidth: 200,
        renderCell: ({ row }) => (
          <Typography sx={{ fontWeight: 600 }}>{row.table_name || '—'}</Typography>
        ),
      },
      { field: 'expected_max_age_hours', headerName: t('columns.maxAgeHours'), width: 120, type: 'number' },
      {
        field: 'is_fresh',
        headerName: t('columns.fresh'),
        width: 100,
        renderCell: ({ row }) => (
          <Chip
            size="small"
            icon={row.is_fresh ? <CheckCircle /> : <ErrorOutline />}
            label={row.is_fresh ? t('monitoring.yes') : t('monitoring.no')}
            color={row.is_fresh ? 'success' : 'error'}
            variant="outlined"
          />
        ),
      },
      {
        field: 'last_data_timestamp',
        headerName: t('columns.lastData'),
        width: 170,
        renderCell: ({ row }) => (row.last_data_timestamp ? new Date(row.last_data_timestamp).toLocaleString() : '—'),
      },
      {
        field: 'checked_at',
        headerName: t('columns.checkedAt'),
        width: 170,
        renderCell: ({ row }) => (row.checked_at ? new Date(row.checked_at).toLocaleString() : '—'),
      },
    ],
    [t]
  );

  const schemaChangeColumns = useMemo(
    () => [
      {
        field: 'table_name',
        headerName: t('columns.table'),
        flex: 1.2,
        minWidth: 160,
        renderCell: ({ row }) => (
          <Typography sx={{ fontWeight: 600 }}>{row.table_name || '—'}</Typography>
        ),
      },
      {
        field: 'change_type',
        headerName: t('columns.change'),
        width: 110,
        renderCell: ({ row }) => (
          <Chip size="small" color={SCHEMA_CHANGE_COLORS[row.change_type] || 'default'} label={row.change_type} />
        ),
      },
      { field: 'field_name', headerName: t('columns.field'), width: 150 },
      {
        field: 'detected_at',
        headerName: t('columns.detectedAt'),
        width: 170,
        renderCell: ({ row }) => (row.detected_at ? new Date(row.detected_at).toLocaleString() : '—'),
      },
    ],
    [t]
  );

  const snapshotColumns = useMemo(
    () => [
      {
        field: 'table_name',
        headerName: t('columns.table'),
        flex: 1.2,
        minWidth: 160,
        renderCell: ({ row }) => (
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{row.table_name || '—'}</Typography>
        ),
      },
      { field: 'row_count', headerName: t('columns.rowCount'), width: 100, type: 'number' },
      { field: 'column_count', headerName: t('columns.columns'), width: 90, type: 'number' },
      {
        field: 'snapshot_at',
        headerName: t('columns.snapshotAt'),
        width: 170,
        renderCell: ({ row }) => (row.snapshot_at ? new Date(row.snapshot_at).toLocaleString() : '—'),
      },
      {
        field: 'actions',
        headerName: '',
        width: 80,
        sortable: false,
        renderCell: ({ row }) => (
          <Tooltip title={t('monitoring.viewSchema')}>
            <IconButton size="small" onClick={() => setSchemaDialog(row)}>
              <Visibility fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
    ],
    [t]
  );

  return (
    <Box>
      <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mb: 1 }}>
        <Button size="small" variant="outlined" onClick={loadProfiles}>
          {t('monitoring.refreshProfiles')}
        </Button>
        <Button size="small" variant="outlined" onClick={loadMonitoring}>
          {t('monitoring.refreshMonitoring')}
        </Button>
      </Stack>

      {profilesError ? (
        <Alert severity="error" sx={{ mb: 1.5 }}>
          {profilesError}
        </Alert>
      ) : null}
      {monitoringError ? (
        <Alert severity="error" sx={{ mb: 1.5 }}>
          {monitoringError}
        </Alert>
      ) : null}

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('monitoring.tableProfiles')}</Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CarbonDataGrid
          columns={profileColumns}
          rows={profiles}
          loading={profilesLoading}
          getRowId={(row) => row.id || row.data_table}
          emptyMessage={t('monitoring.noProfiles')}
        />
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('monitoring.freshness')}</Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CarbonDataGrid
          columns={freshnessColumns}
          rows={freshness}
          loading={freshnessLoading}
          getRowId={(row) => row.id || row.data_table}
          emptyMessage={t('monitoring.noFreshness')}
        />
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('monitoring.schemaSnapshots')}</Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CarbonDataGrid
          columns={snapshotColumns}
          rows={schemaSnapshots}
          loading={freshnessLoading}
          getRowId={(row) => row.id}
          emptyMessage={t('monitoring.noSchemaSnapshots')}
        />
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('monitoring.anomalies')}</Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CarbonDataGrid
          columns={[
            {
              field: 'table_name',
              headerName: t('columns.table'),
              flex: 1.1,
              minWidth: 160,
              renderCell: ({ row }) => <Typography sx={{ fontWeight: 600 }}>{row.table_name || '—'}</Typography>,
            },
            { field: 'metric', headerName: t('columns.metric'), width: 180 },
            {
              field: 'severity',
              headerName: t('columns.severity'),
              width: 110,
              renderCell: ({ row }) => (
                <Chip
                  size="small"
                  color={row.severity === 'error' ? 'error' : row.severity === 'warn' ? 'warning' : 'info'}
                  label={severityLabel(t, row.severity || 'info')}
                />
              ),
            },
            {
              field: 'score',
              headerName: t('columns.score'),
              width: 90,
              renderCell: ({ row }) => (row.score != null ? Number(row.score).toFixed(2) : '—'),
            },
            {
              field: 'observed',
              headerName: t('columns.observed'),
              width: 100,
              renderCell: ({ row }) => (row.observed != null ? Number(row.observed).toFixed(2) : '—'),
            },
            {
              field: 'detected_at',
              headerName: t('columns.detectedAt'),
              width: 170,
              renderCell: ({ row }) => (row.detected_at ? new Date(row.detected_at).toLocaleString() : '—'),
            },
          ]}
          rows={anomalies}
          loading={freshnessLoading}
          getRowId={(row) => row.id}
          emptyMessage={t('monitoring.noAnomalies')}
        />
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('monitoring.schemaChanges')}</Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2 }}>
        <CarbonDataGrid
          columns={schemaChangeColumns}
          rows={schemaChanges}
          loading={freshnessLoading}
          getRowId={(row) => row.id}
          emptyMessage={t('monitoring.noSchemaChanges')}
        />
      </Paper>

      <SchemaDialog open={!!schemaDialog} onClose={() => setSchemaDialog(null)} snapshot={schemaDialog} />
    </Box>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function DQWorkspacePage() {
  const { t } = useTranslation('dq');
  useDocumentTitle(t('pageTitle'));
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const { transferTask } = useAITaskTransfer();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const tableFilter = searchParams.get('table') || '';

  const tabIndexFromHash = useMemo(() => {
    const hash = location.hash.replace('#', '').toLowerCase();
    const idx = TAB_IDS.indexOf(hash);
    if (idx >= 0) return idx;
    // Deep-link: /dq/rules?table=<id> opens the Rules tab
    return searchParams.get('table') ? TAB_IDS.indexOf('rules') : 0;
  }, [location.hash, searchParams]);

  // Tab state: persisted in localStorage (standard pattern), with URL hash as secondary
  const [tab, setTab] = useState(() => {
    const stored = localStorage.getItem('carbonDqWorkspaceTab');
    if (stored != null) {
      const parsed = parseInt(stored, 10);
      if (parsed >= 0 && parsed < TAB_IDS.length) return parsed;
    }
    return tabIndexFromHash;
  });

  // Keep internal tab state in sync with the URL hash (#jobs, #rules, …)
  useEffect(() => {
    setTab(tabIndexFromHash);
  }, [tabIndexFromHash]);

  const changeTab = useCallback((event, index) => {
    setTab(index);
    localStorage.setItem('carbonDqWorkspaceTab', index);
    const id = TAB_IDS[index];
    const current = location.hash;
    if (current !== `#${id}`) {
      window.history.replaceState(null, '', `#${id}`);
    }
  }, [location.hash]);

  // Programmatic tab switch (not from the Tabs onChange event)
  const goToTab = useCallback((index) => {
    changeTab(null, index);
  }, [changeTab]);

  // Shared jobs state + polling (Overview strip + Jobs tab)
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  const reloadJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const payload = await listDQJobs(token, {});
      setJobs(unwrap(payload));
    } catch (err) {
      notifyFromError(err, t('jobs.loadError'));
    } finally {
      setJobsLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    reloadJobs();
  }, [reloadJobs]);

  const activeJobCount = useMemo(
    () => jobs.filter((j) => j.status === 'queued' || j.status === 'running').length,
    [jobs]
  );

  // Wave D1: live narrated progress over SSE (no bare spinner, no 5s poll).
  // Each `op.progress` frame for a dq_run updates its job in place; a terminal
  // frame triggers a reload so the grid/drawer gets the authoritative result.
  const { connected } = useOperationProgress((frame) => {
    if (!frame || frame.op_type !== 'dq_run') return;
    const opId = String(frame.op_id);
    const terminal =
      frame.status === 'done' || frame.status === 'failed' || frame.status === 'canceled';

    setJobs((prev) => {
      const idx = prev.findIndex((j) => String(j.id) === opId);
      if (idx === -1) return prev;
      const next = prev.slice();
      next[idx] = {
        ...next[idx],
        status: frame.status,
        progress: frame.percent != null ? frame.percent : next[idx].progress,
        progressMessage: frame.message,
      };
      return next;
    });

    if (terminal) reloadJobs();
  });

  // Safety net only: if the stream is disconnected but jobs are still active,
  // reconcile with a slow poll so a missed terminal frame (transient bus)
  // can't leave a job stuck "running". No poll while SSE is connected.
  useEffect(() => {
    if (activeJobCount === 0 || connected) return undefined;
    const id = setInterval(() => {
      reloadJobs();
    }, 10000);
    return () => clearInterval(id);
  }, [activeJobCount, connected, reloadJobs]);

  const [metrics, setMetrics] = useState(null);
  const [results, setResults] = useState([]);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState('');

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError('');
    try {
      const [m, r] = await Promise.all([
        getOrgDQMetrics(token),
        getDQResults({ limit: 100, ordering: '-run_at' }, token),
      ]);
      setMetrics(m || null);
      setResults(unwrap(r));
    } catch (err) {
      setOverviewError(err?.message || t('overview.loadError'));
      notifyFromError(err, t('overview.loadError'));
    } finally {
      setOverviewLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  const runningJobs = useMemo(
    () => jobs.filter((j) => j.status === 'queued' || j.status === 'running'),
    [jobs]
  );

  const handleJobCreated = useCallback(() => {
    goToTab(TAB_IDS.indexOf('jobs'));
    reloadJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadJobs, tab]);

  const [mountedTabs, setMountedTabs] = useState(() => new Set([0]));
  useEffect(() => {
    setMountedTabs((prev) => new Set([...prev, tab]));
  }, [tab]);

  // WorkspaceContext emitted with every AI transfer from the DQ Workspace.
  // No selection → entity_type 'workspace'; table filter → 'table'.
  const buildWorkspaceContext = useCallback(() => ({
    workspace: 'dq',
    current_view: TAB_IDS[tab] ?? 'overview',
    entity_type: tableFilter ? 'table' : 'workspace',
    entity_id: tableFilter || null,
    entity_name: tableFilter ? `Table #${tableFilter}` : null,
    intent_signal: 'explore',
    recent_actions: [],
  }), [tab, tableFilter]);

  const handleAskAIHealth = useCallback(async () => {
    await transferTask(
      'nl_query',
      {
        prompt: 'Summarize DQ health, recent failures, and highest-risk dimensions.',
        row_count: results.length,
        columns: ['status', 'rule_type', 'score', 'failed_count', 'run_at'],
      },
      {
        title: t('overview.healthSummaryTitle'),
        source_page: 'dq-workspace-overview',
        workspaceContext: buildWorkspaceContext(),
      },
    );
  }, [transferTask, results.length, buildWorkspaceContext, t]);

  const handleSuggestRulesAI = useCallback(async () => {
    await transferTask(
      'dq_suggest',
      {
        table_id: tableFilter || null,
        table_name: tableFilter ? `Table #${tableFilter}` : null,
      },
      {
        title: tableFilter ? t('rules.suggestTitleTable', { id: tableFilter }) : t('rules.suggestTitle'),
        source_page: 'dq-workspace-rules',
        workspaceContext: buildWorkspaceContext(),
      },
    );
  }, [transferTask, tableFilter, buildWorkspaceContext, t]);

  const handleAnalyzeFailuresAI = useCallback(async () => {
    await transferTask(
      'nl_query',
      {
        prompt: 'Analyze recent DQ job failures and suggest likely root causes.',
        row_count: runningJobs.length,
        columns: ['job_type', 'status', 'error_message', 'created_at'],
      },
      {
        title: t('jobs.analyzeFailuresTitle'),
        source_page: 'dq-workspace-jobs',
        workspaceContext: buildWorkspaceContext(),
      },
    );
  }, [transferTask, runningJobs.length, buildWorkspaceContext, t]);

  return (
    <PageContainer>
      <DetailHeader
        title={t('pageTitle')}
        description={t('pageDescription')}
        icon={RuleIcon}
        onClose={() => navigate(-1)}
      />
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Tabs
          value={tab}
          onChange={changeTab}
          variant="scrollable"
          scrollButtons="auto"
        >
          {TAB_LABELS.map((tabItem) => (
            <Tab key={tabItem.id} label={t(tabItem.labelKey)} icon={tabItem.icon} iconPosition="start" />
          ))}
        </Tabs>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'background.paper', p: 1.5 }}>

      {tab === 0 ? (
        overviewError ? (
          <Alert severity="error" sx={{ mb: 1 }}>
            {overviewError}
            <Button size="small" variant="outlined" sx={{ ml: 1 }} onClick={loadOverview}>
              {t('retry')}
            </Button>
          </Alert>
        ) : (
          <OverviewTab
            metrics={metrics}
            results={results}
            loading={overviewLoading}
            runningJobs={runningJobs}
            onGoJobs={() => goToTab(2)}
            onRefresh={loadOverview}
            onAskAI={handleAskAIHealth}
          />
        )
      ) : null}
      {mountedTabs.has(1) ? (
        <Box sx={{ display: tab === 1 ? 'block' : 'none' }}>
          <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
            <AIActionButton title={t('rules.suggestWithAi')} onClick={handleSuggestRulesAI} />
          </Stack>
          <RulesTab onJobCreated={handleJobCreated} tableFilter={tableFilter} />
        </Box>
      ) : null}
      {mountedTabs.has(2) ? (
        <Box sx={{ display: tab === 2 ? 'block' : 'none' }}>
          <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
            <AIActionButton title={t('jobs.analyzeFailuresWithAi')} onClick={handleAnalyzeFailuresAI} />
          </Stack>
          <JobsTab jobs={jobs} loading={jobsLoading} reload={reloadJobs} />
        </Box>
      ) : null}
      {mountedTabs.has(3) ? (
        <Box sx={{ display: tab === 3 ? 'block' : 'none' }}>
          <SuggestionsTab />
        </Box>
      ) : null}
      {mountedTabs.has(4) ? (
        <Box sx={{ display: tab === 4 ? 'block' : 'none' }}>
          <MonitoringTab />
        </Box>
      ) : null}
    </Box>
    </PageContainer>
  );
}
