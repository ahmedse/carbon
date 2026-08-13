// src/pages/admin/ai/PulseDataPanel.jsx
// Generic read-only Pulse console panel — renders model-backed rows from the
// /ai/pulse/data/<key>/ read API. Never fabricates data: loading spinner,
// offline paper, grounded empty state, then the real rows in a DataGrid.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseData } from '../../../api/aiPulse';

// AppScopeMixin columns — collapsed into a single compact "scope" column.
const SCOPE_FIELDS = ['app_identifier', 'org_unit_id', 'host_user_id', 'visibility'];

/** Defensive cell formatting: null/undefined -> '—', nested values -> JSON. */
function formatCellValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value) || typeof value === 'object') {
    const text = JSON.stringify(value);
    return text.length > 80 ? `${text.slice(0, 80)}…` : text;
  }
  return String(value);
}

/** Compact one-line scope summary for a row (replaces 4 wide columns). */
function buildScopeLabel(row) {
  const parts = [];
  if (row.app_identifier) parts.push(String(row.app_identifier));
  if (row.org_unit_id != null) parts.push(`org:${row.org_unit_id}`);
  if (row.host_user_id) parts.push(`user:${row.host_user_id}`);
  if (row.visibility) parts.push(String(row.visibility));
  return parts.length ? parts.join(' · ') : '—';
}

export default function PulseDataPanel({ title, description, dataKey, emptyHint }) {
  useDocumentTitle(title);
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

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

  const rows = data?.results ?? [];

  const columns = useMemo(() => {
    if (!rows.length) return [];
    const keys = new Set();
    rows.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
    const dynamic = [...keys].filter((key) => key !== '_type' && !SCOPE_FIELDS.includes(key));
    return [
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
            />
          </Paper>
        )}
      </Stack>
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
