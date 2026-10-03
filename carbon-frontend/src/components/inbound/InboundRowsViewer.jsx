// src/components/inbound/InboundRowsViewer.jsx
// Read-only, server-paginated view of every row in the batch file.
// The server re-parses the CSV on each page (no staging table). The smoke
// result, reason and structured issues come from the persisted smoke envelope
// joined by row number, so an unsmoked batch reads "Not smoked yet" and never a
// false pass. Works for every status, including committed.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useTranslation } from 'react-i18next';
import FilteredDataGrid from '../FilteredDataGrid';
import ErrorAlert from '../Page/ErrorAlert';
import { fetchInboundRows } from '../../api/inbound';

const PAGE_SIZES = [25, 50, 100, 200];

// Raw smoke verdict -> design-system chip colour. Labels are i18n keys
// (importResult_*), resolved by the active namespace.
const RESULT_TONE = {
  insert: 'success',
  update: 'info',
  skip: 'default',
  ok: 'success',
  reject: 'error',
};

function resultKey(verdict, smoked) {
  if (!smoked) return 'importResult_notSmoked';
  switch (verdict) {
    case 'insert': return 'importResult_insert';
    case 'update': return 'importResult_update';
    case 'skip': return 'importResult_skip';
    case 'ok': return 'importResult_ok';
    case 'reject': return 'importResult_reject';
    default: return 'importResult_unrecorded';
  }
}

function actionKey(verdict, smoked) {
  if (!smoked) return 'importAction_notSmoked';
  switch (verdict) {
    case 'insert': return 'importAction_insert';
    case 'update': return 'importAction_update';
    case 'skip': return 'importAction_skip';
    case 'ok': return 'importAction_ok';
    case 'reject': return 'importAction_reject';
    default: return 'importAction_unrecorded';
  }
}

export default function InboundRowsViewer({
  token,
  batchId,
  headers = [],
  fields = [],
  columnMap = {},
  ns = 'people',
  height = 360,
}) {
  const { t } = useTranslation(ns);

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [smoked, setSmoked] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [detailRow, setDetailRow] = useState(null);

  const load = useCallback(async () => {
    if (!token || !batchId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInboundRows(token, batchId, { page: page + 1, pageSize });
      const list = Array.isArray(data) ? data : data?.results || [];
      setRows(list);
      setCount(Number.isFinite(data?.count) ? data.count : list.length);
      setSmoked(Boolean(data?.smoked));
    } catch (err) {
      setError(err?.status === 403 ? 'forbidden' : (err?.message || t('importRowsFailed')));
    } finally {
      setLoading(false);
    }
  }, [token, batchId, page, pageSize, t]);

  useEffect(() => {
    load();
  }, [load]);

  // The open details panel belongs to one page; clear it when the page changes.
  useEffect(() => {
    setDetailRow(null);
  }, [page, pageSize]);

  const fieldByName = useMemo(
    () => Object.fromEntries((fields || []).map((field) => [field.name, field])),
    [fields],
  );

  const gridRows = useMemo(
    () => rows.map((row) => ({
      ...(row.values || {}),
      __row: row.row,
      __key: row.key,
      __verdict: row.verdict,
      __reason: row.reason,
      __issues: row.issues || [],
      __smoked: smoked,
    })),
    [rows, smoked],
  );

  const columns = useMemo(() => [
    { field: '__row', headerName: t('importColRow'), width: 80 },
    { field: '__key', headerName: t('importColKey'), width: 150, valueGetter: (v) => v || '—' },
    {
      field: '__smokeResult',
      headerName: t('importColSmokeResult'),
      width: 160,
      sortable: false,
      renderCell: (params) => (
        <Chip
          size="small"
          label={t(resultKey(params.row.__verdict, params.row.__smoked))}
          color={RESULT_TONE[params.row.__verdict] || 'default'}
          variant={params.row.__verdict ? 'filled' : 'outlined'}
        />
      ),
    },
    {
      field: '__smokeDetails',
      headerName: t('importColSmokeDetails'),
      flex: 1,
      minWidth: 220,
      sortable: false,
      renderCell: (params) => {
        const isReject = params.row.__verdict === 'reject';
        return (
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ width: '100%' }}>
            <Typography
              variant="caption"
              noWrap
              color={isReject ? 'error.main' : 'text.secondary'}
              sx={{ flex: 1, minWidth: 0 }}
            >
              {isReject && params.row.__reason
                ? params.row.__reason
                : t(actionKey(params.row.__verdict, params.row.__smoked))}
            </Typography>
            {isReject && (
              <Button
                size="small"
                color="error"
                onClick={() => setDetailRow(params.row.__row)}
              >
                {t('importRowDetails')}
              </Button>
            )}
          </Stack>
        );
      },
    },
    ...headers.map((header) => ({
      field: header,
      headerName: header,
      width: 150,
      valueGetter: (_v, row) => row[header] ?? '',
    })),
  ], [headers, t]);

  const selected = useMemo(
    () => rows.find((row) => row.row === detailRow) || null,
    [rows, detailRow],
  );

  const labelFor = useCallback((name) => {
    const source = Object.entries(columnMap || {})
      .find(([, target]) => target === name)?.[0] || '';
    const label = fieldByName[name]?.label || name;
    return source && source !== label ? `${source} → ${label}` : label;
  }, [columnMap, fieldByName]);

  if (error) {
    return (
      <ErrorAlert
        message={error === 'forbidden' ? t('importForbidden') : error}
        onRetry={error === 'forbidden' ? undefined : load}
      />
    );
  }

  const empty = count === 0;
  const issues = selected?.issues || [];
  return (
    <Stack spacing={0.5}>
      <Stack direction="row" spacing={1} alignItems="baseline" justifyContent="space-between">
        <Typography variant="subtitle2">{t('importRowsTitle')}</Typography>
        <Typography variant="caption" color="text.secondary">
          {t('importRowsCount', { count })}
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary">{t('importRowsHint')}</Typography>
      {!smoked && count > 0 && (
        <Alert severity="info">{t('importRowsNotSmoked')}</Alert>
      )}
      <FilteredDataGrid
        embedded
        hideSearch
        loading={loading}
        rows={gridRows}
        columns={columns}
        getRowId={(row) => String(row.__row)}
        paginationMode="server"
        rowCount={count}
        paginationModel={{ page, pageSize }}
        onPaginationModelChange={(model) => {
          setPage(model.page);
          setPageSize(model.pageSize);
        }}
        rowsPerPageOptions={PAGE_SIZES}
        height={height}
        emptyMessage={empty ? t('importRowsEmpty') : t('importRowsNoResults')}
        emptySubtext={empty ? t('importRowsEmptyDesc') : ''}
        highlightRow={(row) => row.__row === detailRow}
        dataGridProps={{ density: 'compact', hideFooterSelectedRowCount: true }}
      />
      {selected && selected.verdict === 'reject' && (
        <Paper variant="outlined" sx={{ p: 1.5, borderColor: 'error.main' }}>
          <Stack spacing={1}>
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Typography variant="subtitle2">
                {t('importRowDetailsTitle', { row: selected.row, key: selected.key || '—' })}
              </Typography>
              <IconButton
                size="small"
                aria-label={t('importRowDetailsClose')}
                onClick={() => setDetailRow(null)}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {t('importRowDetailsHint')}
            </Typography>
            {issues.length > 0 ? issues.map((item, index) => (
              <Box key={`${item.field}-${index}`}>
                <Typography variant="subtitle2">{labelFor(item.field)}</Typography>
                <Typography variant="body2" color="error.main">{item.message}</Typography>
                {item.fix && (
                  <Typography variant="caption" color="text.secondary">
                    {t('importRowDetailsFix')}: {item.fix}
                  </Typography>
                )}
              </Box>
            )) : (
              <Box>
                <Typography variant="subtitle2">{t('importRowDetailsReason')}</Typography>
                <Typography variant="body2" color="error.main">{selected.reason}</Typography>
              </Box>
            )}
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
