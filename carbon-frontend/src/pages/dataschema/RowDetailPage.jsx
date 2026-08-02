// File: src/pages/dataschema/RowDetailPage.jsx
// Row detail page — enterprise three-column layout with EntityDetailShell.
// Main content: Overview, Edit, Evidence tabs.
// Right panel: DQ Metrics, Lineage, Related tabs.

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import CloseIcon from '@mui/icons-material/Close';
import { useAuth } from '../../auth/AuthContext';
import { API_BASE_URL, API_ROUTES } from '../../config';
import { apiFetch, authFetch } from '../../api/api';
import EntityDetailShell from '../../components/entity/EntityDetailShell';
import PageHeader from '../../components/Page/PageHeader';
import RowOverviewTab from './tabs/RowOverviewTab';
import RowEditTab from './tabs/RowEditTab';
import RowEvidenceTab from './tabs/RowEvidenceTab';
import DQMetricsTab from './metrics/DQMetricsTab';
import DataLineageTab from './metrics/DataLineageTab';
import RelatedRecordsTab from './metrics/RelatedRecordsTab';

function notify(message, type = 'info') {
  const event = new CustomEvent('notify', { detail: { message, type } });
  window.dispatchEvent(event);
}

export default function RowDetailPage() {
  useDocumentTitle("Row Detail");
  const { tableId, rowId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [rowData, setRowData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeMainTab, setActiveMainTab] = useState(() => {
    const saved = localStorage.getItem('carbonRowDetail:mainTab');
    return saved ? parseInt(saved, 10) : 0;
  });
  // DQ metrics state (moved from RowMetricsPanel)
  const [dqLoading, setDqLoading] = useState(false);
  const [dqError, setDqError] = useState(null);
  const [dqMetrics, setDQMetrics] = useState(null);
  const [dqFetched, setDqFetched] = useState(false);

  // Listen for switchTab event from RowOverviewTab
  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.tab != null) setActiveMainTab(e.detail.tab);
    };
    window.addEventListener('switchTab', handler);
    return () => window.removeEventListener('switchTab', handler);
  }, []);

  // ── Fetch row data ─────────────────────────────────────────────────

  useEffect(() => {
    const fetchRowData = async () => {
      let currentToken = token || localStorage.getItem('access');
      if (!currentToken || !rowId || !tableId) {
        setError('Authentication required. Please log in.');
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const rowData = await apiFetch(`dataschema/rows/${rowId}/?data_table=${tableId}`, { method: 'GET', token: currentToken }); // fetch row data
        setRowData(rowData);
      } catch (err) {
        setError(err.message || 'Failed to load row data');
        notify(`Error: ${err.message}`, 'error');
      } finally {
        setLoading(false);
      }
    };
    fetchRowData();
  }, [token, rowId, tableId]);

  // ── Lazy-load DQ metrics when DQ tab is selected ───────────────────

  const handleMetricsTabChange = (_event, newValue) => {
    // Only fetch when DQ Metrics tab (index 0) is selected
    if (newValue === 0 && !dqFetched && rowId && tableId) {
      setDqLoading(true);
      setDqError(null);
      (async () => {
        try {
          let res = await authFetch(`dq/metrics/table/${tableId}/?row_id=${rowId}`, { method: 'GET', token });
          if (!res.ok && res.status === 404) {
            res = await authFetch(`dq/metrics/table/${tableId}/`, { method: 'GET', token });
          }
          if (res.ok) {
            setDQMetrics(await res.json());
          } else {
            throw new Error(`Failed: ${res.status}`);
          }
        } catch (err) {
          setDqError(err.message || 'Failed to load DQ metrics');
        } finally {
          setDqLoading(false);
          setDqFetched(true);
        }
      })();
    }
  };

  // ── Row refresh ────────────────────────────────────────────────────

  const handleRefresh = async () => {
    let currentToken = token || localStorage.getItem('access');
    try {
      const rowData = await apiFetch(`dataschema/rows/${rowId}/?data_table=${tableId}`, { method: 'GET', token: currentToken }); // refresh row
      setRowData(rowData);
    } catch (err) {
      notify(`Refresh error: ${err.message}`, 'error');
    }
  };

  const handleClose = () => navigate(-1);

  // ── Row display name ───────────────────────────────────────────────

  const getRowDisplayName = () => {
    if (!rowData) return 'Row Details';
    const nameFields = ['name', 'title', 'building', 'id', 'building_id'];
    for (const field of nameFields) {
      if (rowData[field]) return `${field.replace(/_/g, ' ')}: ${rowData[field]}`;
    }
    return rowData.id ? `Row #${rowData.id}` : 'Row Details';
  };

  // ── Loading / error states ─────────────────────────────────────────

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', bgcolor: 'background.default' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error"><strong>Error loading row:</strong> {error}</Alert>
        <Box sx={{ mt: 2 }}><button onClick={handleClose}>← Back to list</button></Box>
      </Box>
    );
  }

  if (!rowData) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Row not found</Alert>
        <Box sx={{ mt: 2 }}><button onClick={handleClose}>← Back to list</button></Box>
      </Box>
    );
  }

  // ── Tab definitions for EntityDetailShell ──────────────────────────

  const header = (
    <PageHeader
      title={getRowDisplayName()}
      subtitle={`Table: ${tableId}`}
      actions={
        <IconButton size="small" onClick={handleClose} sx={{ p: 0.5 }}>
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      }
    />
  );

  const mainTabs = [
    { label: 'Overview', render: () => <RowOverviewTab rowData={rowData} onRefresh={handleRefresh} onClose={handleClose} /> },
    { label: 'Edit', render: () => <RowEditTab rowData={rowData} setRowData={setRowData} tableId={tableId} rowId={rowId} token={token} onClose={handleClose} /> },
    { label: 'Evidence', render: () => <RowEvidenceTab rowId={rowId} token={token} /> },
  ];

  const metricsTabs = [
    {
      label: 'DQ Metrics',
      render: () => (
        <Box sx={{ p: 2 }}>
          {dqLoading ? <CircularProgress size={24} /> : dqError ? <Alert severity="warning" sx={{ fontSize: '0.85rem' }}>{dqError}</Alert> : <DQMetricsTab metrics={dqMetrics} rowId={rowId} tableId={tableId} token={token} />}
        </Box>
      ),
    },
    { label: 'Lineage', render: () => <DataLineageTab rowId={rowId} /> },
    { label: 'Related', render: () => <RelatedRecordsTab rowId={rowId} /> },
  ];

  return (
    <EntityDetailShell
      header={header}
      mainTabs={mainTabs}
      activeMainTab={activeMainTab}
      onMainTabChange={(_event, next) => { setActiveMainTab(next); localStorage.setItem('carbonRowDetail:mainTab', next); }}
      metricsPanel={<></>}
      metricsTabs={metricsTabs}
      onMetricsTabChange={handleMetricsTabChange}
      panelWidthKey="carbonRowDetail:panelWidth"
    />
  );
}
