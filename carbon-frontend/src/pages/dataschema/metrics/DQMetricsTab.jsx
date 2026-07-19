// File: src/pages/dataschema/metrics/DQMetricsTab.jsx
// DQ Metrics display with results and re-run button

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Chip,
  Stack,
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

function notify(message, type = 'info') {
  const event = new CustomEvent('notify', { detail: { message, type } });
  window.dispatchEvent(event);
}

export default function DQMetricsTab({ metrics, rowId, tableId, token }) {
  const [running, setRunning] = useState(false);
  const [rerunError, setRerunError] = useState(null);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'passed':
        return <CheckCircleIcon sx={{ color: '#4caf50', mr: 1 }} />;
      case 'failed':
        return <ErrorIcon sx={{ color: '#f44336', mr: 1 }} />;
      case 'warning':
        return <WarningIcon sx={{ color: '#ff9800', mr: 1 }} />;
      default:
        return null;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'passed':
        return 'success';
      case 'failed':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'default';
    }
  };

  const handleRerun = async () => {
    setRunning(true);
    setRerunError(null);

    try {
      const response = await authFetch(`dq/run-validation/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: {
          data_table: tableId,
          row_id: rowId,
        },
      });

      if (!response.ok) {
        throw new Error(`Validation failed: ${response.status}`);
      }

      notify('Validation run started', 'info');
      // Optionally refetch metrics after a delay
      setTimeout(() => {
        window.location.reload();
      }, 2000);
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
  const results = metrics.results || [];
  const timestamp = metrics.last_run || null;

  return (
    <Stack spacing={2}>
      {/* Status badge */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 1.5,
          bgcolor: '#f5f5f5',
          borderRadius: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {getStatusIcon(status)}
          <Box>
            <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
              Status
            </Typography>
            <Chip
              label={`${passed}/${total} Checks Passed`}
              color={getStatusColor(status)}
              size="small"
              variant="outlined"
            />
          </Box>
        </Box>
      </Box>

      {/* Timestamp */}
      {timestamp && (
        <Typography variant="caption" sx={{ color: '#999', fontSize: '0.75rem' }}>
          Last Run: {new Date(timestamp).toLocaleString()}
        </Typography>
      )}

      {/* Re-run error */}
      {rerunError && (
        <Alert severity="error" sx={{ fontSize: '0.8rem' }}>
          {rerunError}
        </Alert>
      )}

      {/* Re-run button */}
      <Button
        startIcon={running ? <CircularProgress size={16} /> : <RefreshIcon />}
        onClick={handleRerun}
        disabled={running}
        size="small"
        variant="outlined"
        fullWidth
      >
        {running ? 'Running...' : 'Re-run Validation'}
      </Button>

      <Divider />

      {/* Results list */}
      {results.length > 0 && (
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 1 }}>
            Validation Rules
          </Typography>
          <Stack spacing={1}>
            {results.map((result, idx) => (
              <Box
                key={idx}
                sx={{
                  p: 1,
                  bgcolor: '#fafafa',
                  borderRadius: 0.5,
                  borderLeft: `3px solid ${
                    result.passed ? '#4caf50' : '#f44336'
                  }`,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.3 }}>
                  {result.passed ? (
                    <CheckCircleIcon
                      sx={{ fontSize: '1rem', color: '#4caf50', mr: 0.5 }}
                    />
                  ) : (
                    <ErrorIcon
                      sx={{ fontSize: '1rem', color: '#f44336', mr: 0.5 }}
                    />
                  )}
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 600,
                      fontSize: '0.8rem',
                    }}
                  >
                    {result.rule_name}
                  </Typography>
                </Box>
                {result.message && (
                  <Typography
                    variant="caption"
                    sx={{ fontSize: '0.75rem', color: '#666', display: 'block' }}
                  >
                    {result.message}
                  </Typography>
                )}
              </Box>
            ))}
          </Stack>
        </Box>
      )}

      {/* No results */}
      {results.length === 0 && (
        <Typography variant="caption" sx={{ color: '#999', fontSize: '0.8rem' }}>
          No validation results available
        </Typography>
      )}
    </Stack>
  );
}
