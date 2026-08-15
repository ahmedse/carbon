// File: src/pages/dataschema/RowDetailPage.jsx
// Row detail page — enterprise three-column layout with EntityDetailShell.
// Main content: Overview, Edit, Evidence, History tabs.
// Right panel: DQ Metrics, Lineage, Related tabs.
// Fetches table + module context and calculations for meaningful header.

import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Chip,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import { authFetch } from '../../api/api';
import EntityDetailShell from '../../components/entity/EntityDetailShell';
import useDetailPanel from '../../components/entity/useDetailPanel';
import RowOverviewTab from './tabs/RowOverviewTab';
import RowEditTab from './tabs/RowEditTab';
import RowEvidenceTab from './tabs/RowEvidenceTab';
import DQMetricsTab from './metrics/DQMetricsTab';
import RelatedRecordsTab from './metrics/RelatedRecordsTab';
import { PanelTable } from '../../components/panel';

function notify(message, type = 'info') {
  const event = new CustomEvent('notify', { detail: { message, type } });
  window.dispatchEvent(event);
}

const SCOPE_META = { 1: { label: 'Scope 1', color: 'error' }, 2: { label: 'Scope 2', color: 'warning' }, 3: { label: 'Scope 3', color: 'info' } };

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

export default function RowDetailPage() {
  useDocumentTitle("Row Detail");
  const { tableId, rowId } = useParams();
  const { token, context } = useAuth();
  const navigate = useNavigate();

  const [rowData, setRowData] = useState(null);
  const [tableInfo, setTableInfo] = useState(null);
  const [moduleInfo, setModuleInfo] = useState(null);
  const [calculations, setCalculations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeMainTab, setActiveMainTab] = useState(() => {
    const saved = localStorage.getItem('carbonRowDetail:mainTab');
    return saved ? parseInt(saved, 10) : 0;
  });

  // DQ metrics state
  const [dqLoading, setDqLoading] = useState(false);
  const [dqError, setDqError] = useState(null);
  const [dqMetrics, setDQMetrics] = useState(null);
  const [dqFetched, setDqFetched] = useState(false);

  // ── Right panel via useDetailPanel ────────────────────────────────────
  const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange } = useDetailPanel({
    tabs: [
      { label: 'DQ Metrics', description: 'Data quality rule evaluation results for this row', render: () => (
        <Box sx={{ p: 2 }}>
          {dqLoading ? <CircularProgress size={24} /> : dqError ? <Alert severity="warning" sx={{ fontSize: '0.75rem' }}>{dqError}</Alert> : <DQMetricsTab metrics={dqMetrics} rowId={rowId} tableId={tableId} token={token} />}
        </Box>
      )},
      { label: 'Lineage', description: 'Emission factor provenance and calculation chain', render: () => <RowLineageTab rowId={rowId} tableId={tableId} token={token} calculations={calculations} /> },
      { label: 'Related', description: 'Records linked by foreign keys, temporal neighbors, and relations', render: () => <RelatedRecordsTab rowId={rowId} tableId={tableId} token={token} rowData={rowData} /> },
    ],
    storageKey: 'carbonRowDetail:panelTab',
    configurable: true,
  });

  // ── Listen for switchTab ────────────────────────────────────────────
  useEffect(() => {
    const handler = (e) => { if (e.detail?.tab != null) setActiveMainTab(e.detail.tab); };
    window.addEventListener('switchTab', handler);
    return () => window.removeEventListener('switchTab', handler);
  }, []);

  // ── Fetch row + table + module + calculations ──────────────────────
  useEffect(() => {
    const currentToken = token || localStorage.getItem('access');
    if (!currentToken || !rowId || !tableId) {
      setError('Authentication required. Please log in.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    (async () => {
      try {
        // 1. Fetch row
        const rowRes = await authFetch(`dataschema/rows/${rowId}/?data_table=${tableId}`, { token: currentToken });
        if (!rowRes.ok) throw new Error(`Row fetch failed: ${rowRes.status}`);
        const row = await rowRes.json();
        setRowData(row);

        // 2. Fetch table info
        try {
          const tblRes = await authFetch(`dataschema/tables/?id=${tableId}`, { token: currentToken });
          if (tblRes.ok) {
            const tbls = await tblRes.json();
            const tbl = Array.isArray(tbls) ? tbls.find(t => String(t.id) === String(tableId)) : tbls;
            if (tbl) {
              setTableInfo(tbl);
              // Try to get module from context
              const allModules = context?.modules || [];
              const mod = allModules.find(m => String(m.id) === String(tbl.module_id || tbl.module));
              if (mod) setModuleInfo(mod);
            }
          }
        } catch { /* non-critical */ }

        // 3. Fetch calculations for this row
        try {
          const calcRes = await authFetch(`carbon/calculations/?data_row_id=${rowId}`, { token: currentToken });
          if (calcRes.ok) {
            const calcData = await calcRes.json();
            setCalculations(Array.isArray(calcData.results) ? calcData.results : (Array.isArray(calcData) ? calcData : []));
          }
        } catch { /* non-critical */ }

      } catch (err) {
        setError(err.message || 'Failed to load row data');
        notify(`Error: ${err.message}`, 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, [token, rowId, tableId, context?.modules]);

  // ── Lazy-load DQ metrics on first mount (tab 0 is default) ───────────
  useEffect(() => {
    if (!dqFetched && rowId && tableId && token) {
      setDqLoading(true);
      setDqError(null);
      (async () => {
        try {
          let res = await authFetch(`dq/metrics/table/${tableId}/?row_id=${rowId}`, { token });
          if (!res.ok && res.status === 404)
            res = await authFetch(`dq/metrics/table/${tableId}/`, { token });
          if (res.ok) setDQMetrics(transformDqResponse(await res.json()));
          else throw new Error(`Failed: ${res.status}`);
        } catch (err) {
          setDqError(err.message || 'Failed to load DQ metrics');
        } finally {
          setDqLoading(false);
          setDqFetched(true);
        }
      })();
    }
  }, [rowId, tableId, token, dqFetched]);

  // ── Refresh ─────────────────────────────────────────────────────────
  const handleRefresh = async () => {
    const currentToken = token || localStorage.getItem('access');
    try {
      const res = await authFetch(`dataschema/rows/${rowId}/?data_table=${tableId}`, { token: currentToken });
      if (res.ok) setRowData(await res.json());
    } catch (err) {
      notify(`Refresh error: ${err.message}`, 'error');
    }
  };

  const handleClose = () => navigate(-1);

  // ── Computed display values ─────────────────────────────────────────
  const rowDisplayName = useMemo(() => {
    if (!rowData) return 'Row Details';
    const v = rowData.values || {};
    const nameFields = ['name', 'title', 'building', 'building_id', 'meter_id', 'supplier', 'period_month', 'period'];
    for (const f of nameFields) {
      if (v[f] != null && v[f] !== '') return `${v[f]}`;
    }
    return `Row #${rowData.id}`;
  }, [rowData]);

  const tableDisplayName = tableInfo?.title || tableInfo?.name || `Table #${tableId}`;
  const moduleDisplayName = moduleInfo?.name || '—';
  const scope = moduleInfo?.scope;
  const totalCo2e = calculations.reduce((sum, c) => sum + (Number(c.co2e_kg) || 0), 0);

  const fieldData = useMemo(() => {
    if (!rowData) return {};
    const values = rowData.values || {};
    if (Object.keys(values).length > 0) return values;
    const skip = new Set(['id', 'data_table', 'is_archived', 'version', 'values', 'created_at', 'updated_at', 'created_by', 'updated_by']);
    return Object.fromEntries(Object.entries(rowData).filter(([k]) => !skip.has(k)));
  }, [rowData]);

  const handleDownload = () => {
    const keys = Object.keys(fieldData);
    const csv = `${keys.join(',')}\n${keys.map(k => {
      const v = fieldData[k];
      return typeof v === 'string' && v.includes(',') ? `"${v.replace(/"/g, '""')}"` : v;
    }).join(',')}`;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `row-${rowId}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  // ── Loading / error states ──────────────────────────────────────────
  if (loading) return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <CircularProgress />
    </Box>
  );
  if (error) return (
    <Box sx={{ p: 3 }}>
      <Alert severity="error"><strong>Error:</strong> {error}</Alert>
      <Box sx={{ mt: 2 }}><Chip label="← Back" onClick={handleClose} variant="outlined" /></Box>
    </Box>
  );
  if (!rowData) return (
    <Box sx={{ p: 3 }}>
      <Alert severity="warning">Row not found</Alert>
      <Box sx={{ mt: 2 }}><Chip label="← Back" onClick={handleClose} variant="outlined" /></Box>
    </Box>
  );

  // ── Header ──────────────────────────────────────────────────────────
  const scopeMeta = SCOPE_META[scope] || null;

  const header = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minHeight: 44 }}>
      <IconButton size="small" onClick={handleClose} sx={{ flexShrink: 0 }}>
        <ArrowBackIcon sx={{ fontSize: 18 }} />
      </IconButton>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, lineHeight: 1.3 }} noWrap>
          {rowDisplayName}
        </Typography>
        <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', lineHeight: 1.2 }} noWrap>
          {tableDisplayName} · {moduleDisplayName}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexShrink: 0 }}>
        {scopeMeta && <Chip label={scopeMeta.label} size="small" color={scopeMeta.color} sx={{ height: 20, fontSize: '0.68rem' }} />}
        {totalCo2e > 0 && <Chip label={`${(totalCo2e / 1000).toFixed(2)} tCO₂e`} size="small" color="warning" variant="filled" sx={{ height: 20, fontSize: '0.68rem' }} />}
      </Box>
      <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
        <Tooltip title="Switch to Edit tab">
          <IconButton size="small" onClick={() => { setActiveMainTab(1); localStorage.setItem('carbonRowDetail:mainTab', 1); }}>
            <EditIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Download CSV">
          <IconButton size="small" onClick={handleDownload}><DownloadIcon sx={{ fontSize: 16 }} /></IconButton>
        </Tooltip>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={handleRefresh}><RefreshIcon sx={{ fontSize: 16 }} /></IconButton>
        </Tooltip>
      </Box>
    </Box>
  );

  // ── Tabs ────────────────────────────────────────────────────────────
  const mainTabs = [
    { label: 'Overview',  render: () => <RowOverviewTab rowData={rowData} tableInfo={tableInfo} moduleInfo={moduleInfo} calculations={calculations} onRefresh={handleRefresh} onClose={handleClose} /> },
    { label: 'Edit',      render: () => <RowEditTab rowData={rowData} setRowData={setRowData} tableId={tableId} rowId={rowId} token={token} onClose={handleClose} /> },
    { label: 'Evidence',  render: () => <RowEvidenceTab rowId={rowId} tableId={tableId} token={token} rowData={rowData} /> },
    { label: 'History',   render: () => <RowHistoryTab rowId={rowId} tableId={tableId} token={token} /> },
  ];

  return (
    <EntityDetailShell
      header={header}
      mainTabs={mainTabs}
      activeMainTab={activeMainTab}
      onMainTabChange={(_event, next) => { setActiveMainTab(next); localStorage.setItem('carbonRowDetail:mainTab', next); }}
      metricsPanel={metricsPanel}
      metricsTabs={metricsTabs}
      activeMetricsTab={activeMetricsTab}
      onMetricsTabChange={onMetricsTabChange}
      panelWidthKey="carbonRowDetail:panelWidth"
    />
  );
}

// ── Transform DQ API response to DQMetricsTab-compatible format ─────────

function transformDqResponse(apiData) {
  const rules = apiData?.active_rules || [];
  const completeness = apiData?.completeness_pct ?? 0;
  const fieldProfiles = apiData?.field_profiles || [];

  if (rules.length === 0) {
    return { status: 'unknown', passed_count: 0, total_count: 0, results: [], last_run: null, completeness_pct: completeness, row_count: apiData?.row_count ?? 0 };
  }

  const results = rules.map((rule) => {
    const fp = fieldProfiles.find(p => p.data_field === rule.data_field);
    // Use DQResult pass/fail if available, else infer from severity
    const passed = rule.latest_result?.passed ?? (rule.severity === 'info');
    return {
      rule_name: rule.rule_type + (rule.data_field_name ? ` · ${rule.data_field_name}` : ''),
      passed,
      severity: rule.severity,
      message: fp ? `Completeness: ${fp.completeness_pct?.toFixed(1)}%` : rule.rule_type,
    };
  });

  const passed_count = results.filter(r => r.passed).length;
  const status = passed_count === results.length ? 'passed' : passed_count === 0 ? 'failed' : 'warning';

  return { status, passed_count, total_count: results.length, results, last_run: apiData?.last_run || null, completeness_pct: completeness, row_count: apiData?.row_count ?? 0 };
}

// ── Row History Tab (inline) ──────────────────────────────────────────────

function RowHistoryTab({ rowId, tableId, token }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await authFetch(`carbon/calculation-audits/?data_table=${tableId}`, { token });
        if (res.ok) {
          const data = await res.json();
          const results = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
          setEvents(results.map(e => ({
            id: e.id,
            action: e.rule_name || (e.trigger_type === 'batch' ? 'Batch calc' : e.trigger_type === 'single' ? 'Rule calc' : 'Calc update'),
            description: [
              e.rule_name ? `${e.rule_name}` : '',
              e.triggered_by_name ? `by ${e.triggered_by_name}` : '',
              e.created_count ? `${e.created_count} created` : '',
              e.skipped_count ? `${e.skipped_count} skipped` : '',
              e.error_count ? `${e.error_count} errors` : '',
            ].filter(Boolean).join(' · '),
            timestamp: e.triggered_at || e.timestamp || e.created_at || e.performed_at,
            kind: 'calc',
          })));
        }
      } catch { /* ok if empty */ }
      setLoading(false);
    })();
  }, [token, rowId, tableId]);

  const total = events.length;
  const paged = events.slice((page - 1) * pageSize, page * pageSize);

  const KIND_CHIP = {
    calc: { label: 'Calc', color: 'warning' },
    data: { label: 'Data', color: 'info' },
    dq: { label: 'DQ', color: 'success' },
    gov: { label: 'Gov', color: 'secondary' },
  };

  return (
    <PanelTable
      title="Activity Log"
      columns={[
        {
          key: 'kind',
          header: 'Type',
          width: '15%',
          render: (v) => {
            const cfg = KIND_CHIP[v] || KIND_CHIP.data;
            return <Chip label={cfg.label} size="small" color={cfg.color}
              sx={{ height: 20, fontSize: '0.65rem' }} />;
          },
        },
        {
          key: 'action',
          header: 'Detail',
          width: '55%',
          render: (_v, row) => (
            <Box>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>
                {row.action || 'event'}
              </Typography>
              {row.description && (
                <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                  {row.description}
                </Typography>
              )}
            </Box>
          ),
        },
        {
          key: 'timestamp',
          header: 'When',
          width: '30%',
          align: 'right',
          render: (v) => (
            <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
              {fmtDate(v)}
            </Typography>
          ),
        },
      ]}
      rows={paged}
      emptyText="No history recorded for this row yet. Changes and calculations are logged when data is edited or recalculated."
      loading={loading}
      pagination={total > pageSize ? { page, pageSize, total, onChange: setPage } : null}
    />
  );
}

// ── Row Lineage Tab ─────────────────────────────────────────────────
// Shows emission provenance chain: Factor → Scope → Category → CO₂e output
function RowLineageTab({ calculations }) {
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
                    sx={{ height: 20, fontSize: '0.65rem' }} />
                )}
                {row.category && (
                  <Chip label={row.category} size="small" variant="outlined"
                    sx={{ height: 20, fontSize: '0.65rem' }} />
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
