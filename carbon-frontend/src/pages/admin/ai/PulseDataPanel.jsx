// src/pages/admin/ai/PulseDataPanel.jsx
// Generic read-only Pulse console panel — renders model-backed rows from the
// /ai/pulse/data/<key>/ read API. Never fabricates data: loading spinner,
// offline paper, grounded empty state, then the real rows in a DataGrid.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import CloseIcon from '@mui/icons-material/Close';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseData } from '../../../api/aiPulse';
import {
  SCOPE_FIELDS,
  formatCellValue,
  buildScopeLabel,
  buildDetailFields,
} from './pulseFormat';

/** Read-only detail drawer — the full record of the clicked Pulse row. */
function PulseDetailDrawer({ row, onClose }) {
  if (!row) return null;
  const fields = buildDetailFields(row);
  const rawJson = JSON.stringify(row, null, 2);

  return (
    <Drawer
      anchor="right"
      open
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: '100%', sm: 560 }, p: 3 } }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip size="small" variant="outlined" label={row._type ?? 'record'} />
          <Typography sx={{ fontSize: '1rem', fontWeight: 700 }}>
            {row.id ?? row.conversation_id ?? row.name ?? 'Record detail'}
          </Typography>
        </Stack>
        <IconButton size="small" onClick={onClose} aria-label="Close detail">
          <CloseIcon />
        </IconButton>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {fields.length ? (
        <Stack spacing={1} sx={{ mb: 2 }}>
          {fields.map(({ key, value }) => (
            <Stack key={key} direction="row" spacing={1} alignItems="flex-start">
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  minWidth: 140,
                  flexShrink: 0,
                  color: 'text.secondary',
                }}
              >
                {key}
              </Typography>
              <Typography variant="body2" sx={{ overflowWrap: 'anywhere', flex: 1 }}>
                {value}
              </Typography>
            </Stack>
          ))}
        </Stack>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          No scalar fields — see raw JSON below.
        </Typography>
      )}

      <Divider sx={{ mb: 1 }} />
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>
        Raw JSON
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.5,
          borderRadius: 1,
          bgcolor: 'action.hover',
          fontSize: '0.75rem',
          lineHeight: 1.5,
          overflow: 'auto',
          maxHeight: '50vh',
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
        }}
      >
        {rawJson}
      </Box>
    </Drawer>
  );
}

PulseDetailDrawer.propTypes = {
  row: PropTypes.object,
  onClose: PropTypes.func.isRequired,
};

PulseDetailDrawer.defaultProps = {
  row: null,
};

export default function PulseDataPanel({ title, description, dataKey, emptyHint }) {
  useDocumentTitle(title);
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getPulseData(token, dataKey);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setData(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, dataKey]);

  const rows = useMemo(() => data?.results ?? [], [data?.results]);

  const columns = useMemo(() => {
    if (!rows.length) return [];
    const keys = new Set();
    rows.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
    const dynamic = [...keys].filter((key) => key !== '_type' && !SCOPE_FIELDS.includes(key));
    return [
      {
        field: '_actions',
        headerName: '',
        width: 52,
        sortable: false,
        filterable: false,
        renderCell: ({ row }) => (
          <Tooltip title="Inspect record">
            <IconButton
              size="small"
              aria-label="Inspect record"
              onClick={(event) => {
                event.stopPropagation();
                setSelected(row);
              }}
            >
              <VisibilityOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ),
      },
      {
        field: '_type',
        headerName: 'Type',
        width: 140,
        sortable: true,
        renderCell: ({ value }) => <Chip size="small" variant="outlined" label={value} />,
      },
      {
        field: 'scope',
        headerName: 'Scope',
        width: 220,
        sortable: false,
        renderCell: ({ row }) => (
          <Typography
            variant="body2"
            sx={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}
          >
            {buildScopeLabel(row)}
          </Typography>
        ),
      },
      ...dynamic.map((key) => ({
        field: key,
        headerName: key,
        minWidth: 160,
        flex: 1,
        renderCell: (params) => (
          <Typography
            variant="body2"
            sx={{ display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}
          >
            {formatCellValue(params.row[key])}
          </Typography>
        ),
      })),
    ];
  }, [rows]);

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>{title}</Typography>
          {data && !offline && (
            <Chip size="small" variant="outlined" label={`${data.count} rows`} />
          )}
        </Stack>
        {description && (
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              Data unavailable
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Data unavailable — the Pulse read API is offline
            </Typography>
          </Paper>
        ) : rows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="subtitle1" fontWeight={600}>{title}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {emptyHint}
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined" sx={{ flex: 1, minHeight: 0 }}>
            <CarbonDataGrid
              columns={columns}
              rows={rows}
              loading={false}
              getRowId={(row) => `${row._type}:${row.id ?? row.conversation_id ?? JSON.stringify(row)}`}
              emptyMessage={emptyHint}
              onRowClick={({ row }) => setSelected(row)}
            />
          </Paper>
        )}
      </Stack>
      <PulseDetailDrawer row={selected} onClose={() => setSelected(null)} />
    </PageContainer>
  );
}

PulseDataPanel.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  dataKey: PropTypes.string.isRequired,
  emptyHint: PropTypes.string.isRequired,
};

PulseDataPanel.defaultProps = {
  description: '',
};
