// File: src/pages/dataschema/RowDetailPage.jsx
// Row detail page — main content tabs (Overview, Edit, Evidence, History).
// Right panel (DQ Metrics, Lineage, Related) now lives in the global
// contextual inspector drawer (see inspector/tabs/rowDetailTabs.jsx).
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
  Tab,
  Tabs,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import { authFetch } from '../../api/api';
import RowOverviewTab from './tabs/RowOverviewTab';
import RowEditTab from './tabs/RowEditTab';
import RowEvidenceTab from './tabs/RowEvidenceTab';
import { PanelTable } from '../../components/panel';
import { useNotes } from '../../notes/NotesContext';
import { registerRowDetailInspectorTabs } from '../../inspector/tabs/rowDetailTabs';

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

  // ── Contextual Inspector (global drawer) ────────────────────────────
  const { setContexts } = useNotes();

  // Register the row tabs once; unregister on unmount.
  useEffect(() => registerRowDetailInspectorTabs(), []);

  // Expose this row as the active inspector context with a payload fast-path
  // ({ rowData, tableInfo, moduleInfo, calculations, tableId, rowId }).
  const inspectorContext = useMemo(
    () => [{
      entityType: 'row',
      entityId: rowId,
      label: rowDisplayName,
      payload: { rowData, tableInfo, moduleInfo, calculations, tableId, rowId },
    }],
    [rowDisplayName, rowData, tableInfo, moduleInfo, calculations, tableId, rowId],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

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
        <ArrowBackIcon sx={{ fontSize: '1.125rem' }} />
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
        {scopeMeta && <Chip label={scopeMeta.label} size="small" color={scopeMeta.color} sx={{ height: 2.5, fontSize: '0.68rem' }} />}
        {totalCo2e > 0 && <Chip label={`${(totalCo2e / 1000).toFixed(2)} tCO₂e`} size="small" color="warning" variant="filled" sx={{ height: 2.5, fontSize: '0.68rem' }} />}
      </Box>
      <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
        <Tooltip title="Switch to Edit tab">
          <IconButton size="small" onClick={() => { setActiveMainTab(1); localStorage.setItem('carbonRowDetail:mainTab', 1); }}>
            <EditIcon sx={{ fontSize: '1rem' }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Download CSV">
          <IconButton size="small" onClick={handleDownload}><DownloadIcon sx={{ fontSize: '1rem' }} /></IconButton>
        </Tooltip>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={handleRefresh}><RefreshIcon sx={{ fontSize: '1rem' }} /></IconButton>
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
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
      <Box sx={{ bgcolor: 'white', px: 2, pt: 1.5, pb: 0 }}>{header}</Box>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderTop: 1, borderColor: 'divider' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
          <Tabs
            value={activeMainTab}
            onChange={(_event, next) => { setActiveMainTab(next); localStorage.setItem('carbonRowDetail:mainTab', next); }}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              minHeight: 36,
              '& .MuiTab-root': { textTransform: 'none', fontSize: '0.78rem', minHeight: 36, py: 0.5 },
            }}
          >
            {mainTabs.map((tab, idx) => <Tab key={idx} label={tab.label} />)}
          </Tabs>
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'white' }}>
          {mainTabs[activeMainTab]?.render?.()}
        </Box>
      </Box>
    </Box>
  );
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
              sx={{ height: 2.5, fontSize: '0.65rem' }} />;
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
