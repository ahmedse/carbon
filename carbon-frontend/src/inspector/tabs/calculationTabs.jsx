// src/inspector/tabs/calculationTabs.jsx
// Contextual Inspector tabs for an emission Calculation run (entityType: 'calculation').
//
// Lifted out of CalculationsPage (ADR-0019 Phase C). The page supplies
// `payload.entityData` = the selected calculation (fast-path); each tab renders
// that data directly, no refetch. Also re-exports the small presentation helpers
// (ScopeBadge / StatusChip / fmtDate / fmtNum / STATUS_CFG) that the page's
// DataGrid still uses, so there is a single source of truth for them.
//
// NOTE: this file intentionally mixes component definitions with non-component
// exports, which degrades Fast Refresh. Accepted trade-off for a registry
// contribution module.
/* eslint-disable react-refresh/only-export-components */

import React from 'react';
import { Box, Chip, LinearProgress, Typography, useTheme } from '@mui/material';
import {
  CheckCircleOutline as VerifiedIcon,
  ErrorOutline as FailedIcon,
  HelpOutline as PendingIcon,
  Schedule as ScheduledIcon,
} from '@mui/icons-material';
import { registerInspectorTab } from '../InspectorTabRegistry';
import { FONT } from '../../theme/themeTokens';

// ── Scope config ─────────────────────────────────────────────────────────

const SCOPE_CFG = {
  1: { label: 'Scope 1', palette: 'success' },
  2: { label: 'Scope 2', palette: 'info' },
  3: { label: 'Scope 3', palette: 'warning' },
};

// ── Status config (exported — CalculationsPage filter dropdown uses it) ────

export const STATUS_CFG = {
  draft:      { label: 'Draft',      palette: 'default', Icon: PendingIcon },
  pending:    { label: 'Pending',    palette: 'warning', Icon: ScheduledIcon },
  calculated: { label: 'Calculated', palette: 'success', Icon: VerifiedIcon },
  failed:     { label: 'Failed',     palette: 'error',   Icon: FailedIcon },
  verified:   { label: 'Verified',   palette: 'info',    Icon: VerifiedIcon },
  rejected:   { label: 'Rejected',   palette: 'error',   Icon: FailedIcon },
};

// ── Helpers (exported — CalculationsPage DataGrid reuses them) ────────────

export function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function fmtNum(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function ScopeBadge({ value }) {
  const theme = useTheme();
  const cfg = SCOPE_CFG[value] || SCOPE_CFG[1];
  const p = theme.palette[cfg.palette];
  return (
    <Chip
      label={cfg.label}
      size="small"
      sx={{
        height: 2.5,
        ...FONT.body,
        fontWeight: 700,
        bgcolor: p?.[50] || (p?.light + '30'),
        color: p?.dark || p?.main,
        border: 'none',
        '& .MuiChip-label': { px: 1 },
      }}
    />
  );
}

export function StatusChip({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.draft;
  const Icon = cfg.Icon;
  return (
    <Chip
      icon={<Icon sx={{ fontSize: '0.8125rem !important' }} />}
      label={cfg.label}
      size="small"
      color={cfg.palette === 'default' ? undefined : cfg.palette}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: 0.5 } }}
    />
  );
}

/* ── Overview tab — calculation metadata ─────────────────────────────────── */

function CalculationOverviewTab({ context }) {
  const calc = context?.payload?.entityData;

  if (!calc) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
          Select a calculation to view details.
        </Typography>
      </Box>
    );
  }

  const details = [
    { label: 'Period',           value: calc.period_name || calc.period || '—' },
    { label: 'Scope',            value: <ScopeBadge value={calc.scope} /> },
    { label: 'Status',           value: <StatusChip status={calc.status} /> },
    { label: 'Total tCO₂e',      value: fmtNum(calc.total_emissions || calc.total_co2e) },
    { label: 'Rule Used',        value: calc.rule_name || calc.rule || '—' },
    { label: 'Rule Version',     value: calc.rule_version || '—' },
    { label: 'Org Unit',         value: calc.org_unit_name || calc.org_unit || '—' },
    { label: 'Data Sources',     value: calc.data_source_count != null ? String(calc.data_source_count) : '—' },
    { label: 'Rows Processed',   value: calc.rows_processed != null ? String(calc.rows_processed) : '—' },
    { label: 'Last Calculated',  value: fmtDate(calc.last_calculated || calc.updated_at) },
    { label: 'Calculated By',    value: calc.calculated_by_name || calc.calculated_by || '—' },
  ];

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography sx={{ ...FONT.sectionTitle, color: 'text.secondary' }}>
        Calculation Metadata
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 0.5 }}>
        {details.map(({ label, value }) => (
          <Box
            key={label}
            sx={{
              display: 'grid',
              gridTemplateColumns: '120px 1fr',
              gap: 1,
              py: 0.75,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{label}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
              {typeof value === 'string' ? (
                <Typography sx={{ ...FONT.body, fontWeight: 600, color: 'text.primary' }}>{value}</Typography>
              ) : value}
            </Box>
          </Box>
        ))}
      </Box>

      {calc.traceability_notes && (
        <Box sx={{ pt: 1 }}>
          <Typography sx={{ ...FONT.sectionTitle, color: 'text.secondary', mb: 1 }}>
            Traceability
          </Typography>
          <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>{calc.traceability_notes}</Typography>
        </Box>
      )}
    </Box>
  );
}

/* ── Data Quality tab — DQ metrics ───────────────────────────────────────── */

function CalculationQualityTab({ context }) {
  const calc = context?.payload?.entityData;

  if (!calc) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
          Select a calculation to view data quality metrics.
        </Typography>
      </Box>
    );
  }

  const dq = calc.data_quality || {};
  const completeness = dq.completeness_score ?? calc.dq_completeness;
  const accuracy = dq.accuracy_score ?? calc.dq_accuracy;
  const timeliness = dq.timeliness_score ?? calc.dq_timeliness;

  const metrics = [
    { label: 'Completeness', value: completeness, good: 80, warn: 60 },
    { label: 'Accuracy',     value: accuracy,     good: 80, warn: 60 },
    { label: 'Timeliness',   value: timeliness,   good: 80, warn: 60 },
  ];

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography sx={{ ...FONT.sectionTitle, color: 'text.secondary' }}>
        Data Quality Metrics
      </Typography>
      {metrics.every(m => m.value == null) ? (
        <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
          No quality metrics available for this calculation.
        </Typography>
      ) : (
        metrics.map(({ label, value, good, warn }) => {
          const pct = value != null ? Math.round(value) : null;
          let color = 'text.secondary';
          if (pct != null) {
            color = pct >= good ? 'success.main' : pct >= warn ? 'warning.main' : 'error.main';
          }
          return (
            <Box key={label}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{label}</Typography>
                <Typography sx={{ ...FONT.body, fontWeight: 700, color }}>{pct != null ? `${pct}%` : 'N/A'}</Typography>
              </Box>
              {pct != null && (
                <LinearProgress
                  variant="determinate"
                  value={pct}
                  sx={{
                    height: 0.75,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: color,
                    },
                  }}
                />
              )}
            </Box>
          );
        })
      )}

      {calc.dq_issues && calc.dq_issues.length > 0 && (
        <Box sx={{ pt: 1 }}>
          <Typography sx={{ ...FONT.body, fontWeight: 700, color: 'error.main', mb: 1 }}>
            {calc.dq_issues.length} Issue{calc.dq_issues.length > 1 ? 's' : ''}
          </Typography>
          {calc.dq_issues.map((issue, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, py: 0.5, alignItems: 'flex-start' }}>
              <Box sx={{ width: 0.75, height: 0.75, borderRadius: '50%', bgcolor: 'error.main', mt: 0.5, flexShrink: 0 }} />
              <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{issue}</Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

/* ── Registration (contribution point) ───────────────────────────────────── */

/** Register the calculation inspector tabs; returns an unregister function. */
export function registerCalculationInspectorTabs() {
  const unregister = [
    registerInspectorTab({
      id: 'calculation-overview',
      label: 'Overview',
      order: 10,
      matches: (ctx) => ctx?.entityType === 'calculation',
      render: (ctx) => <CalculationOverviewTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'calculation-quality',
      label: 'Data Quality',
      order: 20,
      matches: (ctx) => ctx?.entityType === 'calculation',
      render: (ctx) => <CalculationQualityTab context={ctx} />,
    }),
  ];
  return () => unregister.forEach((u) => u());
}
