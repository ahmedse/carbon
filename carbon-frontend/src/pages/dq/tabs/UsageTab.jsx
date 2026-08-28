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
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation('dq');
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
      .catch((err) => notifyFromError(err, t('usage.loadError')))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, rule?.id, notifyFromError, t]);

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
          text: t('usage.noCoverage', { field: b.field_name, table: b.table_name }),
        });
      } else {
        notes.push({
          key: `${b.data_table}-${b.data_field}`,
          kind: 'info',
          text:
            others.length === 1
              ? t('usage.alsoCoveredOne', { field: b.field_name, table: b.table_name, count: others.length })
              : t('usage.alsoCoveredMany', { field: b.field_name, table: b.table_name, count: others.length }),
        });
      }
    });
    return notes;
  }, [bindings, rules, t]);

  const assetColumns = useMemo(
    () => [
      {
        field: 'title',
        headerName: t('usage.catalogAsset'),
        flex: 1.4,
        minWidth: 200,
        renderCell: ({ row }) => (
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{row.title || '—'}</Typography>
        ),
      },
      {
        field: 'asset_type',
        headerName: t('columns.type'),
        width: 100,
        renderCell: ({ row }) => (
          <Chip
            size="small"
            variant="outlined"
            label={row.asset_type === 'field' ? t('usage.field') : t('usage.table')}
          />
        ),
      },
      {
        field: 'quality_status',
        headerName: t('usage.quality'),
        width: 150,
        renderCell: ({ row }) =>
          row.quality_status ? (
            <Chip
              size="small"
              color={qualityColor(row.quality_status)}
              label={`${row.quality_status}${row.quality_score != null ? ` · ${row.quality_score}` : ''}`}
            />
          ) : (
            <Typography sx={{ color: 'text.secondary' }}>{t('usage.notAssessed')}</Typography>
          ),
      },
    ],
    [t]
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>
        {t('usage.boundTablesFields')}
        <Chip
          size="small"
          variant="outlined"
          label={
            bindings.length === 1
              ? t('usage.bindingCountOne', { count: bindings.length })
              : t('usage.bindingCountMany', { count: bindings.length })
          }
          sx={{ ml: 1 }}
        />
      </Typography>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 3 }}>
        {bindings.length === 0 ? (
          <Typography sx={{ color: 'text.secondary' }}>
            {t('usage.noBindings')}
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
        {relatedAssets.length === 1
          ? t('usage.usedByOne', { count: relatedAssets.length })
          : t('usage.usedByMany', { count: relatedAssets.length })}
      </Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CarbonDataGrid
          columns={assetColumns}
          rows={relatedAssets}
          loading={loading}
          getRowId={(row) => row.id}
          emptyMessage={t('usage.noAssets')}
        />
      </Paper>

      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('usage.fieldCoverage')}</Typography>
      {coverageNotes.length === 0 ? (
        <Alert severity="info">
          {t('usage.noFieldBindings')}
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
