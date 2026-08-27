// src/inspector/tabs/rowDetailTabs.jsx
// Contextual Inspector tabs for a Data Row (entityType: 'row').
//
// Lifted out of RowDetailPage (ADR-0019 Phase C). Each tab is self-contained:
// it reads primary data from `context.payload` (fast-path { rowData, tableInfo,
// moduleInfo, calculations, tableId, rowId } supplied by the page) and
// self-fetches secondary data (DQ metrics) using its own token.
//
// `registerRowDetailInspectorTabs()` registers the three right-panel tabs with
// the global InspectorTabRegistry; it returns an unregister function.
/* eslint-disable react-refresh/only-export-components */

import React, { useEffect, useState } from 'react';
import { Box, Chip, CircularProgress, Alert, Typography } from '@mui/material';
import { useAuth } from '../../auth/AuthContext';
import { authFetch } from '../../api/api';
import { PanelTable } from '../../components/panel';
import { registerInspectorTab } from '../InspectorTabRegistry';
import DQMetricsTab from '../../pages/dataschema/metrics/DQMetricsTab';
import RelatedRecordsTab from '../../pages/dataschema/metrics/RelatedRecordsTab';

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

// ── Transform DQ API response to DQMetricsTab-compatible format ────────────

function transformDqResponse(apiData) {
  const rules = apiData?.active_rules || [];
  const completeness = apiData?.completeness_pct ?? 0;
  const fieldProfiles = apiData?.field_profiles || [];

  if (rules.length === 0) {
    return { status: 'unknown', passed_count: 0, total_count: 0, results: [], last_run: null, completeness_pct: completeness, row_count: apiData?.row_count ?? 0 };
  }

  const results = rules.map((rule) => {
    const fp = fieldProfiles.find((p) => p.data_field === rule.data_field);
    const passed = rule.latest_result?.passed ?? (rule.severity === 'info');
    return {
      rule_name: rule.rule_type + (rule.data_field_name ? ` · ${rule.data_field_name}` : ''),
      passed,
      severity: rule.severity,
      message: fp ? `Completeness: ${fp.completeness_pct?.toFixed(1)}%` : rule.rule_type,
    };
  });

  const passed_count = results.filter((r) => r.passed).length;
  const status = passed_count === results.length ? 'passed' : passed_count === 0 ? 'failed' : 'warning';

  return { status, passed_count, total_count: results.length, results, last_run: apiData?.last_run || null, completeness_pct: completeness, row_count: apiData?.row_count ?? 0 };
}

/* ── DQ Metrics tab — self-fetches rule evaluation results ─────────────── */

function RowDqTab({ context }) {
  const { token } = useAuth();
  const { rowId, tableId } = context?.payload || {};

  const [dqLoading, setDqLoading] = useState(false);
  const [dqError, setDqError] = useState(null);
  const [dqMetrics, setDQMetrics] = useState(null);

  useEffect(() => {
    if (!rowId || !tableId || !token) return;
    let cancelled = false;
    setDqLoading(true);
    setDqError(null);
    (async () => {
      try {
        let res = await authFetch(`dq/metrics/table/${tableId}/?row_id=${rowId}`, { token });
        if (!res.ok && res.status === 404)
          res = await authFetch(`dq/metrics/table/${tableId}/`, { token });
        if (res.ok) {
          const data = transformDqResponse(await res.json());
          if (!cancelled) setDQMetrics(data);
        } else {
          throw new Error(`Failed: ${res.status}`);
        }
      } catch (err) {
        if (!cancelled) setDqError(err.message || 'Failed to load DQ metrics');
      } finally {
        if (!cancelled) setDqLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [rowId, tableId, token]);

  if (dqLoading) {
    return (
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress size={24} />
      </Box>
    );
  }
  if (dqError) {
    return <Alert severity="warning" sx={{ fontSize: '0.75rem' }}>{dqError}</Alert>;
  }
  return <DQMetricsTab metrics={dqMetrics} rowId={rowId} tableId={tableId} token={token} />;
}

/* ── Lineage tab — emission provenance chain ─────────────────────────────── */

function RowLineageTab({ context }) {
  const calculations = context?.payload?.calculations || [];
  const SCOPE_COLOR = { 1: 'error', 2: 'warning', 3: 'info' };

  const totalTCO2e = calculations.reduce((sum, c) => sum + (Number(c.co2e_kg) || 0), 0) / 1000;

  return (
    <Box sx={{ p: 2 }}>
      <PanelTable
        title="Emission Lineage"
        subtitle={totalTCO2e > 0 ? `Total: ${totalTCO2e.toFixed(3)} tCO₂e` : undefined}
        columns={[
          {
            key: 'emission_factor_name',
            header: 'Factor',
            width: '35%',
            render: (_v, row) => (
              <Box>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>
                  {row.emission_factor__name || row.emission_factor_name || `Factor #${row.emission_factor_id}`}
                </Typography>
                {(row.emission_factor__code || row.emission_factor_code) && (
                  <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', fontFamily: 'monospace' }}>
                    {row.emission_factor__code || row.emission_factor_code}
                  </Typography>
                )}
              </Box>
            ),
          },
          {
            key: 'scope',
            header: 'Scope',
            width: '25%',
            render: (_v, row) => (
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {row.scope && (
                  <Chip label={`Scope ${row.scope}`} size="small" color={SCOPE_COLOR[row.scope] || 'default'}
                    sx={{ height: 2.5, fontSize: '0.65rem' }} />
                )}
                {row.category && (
                  <Chip label={row.category} size="small" variant="outlined"
                    sx={{ height: 2.5, fontSize: '0.65rem' }} />
                )}
              </Box>
            ),
          },
          {
            key: 'co2e_kg',
            header: 'Output',
            width: '40%',
            render: (_v, row) => (
              <Box>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: 'warning.main' }}>
                  {(Number(row.co2e_kg) / 1000).toFixed(3)} tCO₂e
                </Typography>
                <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>
                  {fmtDate(row.calculated_at)}
                </Typography>
              </Box>
            ),
          },
        ]}
        rows={calculations}
        emptyText="No calculations for this row. Run a calculation rule to see emission lineage."
      />
    </Box>
  );
}

/* ── Related tab — FK-linked records ─────────────────────────────────────── */

function RowRelatedTab({ context }) {
  const { token } = useAuth();
  const { rowId, tableId, rowData } = context?.payload || {};
  return <RelatedRecordsTab rowId={rowId} tableId={tableId} token={token} rowData={rowData} />;
}

/** Register all row tabs; returns an unregister function (effect cleanup). */
export function registerRowDetailInspectorTabs() {
  const unregister = [
    registerInspectorTab({
      id: 'row-dq',
      label: 'DQ Metrics',
      order: 10,
      matches: (ctx) => ctx?.entityType === 'row',
      render: (ctx) => <RowDqTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'row-lineage',
      label: 'Lineage',
      order: 20,
      matches: (ctx) => ctx?.entityType === 'row',
      render: (ctx) => <RowLineageTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'row-related',
      label: 'Related',
      order: 30,
      matches: (ctx) => ctx?.entityType === 'row',
      render: (ctx) => <RowRelatedTab context={ctx} />,
    }),
  ];
  return () => unregister.forEach((u) => u());
}
