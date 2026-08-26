// src/pages/catalog/tabs/TableProfileTab.jsx
// DQ profile for a single table (EPH-3A): latest TableProfile + per-field
// FieldProfiles rendered in a DataGrid. Admins can trigger a re-profile.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert, Box, Button, Chip, CircularProgress, Stack, Tooltip, Typography,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { getTableProfile, runTableProfile } from '../../../api/profiling';

const NA = '—';
const NO_PROFILE_DETAIL = 'No profile yet for this table.';

// Relative-time helper shared across the freshness/profile surfaces.
// Safe for SSR/tests: invalid/missing ISO resolves to the "na" translation.
function formatRelativeTime(iso, t) {
  if (!iso) return t('na');
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return t('na');
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60_000) return t('justNow');
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return t('minutesAgo', { count: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return t('hoursAgo', { count: hours });
  const days = Math.floor(hours / 24);
  if (days < 7) return t('daysAgo', { count: days });
  return date.toLocaleDateString();
}

// FieldProfileSerializer serializes `data_field` as the FK id (int), so the
// profile payload carries no field type. Defensively support an embedded
// object (future-proof) — otherwise the Type column renders as blank.
function resolveFieldType(field) {
  const ref = field?.data_field;
  if (ref && typeof ref === 'object') {
    return ref.type || ref.data_type || ref.field_type || '';
  }
  return '';
}

function formatInt(value) {
  if (value === null || value === undefined || value === '') return NA;
  const n = Number(value);
  if (Number.isNaN(n)) return NA;
  return n.toLocaleString();
}

function formatScalar(value) {
  if (value === null || value === undefined || value === '') return NA;
  return String(value);
}

function formatMean(value) {
  if (value === null || value === undefined || value === '') return NA;
  const n = Number(value);
  if (Number.isNaN(n)) return NA;
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatNullPct(row) {
  if (row.null_count === null || row.null_count === undefined) return NA;
  if (!row.row_count) return '0.0%';
  return `${((row.null_count / row.row_count) * 100).toFixed(1)}%`;
}

function TopValuesSummary({ topValues, t }) {
  if (!Array.isArray(topValues) || topValues.length === 0) {
    return <Typography variant="body2">{NA}</Typography>;
  }
  return (
    <Tooltip
      arrow
      title={(
        <Box component="ul" sx={{ m: 0, pl: 2 }}>
          {topValues.map((entry, idx) => (
            <li key={idx}>{String(entry?.value)}: {entry?.count}</li>
          ))}
        </Box>
      )}
    >
      <Chip
        size="small"
        variant="outlined"
        label={t('valuesCount', { count: topValues.length })}
      />
    </Tooltip>
  );
}

export default function TableProfileTab({ tableId, isAdmin = false }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const { t } = useTranslation('catalog');

  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [noProfile, setNoProfile] = useState(false);
  const [error, setError] = useState(null);
  const [profile, setProfile] = useState(null);
  const [fields, setFields] = useState([]);

  const load = useCallback(async () => {
    if (!tableId) return;
    setLoading(true);
    setError(null);
    setNoProfile(false);
    try {
      const data = await getTableProfile(tableId, token);
      setProfile(data?.profile || null);
      setFields(Array.isArray(data?.fields) ? data.fields : []);
    } catch (err) {
      if (err?.status === 404 && err?.data?.detail === NO_PROFILE_DETAIL) {
        // "No profile yet" is a normal pre-profile state — not a fatal error.
        setProfile(null);
        setFields([]);
        setNoProfile(true);
      } else {
        const message = err?.message || t('failedToLoadProfile');
        setError(message);
        notify({ message, type: 'error' });
      }
    } finally {
      setLoading(false);
    }
  }, [tableId, token, notify, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRun = useCallback(async () => {
    setRunning(true);
    try {
      await runTableProfile(tableId, token);
      // Backend runs the profile inline; a single short delay is enough to
      // surface the fresh profile (no infinite polling).
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await load();
    } catch (err) {
      const message = err?.message || t('failedToRunProfile');
      notify({ message, type: 'error' });
    } finally {
      setRunning(false);
    }
  }, [tableId, token, load, notify, t]);

  const columns = useMemo(() => [
    {
      field: 'field_name',
      headerName: t('fieldName'),
      flex: 1.2,
      minWidth: 140,
      valueGetter: (value, row) => row.field_name || NA,
    },
    {
      field: 'type',
      headerName: t('type'),
      flex: 0.8,
      minWidth: 100,
      valueGetter: (value, row) => resolveFieldType(row) || NA,
    },
    {
      field: 'null_pct',
      headerName: t('nullPercent'),
      flex: 0.8,
      minWidth: 90,
      valueGetter: (value, row) => formatNullPct(row),
    },
    {
      field: 'distinct_count',
      headerName: t('cardinality'),
      flex: 0.8,
      minWidth: 100,
      valueGetter: (value, row) => formatInt(row.distinct_count),
    },
    {
      field: 'min_value',
      headerName: t('min'),
      flex: 0.9,
      minWidth: 100,
      valueGetter: (value, row) => formatScalar(row.min_value),
    },
    {
      field: 'max_value',
      headerName: t('max'),
      flex: 0.9,
      minWidth: 100,
      valueGetter: (value, row) => formatScalar(row.max_value),
    },
    {
      field: 'mean_value',
      headerName: t('mean'),
      flex: 0.8,
      minWidth: 100,
      valueGetter: (value, row) => formatMean(row.mean_value),
    },
    {
      field: 'top_values',
      headerName: t('topValues'),
      flex: 1,
      minWidth: 140,
      renderCell: (params) => <TopValuesSummary topValues={params.row.top_values} t={t} />,
    },
  ], [t]);

  const rows = useMemo(
    () => fields.map((f, idx) => ({ ...f, id: f.id ?? idx })),
    [fields],
  );

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Stack spacing={2}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary">
            {profile ? t('profiledAgo', { time: formatRelativeTime(profile.profiled_at, t) }) : null}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {running && <Chip size="small" color="info" label={t('profiling')} />}
            {isAdmin && (
              <Button size="small" variant="contained" onClick={handleRun} disabled={running}>
                {t('runProfile')}
              </Button>
            )}
          </Box>
        </Box>

        {error && <Alert severity="warning">{error}</Alert>}

        {noProfile ? (
          <Alert severity="info">{t('noProfileYet')}</Alert>
        ) : fields.length === 0 ? (
          <Alert severity="info">{t('noFieldsDefined')}</Alert>
        ) : (
          <Box sx={{ width: '100%' }}>
            <DataGrid
              rows={rows}
              columns={columns}
              autoHeight
              density="compact"
              getRowId={(row) => row.id}
            />
          </Box>
        )}
      </Stack>
    </DetailTabContent>
  );
}
