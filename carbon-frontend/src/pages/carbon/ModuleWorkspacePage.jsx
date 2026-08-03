import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Chip, CircularProgress, Divider, LinearProgress, Stack, Typography, useTheme } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import AssessmentIcon from '@mui/icons-material/Assessment';
import LinkIcon from '@mui/icons-material/Link';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import MemoryIcon from '@mui/icons-material/Memory';
import ShieldIcon from '@mui/icons-material/Shield';
import { useAuth } from '../../auth/AuthContext';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchOwnerActivity } from '../../api/emissions';
import { getTableDQMetrics } from '../../api/dq';
import { fetchAssetProfiles, fetchGovernancePolicies, fetchGovernanceEvents, fetchTableRelations } from '../../api/catalog';
import { CarbonDataGrid, PageHeader, EmptyState, ErrorAlert, LoadingSkeleton } from '../../components';
import EntityDetailShell from '../../components/entity/EntityDetailShell';
import useDetailPanel from '../../components/entity/useDetailPanel';
import useDocumentTitle from '../../hooks/useDocumentTitle';

const SCOPE_META = {
  1: { label: 'Scope 1', color: 'error' },
  2: { label: 'Scope 2', color: 'warning' },
  3: { label: 'Scope 3', color: 'info' },
};

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

// ── Activity kind helpers (shared across tabs) ──────────────────────────────

const ACTIVITY_KINDS = {
  data_change:  { label: 'Data', color: 'info',     Icon: MemoryIcon },
  dq_run:       { label: 'DQ',   color: 'success',  Icon: AssessmentIcon },
  governance:   { label: 'Gov',  color: 'secondary',Icon: ShieldIcon },
  calculation:  { label: 'Calc', color: 'warning',  Icon: AssessmentIcon },
};

function detectActivityKind(item) {
  const d = (item.detail || item.message || item.event || '').toLowerCase();
  if (d.includes('governance') || d.includes('lock') || d.includes('policy') || d.includes('approve')) return 'governance';
  if (d.includes('dq') || d.includes('quality') || d.includes('check') || d.includes('rule') || d.includes('profile')) return 'dq_run';
  if (d.includes('calc') || d.includes('compute') || d.includes('emission') || d.includes('target')) return 'calculation';
  return 'data_change';
}

function DetailRow({ label, value, theme }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 1, py: 1, borderBottom: `1px solid ${theme.palette.divider}` }}>
      <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.72rem' }}>{label}</Typography>
      <Typography component="span" variant="body2" sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.82rem' }}>{value ?? '—'}</Typography>
    </Box>
  );
}

/* ── Health tab — DQ gauge + per-table breakdown ──────────────────────────── */

function ModuleHealthTab({ module, tables, token }) {
  const [tableMetrics, setTableMetrics] = useState({});

  useEffect(() => {
    if (!token || !tables?.length) return;
    Promise.allSettled(
      tables.map((t) =>
        getTableDQMetrics(t.id, token).then((m) => [t.id, m]).catch(() => [t.id, null])
      )
    ).then((results) => {
      const map = {};
      results.forEach((r) => { if (r.status === 'fulfilled') { const [id, m] = r.value; map[id] = m; } });
      setTableMetrics(map);
    });
  }, [token, tables]);

  const dqScore = module?.quality_score ?? 0;
  const dqColor = dqScore >= 80 ? 'success.main' : dqScore >= 60 ? 'warning.main' : 'error.main';
  const completion = tables.length > 0
    ? Math.round((tables.filter((t) => (t.row_count || 0) > 0).length / tables.length) * 100)
    : 0;
  const tablesWithData = tables.filter((t) => (t.row_count || 0) > 0);

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Health
      </Typography>

      {/* DQ Gauge */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress variant="determinate" value={Math.min(dqScore, 100)} size={72} thickness={5} sx={{ color: dqColor }} />
          <Box sx={{ position: 'absolute', top: 0, left: 0, bottom: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.82rem', color: dqColor }}>
              {dqScore > 0 ? `${Math.round(dqScore)}%` : '—'}
            </Typography>
          </Box>
        </Box>
        <Box>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>DQ Score</Typography>
          <Chip
            label={dqScore >= 80 ? 'Passing' : dqScore >= 60 ? 'Warning' : dqScore > 0 ? 'Failing' : 'No data'}
            size="small"
            color={dqScore >= 80 ? 'success' : dqScore >= 60 ? 'warning' : dqScore > 0 ? 'error' : 'default'}
            variant="outlined"
            sx={{ height: 20, fontSize: '0.68rem', mt: 0.5 }}
          />
        </Box>
      </Box>

      <Divider />

      {/* Completion bar */}
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.72rem' }}>Completion</Typography>
          <Typography variant="body2" sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{completion}%</Typography>
        </Box>
        <LinearProgress variant="determinate" value={completion} sx={{ height: 6, borderRadius: 99 }} />
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.68rem', mt: 0.5 }}>
          {tablesWithData.length}/{tables.length} tables have data
        </Typography>
      </Box>

      {/* Per-table DQ */}
      {tablesWithData.length > 0 && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 700, fontSize: '0.72rem' }}>
            Table Quality
          </Typography>
          {tablesWithData.map((t) => {
            const m = tableMetrics[t.id];
            const score = m?.score ?? 0;
            const sColor = score >= 80 ? 'success.main' : score >= 60 ? 'warning.main' : 'error.main';
            return (
              <Box key={t.id}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                  <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{t.name || t.title}</Typography>
                  <Typography sx={{ fontSize: '0.68rem', color: sColor, fontWeight: 700 }}>
                    {m ? `${Math.round(score)}%` : '—'}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(score, 100)}
                  sx={{ height: 4, borderRadius: 99, mb: 0.25, '& .MuiLinearProgress-bar': { bgcolor: sColor } }}
                />
                {m && (
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                    {m.failing_rules ?? 0} failing / {m.total_rules ?? 0} rules
                  </Typography>
                )}
              </Box>
            );
          })}
        </>
      )}
    </Box>
  );
}

/* ── Lineage tab — upstream/downstream table dependencies ─────────────────── */

function ModuleLineageTab({ tables, token }) {
  const theme = useTheme();
  const [relations, setRelations] = useState([]);

  useEffect(() => {
    if (!token || !tables?.length) return;
    Promise.allSettled(
      tables.map((t) =>
        fetchTableRelations(token, { from_table: t.id }).catch(() => [])
      )
    ).then((results) => {
      const all = [];
      results.forEach((r) => { if (r.status === 'fulfilled' && Array.isArray(r.value)) all.push(...r.value); });
      setRelations(all);
    });
  }, [token, tables]);

  const upstream = relations.filter((r) => tables.some((t) => t.id === r.to_table));
  const downstream = relations.filter((r) => tables.some((t) => t.id === r.from_table));

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Lineage
      </Typography>

      {/* Upstream */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <LinkIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700 }}>Upstream ({upstream.length})</Typography>
        </Box>
        {upstream.length === 0 ? (
          <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>No upstream dependencies</Typography>
        ) : (
          <Stack spacing={1}>
            {upstream.map((r) => (
              <Box key={r.id} sx={{ pl: 2.5, py: 0.75, borderLeft: `2px solid ${theme.palette.divider}` }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{r.from_table_name || `Table #${r.from_table}`}</Typography>
                <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{r.relation_type || 'references'}</Typography>
              </Box>
            ))}
          </Stack>
        )}
      </Box>

      {/* Downstream */}
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <AccountTreeIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700 }}>Downstream ({downstream.length})</Typography>
        </Box>
        {downstream.length === 0 ? (
          <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>No downstream consumers</Typography>
        ) : (
          <Stack spacing={1}>
            {downstream.map((r) => (
              <Box key={r.id} sx={{ pl: 2.5, py: 0.75, borderLeft: `2px solid ${theme.palette.primary.light}` }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{r.to_table_name || `Table #${r.to_table}`}</Typography>
                <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{r.relation_type || 'consumes'}</Typography>
              </Box>
            ))}
          </Stack>
        )}
      </Box>

      {upstream.length === 0 && downstream.length === 0 && (
        <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', textAlign: 'center', py: 2 }}>
          No lineage data available
        </Typography>
      )}
    </Box>
  );
}

/* ── Governance tab — policy status, lock state, access ────────────────────── */

function ModuleGovernanceTab({ module, tables, token }) {
  const theme = useTheme();
  const [policies, setPolicies] = useState([]);
  const [assetProfile, setAssetProfile] = useState(null);

  useEffect(() => {
    if (!token) return;
    fetchGovernancePolicies(token)
      .then((p) => setPolicies(Array.isArray(p) ? p : []))
      .catch(() => setPolicies([]));
    fetchAssetProfiles(token)
      .then((profiles) => {
        const match = (profiles || []).find(
          (p) => p.name === module?.name || p.source_id === module?.id
        );
        setAssetProfile(match || null);
      })
      .catch(() => setAssetProfile(null));
  }, [token, module?.id, module?.name]);

  const isLocked = module?.is_locked || assetProfile?.governance?.locked || false;
  const lastVerified = assetProfile?.governance?.last_verified ?? null;
  const relevantPolicies = policies.filter((p) => p.enabled);

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Governance
      </Typography>

      {/* Lock status */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        {isLocked ? (
          <LockIcon sx={{ fontSize: 28, color: 'error.main' }} />
        ) : (
          <LockOpenIcon sx={{ fontSize: 28, color: 'success.main' }} />
        )}
        <Box>
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: isLocked ? 'error.main' : 'success.main' }}>
            {isLocked ? 'Locked' : 'Unlocked'}
          </Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
            {isLocked ? 'Write operations blocked' : 'Edits allowed'}
          </Typography>
        </Box>
      </Box>

      <Divider />

      <DetailRow label="Org unit" value={module?.org_unit_name || module?.name} theme={theme} />
      <DetailRow label="Last verified" value={fmtDate(lastVerified)} theme={theme} />
      <DetailRow label="Tables" value={`${tables.length}`} theme={theme} />

      {/* Policies */}
      {relevantPolicies.length > 0 && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 700, fontSize: '0.72rem', mt: 1 }}>
            Active Policies ({relevantPolicies.length})
          </Typography>
          <Stack spacing={0.75}>
            {relevantPolicies.map((p) => (
              <Box key={p.id} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ShieldIcon sx={{ fontSize: 14, color: 'secondary.main' }} />
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{p.name}</Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                    {p.policy_type} · {p.scope_type}
                  </Typography>
                </Box>
              </Box>
            ))}
          </Stack>
        </>
      )}
    </Box>
  );
}

/* ── Activity tab — enhanced with categorization + filters ─────────────────── */

function ModuleActivityTab({ activity, token }) {
  const [filter, setFilter] = useState('all');
  const [govEvents, setGovEvents] = useState([]);

  useEffect(() => {
    if (!token) return;
    fetchGovernanceEvents(token, { limit: 20 })
      .then((events) => setGovEvents(Array.isArray(events) ? events : []))
      .catch(() => setGovEvents([]));
  }, [token]);

  const merged = useMemo(() => {
    const govMapped = govEvents.map((e) => ({
      id: e.id,
      detail: e.description || e.event || e.action || 'Governance event',
      timestamp: e.timestamp || e.created_at,
      kind: 'governance',
    }));
    const actMapped = (activity || []).map((a) => ({ ...a, kind: detectActivityKind(a) }));
    const combined = [...actMapped, ...govMapped];
    combined.sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0));
    return combined;
  }, [activity, govEvents]);

  const filtered = useMemo(() => {
    if (filter === 'all') return merged;
    return merged.filter((item) => item.kind === filter);
  }, [merged, filter]);

  const filterOptions = [
    { value: 'all', label: 'All' },
    { value: 'data_change', label: 'Data', color: 'info' },
    { value: 'dq_run', label: 'DQ', color: 'success' },
    { value: 'governance', label: 'Gov', color: 'secondary' },
    { value: 'calculation', label: 'Calc', color: 'warning' },
  ];

  return (
    <Box sx={{ p: 1.5 }}>
      <Stack direction="row" spacing={0.5} sx={{ mb: 1.5, flexWrap: 'wrap', gap: 0.5 }}>
        {filterOptions.map((opt) => {
          const isActive = filter === opt.value;
          return (
            <Chip
              key={opt.value}
              label={opt.label}
              size="small"
              variant={isActive ? 'filled' : 'outlined'}
              color={isActive ? (opt.color || 'primary') : 'default'}
              onClick={() => setFilter(opt.value)}
              sx={{ height: 22, fontSize: '0.65rem', fontWeight: isActive ? 700 : 500, cursor: 'pointer' }}
            />
          );
        })}
      </Stack>

      {filtered.length === 0 ? (
        <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>No recent activity.</Typography>
      ) : (
        <Stack divider={<Divider flexItem />} spacing={0}>
          {filtered.map((item, i) => {
            const cfg = ACTIVITY_KINDS[item.kind] || ACTIVITY_KINDS.data_change;
            const Icon = cfg.Icon;
            return (
              <Box key={item.id ?? i} sx={{ py: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <Icon sx={{ fontSize: 14, mt: '2px', color: `${cfg.color}.main`, flexShrink: 0 }} />
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.72rem', lineHeight: 1.35 }}>
                    {item.detail || item.message || 'Updated'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.25 }}>
                    {fmtDate(item.timestamp || item.created_at)}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Stack>
      )}
    </Box>
  );
}

export default function ModuleWorkspacePage() {
  useDocumentTitle("My Data Workspace");
  const navigate = useNavigate();
  const { moduleId } = useParams();
  const { token, context } = useAuth();
  const [tables, setTables] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const projectId = context?.project_id || context?.projectId;
  const module = useMemo(
    () => (context?.modules || []).find((item) => String(item.id) === String(moduleId)),
    [context?.modules, moduleId]
  );

  useEffect(() => {
    if (!token || !projectId || !moduleId) return;
    setLoading(true);
    Promise.all([
      fetchDataSchemaTables(token, projectId, moduleId),
      fetchOwnerActivity({ limit: 8 }, token),
    ])
      .then(([tableData, activityData]) => {
        setTables(tableData || []);
        setActivity(activityData || []);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load source workspace');
      })
      .finally(() => setLoading(false));
  }, [moduleId, projectId, token]);

  const _breadcrumb = useMemo(() => [
    { label: 'Home', path: '/dashboard' },
    { label: 'My Data', path: '/carbon/my-data' },
    { label: module?.name || '...' },
  ], [module?.name]);

  const columns = useMemo(() => [
    {
      field: 'title',
      headerName: 'Table Name',
      flex: 2,
      minWidth: 220,
      renderCell: (params) => <Typography sx={{ fontWeight: 600 }}>{params.value || params.row.name}</Typography>,
    },
    {
      field: 'row_count',
      headerName: 'Rows',
      width: 80,
      type: 'number',
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip label={params.row.row_count === 0 ? 'No Data' : 'Has Data'} color={params.row.row_count === 0 ? 'default' : 'success'} size="small" />
      ),
    },
    {
      field: 'arrow',
      headerName: '',
      width: 50,
      sortable: false,
      renderCell: () => <ChevronRightIcon fontSize="small" color="action" />,
    },
  ], []);

  const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange } = useDetailPanel({
    tabs: [
      { label: 'Health',      render: () => <ModuleHealthTab module={module} tables={tables} token={token} /> },
      { label: 'Lineage',     render: () => <ModuleLineageTab tables={tables} token={token} /> },
      { label: 'Governance',  render: () => <ModuleGovernanceTab module={module} tables={tables} token={token} /> },
      { label: 'Activity',    render: () => <ModuleActivityTab activity={activity} token={token} /> },
    ],
    storageKey: 'moduleWorkspace:panelTab',
  });

  if (loading) return <LoadingSkeleton variant="detail" />;
  if (error) return (
    <Box>
      <PageHeader title="Source Workspace" subtitle="Loading workspace" />
      <ErrorAlert message={error} onRetry={() => window.location.reload()} />
    </Box>
  );

  return (
    <EntityDetailShell
      header={(
        <PageHeader
          title={module?.name || 'Loading...'}
          subtitle={`${SCOPE_META[module?.scope]?.label || 'Scope'} — ${tables.length} tables, ${module?.row_count || 0} rows`}
          description="Browse, filter, edit, and manage rows in each table. Use the DQ panel for quality checks. Add new rows or import data from CSV."
          badge={SCOPE_META[module?.scope]?.label ? { label: SCOPE_META[module?.scope]?.label, color: SCOPE_META[module?.scope]?.color } : undefined}
        />
      )}
      mainTabs={[{ label: 'Tables', render: () => (
        <Box sx={{ p: 2 }}>
          {tables.length === 0 ? (
            <EmptyState
              title="No tables defined for this source yet"
              description="Contact your administrator to set up data tables."
            />
          ) : (
            <CarbonDataGrid
              rows={tables}
              columns={columns}
              height={420}
              pageSize={20}
              showColumnToggle={false}
              onRowClick={(params) => navigate(`/carbon/my-data/${moduleId}/${params.row.id}`)}
            />
          )}
        </Box>
      ) }]}
      metricsPanel={metricsPanel}
      metricsTabs={metricsTabs}
      activeMetricsTab={activeMetricsTab}
      onMetricsTabChange={onMetricsTabChange}
      panelWidthKey="moduleWorkspace:panelWidth"
    />
  );
}
