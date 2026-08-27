// src/inspector/tabs/moduleTabs.jsx
// Contextual Inspector tabs for a Data Product Module (entityType: 'module').
//
// These were lifted out of ModuleWorkspacePage (ADR-0019 Phase B). Each tab is
// self-contained: it reads its primary data from `context.payload` (fast-path
// { module, tables, activity } supplied by the page) and self-fetches secondary
// data (DQ metrics, relations, policies, governance events) using its own token.
//
// `registerModuleInspectorTabs()` registers all four tabs with the global
// InspectorTabRegistry; it returns an unregister function (use as effect cleanup).
//
// NOTE: this file intentionally mixes component definitions with a non-component
// export (`registerModuleInspectorTabs`), which degrades Fast Refresh. That is an
// accepted trade-off for a registry contribution module.
/* eslint-disable react-refresh/only-export-components */

import React, { useEffect, useMemo, useState } from 'react';
import { Box, Chip, Divider, LinearProgress, Typography } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import MemoryIcon from '@mui/icons-material/Memory';
import AssessmentIcon from '@mui/icons-material/Assessment';
import ShieldIcon from '@mui/icons-material/Shield';
import { useAuth } from '../../auth/AuthContext';
import { getTableDQMetrics } from '../../api/dq';
import {
  fetchAssetProfiles,
  fetchGovernancePolicies,
  fetchGovernanceEvents,
  fetchTableRelations,
} from '../../api/catalog';
import { PanelGauge, PanelMetricRow, PanelTable } from '../../components/panel';
import { registerInspectorTab } from '../InspectorTabRegistry';

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

/* ── Health tab — DQ gauge + per-table breakdown (PanelTable) ─────────────── */

function ModuleHealthTab({ context }) {
  const { token } = useAuth();
  const { module, tables = [] } = context?.payload || {};
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

function ModuleLineageTab({ context }) {
  const { token } = useAuth();
  const { tables = [] } = context?.payload || {};
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

function ModuleGovernanceTab({ context }) {
  const { token } = useAuth();
  const { module, tables = [] } = context?.payload || {};
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
          <LockIcon sx={{ fontSize: '1.75rem', color: 'error.main' }} />
        ) : (
          <LockOpenIcon sx={{ fontSize: '1.75rem', color: 'success.main' }} />
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
                <ShieldIcon sx={{ fontSize: '0.875rem', color: 'secondary.main', flexShrink: 0 }} />
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

function ModuleActivityTab({ context }) {
  const { token } = useAuth();
  const { activity = [] } = context?.payload || {};
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
                  icon={<Icon sx={{ fontSize: '0.75rem' }} />}
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

/* ── Registration (contribution point) ───────────────────────────────────── */

/** Register all module tabs; returns an unregister function (effect cleanup). */
export function registerModuleInspectorTabs() {
  const unregister = [
    registerInspectorTab({
      id: 'module-health',
      label: 'Health',
      order: 10,
      matches: (ctx) => ctx?.entityType === 'module',
      render: (ctx) => <ModuleHealthTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'module-lineage',
      label: 'Lineage',
      order: 20,
      matches: (ctx) => ctx?.entityType === 'module',
      render: (ctx) => <ModuleLineageTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'module-governance',
      label: 'Governance',
      order: 30,
      matches: (ctx) => ctx?.entityType === 'module',
      render: (ctx) => <ModuleGovernanceTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'module-activity',
      label: 'Activity',
      order: 40,
      matches: (ctx) => ctx?.entityType === 'module',
      render: (ctx) => <ModuleActivityTab context={ctx} />,
    }),
  ];
  return () => unregister.forEach((u) => u());
}
