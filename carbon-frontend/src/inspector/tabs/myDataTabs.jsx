// src/inspector/tabs/myDataTabs.jsx
// Contextual Inspector tabs for a My-Data source / org unit (entityType: 'myDataSource').
//
// Lifted out of MyDataPage (ADR-0019 Phase C). Each tab reads its primary data
// from `context.payload` fast-path ({ mod, activity } supplied by the page) and
// self-fetches secondary data (DQ metrics, asset profile, SBTi targets,
// governance events) using its own token.
//
// `registerMyDataSourceInspectorTabs()` registers all three tabs; returns an
// unregister function (use as effect cleanup).
/* eslint-disable react-refresh/only-export-components */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Divider,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import MemoryIcon from '@mui/icons-material/Memory';
import ShieldIcon from '@mui/icons-material/Shield';
import { useAuth } from '../../auth/AuthContext';
import { getOrgDQMetrics } from '../../api/dq';
import { fetchSBTiTargets } from '../../api/emissions-extended';
import { fetchAssetProfiles, fetchGovernanceEvents } from '../../api/catalog';
import { PanelGauge, PanelMetricRow } from '../../components/panel';
import { FONT } from '../../theme/themeTokens';
import { registerInspectorTab } from '../InspectorTabRegistry';

function fmtDate(v) {
  if (!v) return 'Never';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? 'Never' : d.toLocaleDateString();
}

/* ── Trust tab ──────────────────────────────────────────────────────────── */

function TrustTab({ context }) {
  const { token } = useAuth();
  const { mod } = context?.payload || {};
  const [dqMetrics, setDqMetrics] = useState(null);
  const [assetProfile, setAssetProfile] = useState(null);

  useEffect(() => {
    if (!mod?.id || !token) return;
    getOrgDQMetrics(token)
      .then(setDqMetrics)
      .catch(() => setDqMetrics(null));
    fetchAssetProfiles(token)
      .then((profiles) => {
        const match = (profiles || []).find(
          (p) => p.id === mod.id || p.source_id === mod.id || p.name === mod.name
        );
        setAssetProfile(match || null);
      })
      .catch(() => setAssetProfile(null));
  }, [mod?.id, mod?.name, token]);

  if (!mod) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a source to see trust metrics.
        </Typography>
      </Box>
    );
  }

  const dqScore = mod.quality_score ?? 0;
  const failingRules = dqMetrics?.failing_rules ?? (mod.quality_score != null && mod.quality_score < 60 ? '—' : 0);
  const isLocked = assetProfile?.governance?.locked ?? false;
  const lastVerified = assetProfile?.governance?.last_verified ?? null;
  const evidenceCount = assetProfile?.evidence_count ?? 0;

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.sectionTitle, letterSpacing: '0.08em' }}>
        Trust
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <PanelGauge score={dqScore} size={72} label="DQ Score" />
      </Box>

      <Divider />

      <Box>
        <PanelMetricRow label="Failing rules" value={`${failingRules}`} divider />
        <PanelMetricRow label="Locked" value={isLocked ? 'Yes' : 'No'} divider />
        <PanelMetricRow label="Last verified" value={fmtDate(lastVerified)} divider />
        <PanelMetricRow label="Evidence" value={`${evidenceCount} docs`} divider />
      </Box>
    </Box>
  );
}

/* ── Impact tab ──────────────────────────────────────────────────────────── */

function ImpactTab({ context }) {
  const { token } = useAuth();
  const theme = useTheme();
  const { mod } = context?.payload || {};
  const [sbtiTargets, setSbtiTargets] = useState([]);

  useEffect(() => {
    if (!mod?.id || !token) return;
    fetchSBTiTargets(token)
      .then((targets) => setSbtiTargets(Array.isArray(targets) ? targets : []))
      .catch(() => setSbtiTargets([]));
  }, [mod?.id, token]);

  if (!mod) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a source to see downstream impact.
        </Typography>
      </Box>
    );
  }

  const sbtiCount = sbtiTargets.filter(
    (t) =>
      t.org_unit_id === mod.id ||
      t.source_id === mod.id ||
      (t.org_unit_name && t.org_unit_name === mod.name)
  ).length;
  const rowCount = mod.row_count ?? 0;

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.sectionTitle, letterSpacing: '0.08em' }}>
        Impact
      </Typography>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.5,
          py: 1.5,
          flexWrap: 'wrap',
        }}
      >
        {[
          { label: 'Source', icon: <MemoryIcon sx={{ fontSize: '0.875rem' }} /> },
          { label: 'Tables', icon: null },
          { label: 'Calc', icon: <AssessmentIcon sx={{ fontSize: '0.875rem' }} /> },
          { label: 'Reports', icon: null },
        ].map((step, idx, arr) => (
          <React.Fragment key={step.label}>
            <Chip
              icon={step.icon}
              label={step.label}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 600, borderColor: theme.palette.divider }}
            />
            {idx < arr.length - 1 && (
              <Typography sx={{ ...FONT.cardTitle, color: 'text.disabled', mx: -0.25 }}>→</Typography>
            )}
          </React.Fragment>
        ))}
      </Box>

      <Divider />

      <Box>
        <PanelMetricRow label="SBTi targets" value={`${sbtiCount} reference${sbtiCount !== 1 ? 's' : ''} this org unit`} divider />
        <PanelMetricRow label="Calculations" value={`${rowCount} records linked`} divider />
        <PanelMetricRow label="Data consumers" value={(
          <Chip label="Carbon app" size="small" sx={{ fontWeight: 600 }} />
        )} divider />
      </Box>
    </Box>
  );
}

/* ── Activity tab ────────────────────────────────────────────────────────── */

const ACTIVITY_KINDS = {
  data_change: { label: 'Data change', color: 'info', Icon: MemoryIcon },
  dq_run: { label: 'DQ run', color: 'success', Icon: AssessmentIcon },
  governance: { label: 'Governance', color: 'secondary', Icon: ShieldIcon },
  calculation: { label: 'Calculation', color: 'warning', Icon: AssessmentIcon },
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
  const detail = (item.detail || item.message || item.event || item.activity_type || '').toLowerCase();
  if (detail.includes('governance') || detail.includes('lock') || detail.includes('policy') || detail.includes('approve')) return 'governance';
  if (detail.includes('dq') || detail.includes('quality') || detail.includes('check') || detail.includes('rule')) return 'dq_run';
  if (detail.includes('calc') || detail.includes('compute') || detail.includes('emission') || detail.includes('target')) return 'calculation';
  return 'data_change';
}

function ActivityTab({ context }) {
  const { token } = useAuth();
  const theme = useTheme();
  const { activity } = context?.payload || {};
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
    const actMapped = (activity || []).map((a) => ({
      ...a,
      kind: detectActivityKind(a),
    }));
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
              sx={{
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                '&:hover': { bgcolor: isActive ? undefined : theme.palette.action.hover },
              }}
            />
          );
        })}
      </Stack>

      {filtered.length === 0 ? (
        <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>No recent activity.</Typography>
      ) : (
        <Stack divider={<Divider flexItem />} spacing={0}>
          {filtered.map((item, i) => {
            const cfg = ACTIVITY_KINDS[item.kind] || ACTIVITY_KINDS.data_change;
            const Icon = cfg.Icon;
            return (
              <Box key={item.id ?? i} sx={{ py: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <Icon
                  sx={{
                    fontSize: '0.875rem',
                    mt: 0.25,
                    color: `${cfg.color}.main`,
                    flexShrink: 0,
                  }}
                />
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ ...FONT.cardTitle, lineHeight: 1.35 }}>
                    {fmtActivityText(item)}
                  </Typography>
                  <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', mt: 0.25 }}>
                    {fmtDate(item.reported_at || item.timestamp || item.created_at)}
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

/* ── Registration (contribution point) ───────────────────────────────────── */

/** Register all My-Data source tabs; returns an unregister function. */
export function registerMyDataSourceInspectorTabs() {
  const unregister = [
    registerInspectorTab({
      id: 'my-data-trust',
      label: 'Trust',
      order: 10,
      matches: (ctx) => ctx?.entityType === 'myDataSource',
      render: (ctx) => <TrustTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'my-data-impact',
      label: 'Impact',
      order: 20,
      matches: (ctx) => ctx?.entityType === 'myDataSource',
      render: (ctx) => <ImpactTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'my-data-activity',
      label: 'Activity',
      order: 30,
      matches: (ctx) => ctx?.entityType === 'myDataSource',
      render: (ctx) => <ActivityTab context={ctx} />,
    }),
  ];
  return () => unregister.forEach((u) => u());
}
