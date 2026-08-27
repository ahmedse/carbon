// File: src/pages/dataschema/metrics/DQMetricsTab.jsx
// DQ Metrics display with results and re-run button — uses PanelTable.

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Chip,
  Button,
  CircularProgress,
  Alert,
  Divider,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import RefreshIcon from '@mui/icons-material/Refresh';
import { authFetch } from '../../../api/api';
import { PanelTable } from '../../../components/panel';

function notify(message, type = 'info') {
  const event = new CustomEvent('notify', { detail: { message, type } });
  window.dispatchEvent(event);
}

export default function DQMetricsTab({ metrics, rowId, tableId, token: _token }) {
  const [running, setRunning] = useState(false);
  const [rerunError, setRerunError] = useState(null);

  const getStatusChip = (passed) => {
    if (passed) return <Chip icon={<CheckCircleIcon />} label="Pass" size="small" color="success" variant="outlined" sx={{ height: 20, fontSize: '0.68rem' }} />;
    return <Chip icon={<ErrorIcon />} label="Fail" size="small" color="error" variant="outlined" sx={{ height: 20, fontSize: '0.68rem' }} />;
  };

  const handleRerun = async () => {
    setRunning(true);
    setRerunError(null);
    try {
      const response = await authFetch('dq/run-validation/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: { data_table: tableId, row_id: rowId },
      });
      if (!response.ok) throw new Error(`Validation failed: ${response.status}`);
      notify('Validation run started', 'info');
      setTimeout(() => { window.location.reload(); }, 2000);
    } catch (err) {
      console.error('Rerun error:', err);
      setRerunError(err.message);
      notify(`Error: ${err.message}`, 'error');
    } finally {
      setRunning(false);
    }
  };

  if (!metrics) {
    return (
      <Alert severity="info" sx={{ fontSize: '0.85rem' }}>
        No DQ metrics available for this row
      </Alert>
    );
  }

  const status = metrics.status || 'unknown';
  const passed = metrics.passed_count || 0;
  const total = metrics.total_count || 0;
  const hasRules = total > 0;
  const results = metrics.results || [];
  const timestamp = metrics.last_run || null;

  const statusColor = status === 'passed' ? 'success' : status === 'failed' ? 'error' : 'warning';

  return (
    <Box>
      {/* Status badge + re-run */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 1.5,
          bgcolor: 'grey.50',
          borderRadius: 1,
          mb: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            label={hasRules ? `${passed}/${total} Checks Passed` : 'No rules'}
            color={hasRules ? statusColor : 'default'}
            size="small"
            variant="outlined"
          />
          {timestamp && (
            <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.7rem' }}>
              Last: {new Date(timestamp).toLocaleString()}
            </Typography>
          )}
        </Box>
        <Button
          startIcon={running ? <CircularProgress size={14} /> : <RefreshIcon sx={{ fontSize: '1rem' }} />}
          onClick={handleRerun}
          disabled={running}
          size="small"
          variant="outlined"
          sx={{ minWidth: 'auto', fontSize: '0.68rem', py: 0.25 }}
        >
          {running ? 'Running...' : 'Re-run'}
        </Button>
      </Box>

      {rerunError && (
        <Alert severity="error" sx={{ fontSize: '0.8rem', mb: 1.5 }}>
          {rerunError}
        </Alert>
      )}

      <Divider sx={{ mb: 1.5 }} />

      {/* Results table via PanelTable */}
      <PanelTable
        title="Validation Rules"
        subtitle={hasRules ? `${passed}/${total} passing` : undefined}
        columns={[
          {
            key: 'passed',
            header: 'Status',
            width: '25%',
            render: (v) => getStatusChip(v),
          },
          {
            key: 'rule_name',
            header: 'Rule',
            width: '35%',
            render: (v) => (
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>{v}</Typography>
            ),
          },
          {
            key: 'message',
            header: 'Detail',
            width: '40%',
            render: (v) => (
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                {v || '—'}
              </Typography>
            ),
          },
        ]}
        rows={results}
        emptyText="No validation rules configured for this table. Add rules in Catalog Studio to enable quality checks."
        loading={false}
      />
    </Box>
  );
}
