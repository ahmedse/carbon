import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Chip, CircularProgress, Divider, IconButton, LinearProgress, Stack, Tooltip, Typography, useTheme } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
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
import { PanelGauge, PanelMetricRow, PanelTable } from '../../components/panel';
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

function fmtActivityText(item) {
  if (item.detail || item.message) return item.detail || item.message;
  const type = item.activity_type || '';
  const name = item.module_name || '';
  const tonnes = item.co2e_tonnes != null ? `${Number(item.co2e_tonnes).toFixed(1)} tCO₂e` : '';
  const parts = [name, tonnes].filter(Boolean);
  return parts.length ? `${type}${parts.length ? ' · ' : ''}${parts.join(' · ')}` : (type || 'Updated');
}

function detectActivityKind(item) {
  const d = (item.detail || item.message || item.event || item.activity_type || '').toLowerCase();
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

/* ── Health tab — DQ gauge + per-table breakdown (PanelTable) ─────────────── */

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
  const completion = tables.length > 0
    ? Math.round((tables.filter((t) => (t.row_count || 0) > 0).length / tables.length) * 100)
    : 0;
  const tablesWithData = tables.filter((t) => (t.row_count || 0) > 0);

  const qualityRows = tablesWithData.map((t) => {
    const m = tableMetrics[t.id];
    return {
      id: t.id,
      name: t.name || t.title,
      score: m ? `${Math.round(m.score)}%` : '—',
      scoreVal: m?.score ?? 0,
      failing: m ? `${m.failing_rules ?? 0}/${m.total_rules ?? 0}` : '—',
      rows: t.row_count ?? 0,
    };
  });

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Health
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <PanelGauge score={dqScore} size={72} label="DQ Score" />
      </Box>

      <Divider />

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

      {qualityRows.length > 0 && (
        <PanelTable
          dense
          title="Table Quality"
          columns={[
            { key: 'name', header: 'Table', width: '40%', render: (v) => <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{v}</Typography> },
            { key: 'score', header: 'DQ%', width: '16%', align: 'right', render: (v, row) => (
              <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: row.scoreVal >= 80 ? 'success.main' : row.scoreVal >= 60 ? 'warning.main' : 'error.main' }}>{v}</Typography>
            )},
            { key: 'failing', header: 'Rules', width: '16%', align: 'right' },
            { key: 'rows', header: 'Rows', width: '16%', align: 'right' },
          ]}
          rows={qualityRows}
          emptyText="No quality data available."
        />
      )}
    </Box>
  );
}

/* ── Lineage tab — upstream/downstream table dependencies (PanelTable) ────── */

function ModuleLineageTab({ tables, token }) {
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

      <PanelTable
        dense
        title={`Upstream (${upstream.length})`}
        columns={[
          { key: 'name', header: 'Source Table', width: '60%', render: (v) => <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{v}</Typography> },
          { key: 'type', header: 'Relation', width: '40%' },
        ]}
        rows={upstream.map((r) => ({ id: r.id, name: r.from_table_name || `Table #${r.from_table}`, type: r.relation_type || 'references' }))}
        emptyText="No upstream dependencies"
      />

      <PanelTable
        dense
        title={`Downstream (${downstream.length})`}
        columns={[
          { key: 'name', header: 'Consumer Table', width: '60%', render: (v) => <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{v}</Typography> },
          { key: 'type', header: 'Relation', width: '40%' },
        ]}
        rows={downstream.map((r) => ({ id: r.id, name: r.to_table_name || `Table #${r.to_table}`, type: r.relation_type || 'consumes' }))}
        emptyText="No downstream consumers"
      />
    </Box>
  );
}

/* ── Governance tab — policy status, lock state, access (PanelMetricRow + PanelTable) ── */

function ModuleGovernanceTab({ module, tables, token }) {
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

      <PanelMetricRow label="Org unit" value={module?.org_unit_name || module?.name} divider />
      <PanelMetricRow label="Last verified" value={fmtDate(lastVerified)} divider />
      <PanelMetricRow label="Tables" value={`${tables.length}`} divider />

      {relevantPolicies.length > 0 && (
        <PanelTable
          dense
          title={`Active Policies (${relevantPolicies.length})`}
          columns={[
            { key: 'name', header: 'Policy', width: '60%', render: (v) => (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                <ShieldIcon sx={{ fontSize: 14, color: 'secondary.main', flexShrink: 0 }} />
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>{v}</Typography>
              </Box>
            )},
            { key: 'scopeType', header: 'Scope', width: '20%' },
            { key: 'policyType', header: 'Type', width: '20%' },
          ]}
          rows={relevantPolicies.map((p) => ({ id: p.id, name: p.name, scopeType: p.scope_type || '—', policyType: p.policy_type || '—' }))}
          emptyText="No active policies."
        />
      )}
    </Box>
  );
}

/* ── Activity tab — chip filter + PanelTable ──────────────────────────────── */

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
      detail: e.action || e.description || e.event || 'Governance event',
      timestamp: e.timestamp || e.created_at,
      kind: 'governance',
    }));
    const actMapped = (activity || []).map((a) => ({ ...a, kind: detectActivityKind(a) }));
    const combined = [...actMapped, ...govMapped];
    combined.sort((a, b) => new Date(b.reported_at || b.timestamp || b.created_at || 0) - new Date(a.reported_at || a.timestamp || a.created_at || 0));
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
      <Box sx={{ mb: 1.5, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
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
      </Box>

      <PanelTable
        dense
        columns={[
          {
            key: 'kind',
            header: 'Type',
            width: '15%',
            render: (v) => {
              const cfg = ACTIVITY_KINDS[v] || ACTIVITY_KINDS.data_change;
              const Icon = cfg.Icon;
              return (
                <Chip
                  icon={<Icon sx={{ fontSize: 12 }} />}
                  label={cfg.label}
                  size="small"
                  color={cfg.color}
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.6rem' }}
                />
              );
            },
          },
          { key: 'detail', header: 'Detail', width: '60%', render: (v) => (
            <Typography sx={{ fontSize: '0.72rem' }}>{fmtActivityText(v)}</Typography>
          )},
          {
            key: 'when',
            header: 'When',
            width: '25%',
            align: 'right',
            render: (v) => (
              <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                {fmtDate(v)}
              </Typography>
            ),
          },
        ]}
        rows={filtered.map((item, i) => ({
          id: item.id ?? i,
          kind: item.kind,
          detail: item,
          when: item.reported_at || item.timestamp || item.created_at,
        }))}
        emptyText="No recent activity."
      />
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
  const [selectedTableId, setSelectedTableId] = useState(null);
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
      field: 'actions',
      headerName: '',
      width: 60,
      sortable: false,
      disableColumnMenu: true,
      renderCell: ({ row }) => (
        <Tooltip title="Open table data">
          <IconButton size="small" onClick={(e) => { e.stopPropagation(); navigate(`/carbon/my-data/${moduleId}/${row.id}`); }}>
            <VisibilityIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Tooltip>
      ),
    },
  ], [moduleId, navigate]);

  const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange, resetTab, toggleConfigPopup, saveConfig, panelConfigOpen, panelConfig } = useDetailPanel({
    tabs: [
      { label: 'Health',      description: 'Data quality overview across all tables in this source', render: () => <ModuleHealthTab module={module} tables={tables} token={token} /> },
      { label: 'Lineage',     description: 'Upstream and downstream data dependencies and factor provenance', render: () => <ModuleLineageTab tables={tables} token={token} /> },
      { label: 'Governance',  description: 'Access controls, verification status, and active policies', render: () => <ModuleGovernanceTab module={module} tables={tables} token={token} /> },
      { label: 'Activity',    description: 'Recent actions, calculations, and governance events for this source', render: () => <ModuleActivityTab activity={activity} token={token} /> },
    ],
    storageKey: 'moduleWorkspace:panelTab',
    configurable: true,
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
          subtitle={`${SCOPE_META[module?.scope]?.label || 'Scope'} — ${tables.length} tables, ${tables.reduce((sum, t) => sum + (t.row_count || 0), 0)} rows`}
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
              onRowClick={(params) => { setSelectedTableId(params.id); resetTab(); }}
            />
          )}
        </Box>
      ) }]}
      metricsPanel={metricsPanel}
      metricsTabs={metricsTabs}
      activeMetricsTab={activeMetricsTab}
      onMetricsTabChange={onMetricsTabChange}
      panelWidthKey="moduleWorkspace:panelWidth"
      panelConfigurable
      panelConfig={panelConfig}
      panelConfigOpen={panelConfigOpen}
      toggleConfigPopup={toggleConfigPopup}
      saveConfig={saveConfig}
      allPanelTabs={['Health', 'Lineage', 'Governance', 'Activity'].map((l) => ({ label: l }))}
    />
  );
}
