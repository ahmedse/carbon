// carbon-frontend/src/pages/dq/tabs/UsageTab.jsx
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { listDQRules } from '../../../api/dq';
import { fetchAssetProfiles } from '../../../api/catalog';

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  return [];
}

function qualityColor(status) {
  if (!status) return 'default';
  const s = String(status).toLowerCase();
  if (s.includes('excellent') || s.includes('good')) return 'success';
  if (s.includes('fair')) return 'warning';
  return 'error';
}

function UsageTab({ rule }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const [assets, setAssets] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);

  const bindings = useMemo(() => rule?.field_assignments || [], [rule]);
  const boundTableIds = useMemo(() => new Set(bindings.map((b) => b.data_table)), [bindings]);
  const boundFieldIds = useMemo(() => new Set(bindings.map((b) => b.data_field).filter(Boolean)), [bindings]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchAssetProfiles(token), listDQRules(token, {})])
      .then(([assetPayload, rulePayload]) => {
        if (!active) return;
        setAssets(unwrap(assetPayload));
        setRules(unwrap(rulePayload).filter((r) => r.id !== rule?.id));
      })
      .catch((err) => notifyFromError(err, 'Could not load usage data'))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, rule?.id, notifyFromError]);

  const relatedAssets = useMemo(
    () =>
      assets.filter(
        (a) =>
          (a.data_table != null && boundTableIds.has(a.data_table)) ||
          (a.data_field != null && boundFieldIds.has(a.data_field))
      ),
    [assets, boundTableIds, boundFieldIds]
  );

  const coverageNotes = useMemo(() => {
    const notes = [];
    bindings.forEach((b) => {
      if (!b.data_field) return; // table-level rule — skip field coverage note
      const others = rules.filter((r) =>
        (r.field_assignments || []).some((a) => a.data_field === b.data_field && a.data_field != null)
      );
      if (others.length === 0) {
        notes.push({
          key: `${b.data_table}-${b.data_field}`,
          kind: 'warning',
          text: `No other rule covers field "${b.field_name}" on "${b.table_name}".`,
        });
      } else {
        notes.push({
          key: `${b.data_table}-${b.data_field}`,
          kind: 'info',
          text: `Field "${b.field_name}" on "${b.table_name}" is also covered by ${others.length} other rule(s).`,
        });
      }
    });
    return notes;
  }, [bindings, rules]);

  const assetColumns = useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Catalog Asset',
        flex: 1.4,
        minWidth: 200,
        renderCell: ({ row }) => (
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{row.title || '—'}</Typography>
        ),
      },
      {
        field: 'asset_type',
        headerName: 'Type',
        width: 100,
        renderCell: ({ row }) => (
          <Chip size="small" variant="outlined" label={row.asset_type === 'field' ? 'Field' : 'Table'} />
        ),
      },
      {
        field: 'quality_status',
        headerName: 'Quality',
        width: 150,
        renderCell: ({ row }) =>
          row.quality_status ? (
            <Chip
              size="small"
              color={qualityColor(row.quality_status)}
              label={`${row.quality_status}${row.quality_score != null ? ` · ${row.quality_score}` : ''}`}
            />
          ) : (
            <Typography sx={{ color: 'text.secondary' }}>Not assessed</Typography>
          ),
      },
    ],
    []
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>
        Bound Tables & Fields
        <Chip
          size="small"
          variant="outlined"
          label={`${bindings.length} binding${bindings.length === 1 ? '' : 's'}`}
          sx={{ ml: 1 }}
        />
      </Typography>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 3 }}>
        {bindings.length === 0 ? (
          <Typography sx={{ color: 'text.secondary' }}>
            This rule has no table bindings.
          </Typography>
        ) : (
          <Stack direction="row" spacing={0.5} flexWrap="wrap">
            {bindings.map((b) => (
              <Chip
                key={b.id || `${b.data_table}-${b.data_field}`}
                size="small"
                variant="outlined"
                color="primary"
                label={b.field_name ? `${b.table_name} · ${b.field_name}` : b.table_name}
              />
            ))}
          </Stack>
        )}
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>
        Used by {relatedAssets.length} catalog asset{relatedAssets.length === 1 ? '' : 's'}
      </Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CarbonDataGrid
          columns={assetColumns}
          rows={relatedAssets}
          loading={loading}
          getRowId={(row) => row.id}
          emptyMessage="No catalog assets reference the bound tables/fields"
        />
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>Field Coverage</Typography>
      {coverageNotes.length === 0 ? (
        <Alert severity="info">
          No field-level bindings — coverage notes apply to field-bound rules only.
        </Alert>
      ) : (
        <Stack spacing={1}>
          {coverageNotes.map((note) => (
            <Alert key={note.key} severity={note.kind}>
              {note.text}
            </Alert>
          ))}
        </Stack>
      )}
    </Box>
  );
}

UsageTab.propTypes = {
  rule: PropTypes.object,
};

export default UsageTab;
