// carbon-frontend/src/pages/dq/tabs/ResultsTab.jsx
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Drawer,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { AutoAwesome, Close, InfoOutlined } from '@mui/icons-material';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import PanelTable from '../../../components/panel/PanelTable';
import { getDQResults, getDQResultFailures } from '../../../api/dq';
import { RESULT_STATUS_COLORS } from '../constants';

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  return [];
}

function FailuresDrawer({ result, onClose }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const [failures, setFailures] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!result) return undefined;
    let active = true;
    setLoading(true);
    setFailures(null);
    getDQResultFailures(token, result.id)
      .then((payload) => {
        if (active) setFailures(payload);
      })
      .catch((err) => notifyFromError(err, 'Could not load failure details'))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, result?.id, notifyFromError]);

  if (!result) return null;
  const failureRows = failures?.failures || [];
  const isSkipped = result.status === 'skipped_unavailable';

  return (
    <Drawer anchor="right" open onClose={onClose} PaperProps={{ sx: { width: 560, p: 3 } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography sx={{ fontSize: '1rem', fontWeight: 700 }}>Result #{result.id}</Typography>
        <Button size="small" startIcon={<Close />} onClick={onClose}>
          Close
        </Button>
      </Stack>

      <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 2 }}>
        <Chip
          size="small"
          color={RESULT_STATUS_COLORS[result.status] || 'default'}
          label={result.status || (result.passed ? 'passed' : 'failed')}
        />
        {result.run_at ? (
          <Chip size="small" variant="outlined" label={new Date(result.run_at).toLocaleString()} />
        ) : null}
        {result.score != null ? (
          <Chip size="small" variant="outlined" label={`Score ${Number(result.score).toFixed(1)}%`} />
        ) : null}
      </Stack>

      {isSkipped ? (
        <Box sx={{ mb: 2 }}>
          <Typography sx={{ color: 'text.secondary' }}>
            Pulse could not evaluate this run (skipped_unavailable) — no failure rows were produced.
          </Typography>
        </Box>
      ) : null}

      {loading ? (
        <Typography sx={{ color: 'text.secondary' }}>Loading failures…</Typography>
      ) : (
        <PanelTable
          title="Failure Rows"
          subtitle={`${failures?.failed_count ?? failureRows.length} failed · sample of ${failures?.sample_size ?? failureRows.length}`}
          columns={[
            { key: 'row', header: 'Row' },
            { key: 'field', header: 'Field' },
            {
              key: 'value',
              header: 'Value',
              render: (value) => (
                <Box sx={{ fontFamily: 'monospace', fontSize: '0.75rem', maxWidth: 140, overflowWrap: 'anywhere' }}>
                  {value}
                </Box>
              ),
            },
            {
              key: 'reason',
              header: 'Reason',
              render: (reason) => <Box sx={{ maxWidth: 220 }}>{reason}</Box>,
            },
          ]}
          rows={failureRows.map((f, i) => ({
            id: f.row_id != null ? `${f.row_id}-${i}` : i,
            row: f.row_display || f.row_id || '—',
            field: f.field_name || '—',
            value: f.value != null ? String(f.value) : '—',
            reason: f.reason || '—',
          }))}
          emptyText={
            isSkipped
              ? 'No failure details available for a skipped run.'
              : 'No failure rows recorded — the check passed.'
          }
        />
      )}
    </Drawer>
  );
}

function ResultsTab({ rule, onExplainAI }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getDQResults({ rule: rule.id, ordering: '-run_at' }, token)
      .then((payload) => {
        if (active) setRows(unwrap(payload));
      })
      .catch((err) => notifyFromError(err, 'Could not load results'))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, rule?.id, notifyFromError]);

  const columns = useMemo(
    () => [
      {
        field: 'run_at',
        headerName: 'Run At',
        width: 170,
        renderCell: ({ row }) => (row.run_at ? new Date(row.run_at).toLocaleString() : '—'),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 160,
        renderCell: ({ row }) => (
          <Chip
            size="small"
            color={RESULT_STATUS_COLORS[row.status] || 'default'}
            icon={row.status === 'skipped_unavailable' ? <InfoOutlined /> : undefined}
            label={
              row.status === 'skipped_unavailable'
                ? 'Skipped (Pulse n/a)'
                : row.status || (row.passed ? 'Passed' : 'Failed')
            }
          />
        ),
      },
      { field: 'checked_count', headerName: 'Checked', width: 100, type: 'number' },
      {
        field: 'failed_count',
        headerName: 'Failed',
        width: 90,
        type: 'number',
        renderCell: ({ row }) =>
          row.failed_count ? (
            <Typography sx={{ color: 'error.main', fontWeight: 600 }}>
              {row.failed_count}
            </Typography>
          ) : (
            <Typography>{row.failed_count ?? '—'}</Typography>
          ),
      },
      {
        field: 'score',
        headerName: 'Score',
        width: 90,
        renderCell: ({ row }) =>
          row.score != null ? `${Number(row.score).toFixed(1)}%` : '—',
      },
      {
        field: 'actions',
        headerName: '',
        sortable: false,
        width: 110,
        renderCell: ({ row }) => (
          <Button
            size="small"
            variant="outlined"
            onClick={(e) => {
              e.stopPropagation();
              setSelected(row);
            }}
          >
            Failures
          </Button>
        ),
      },
    ],
    []
  );

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<AutoAwesome />}
          onClick={onExplainAI}
        >
          Explain failures with AI
        </Button>
      </Stack>
      <Paper variant="outlined" sx={{ borderRadius: 2 }}>
        <CarbonDataGrid
          columns={columns}
          rows={rows}
          loading={loading}
          getRowId={(row) => row.id || `${row.rule}-${row.run_at}`}
          emptyMessage="No results yet — run this rule to generate results"
          onRowClick={({ row }) => setSelected(row)}
        />
      </Paper>
      <FailuresDrawer result={selected} onClose={() => setSelected(null)} />
    </Box>
  );
}

ResultsTab.propTypes = {
  rule: PropTypes.object,
  onExplainAI: PropTypes.func,
};

export default ResultsTab;
