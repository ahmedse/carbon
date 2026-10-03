// src/components/inbound/InboundRowsViewer.jsx
// Read-only, server-paginated view of every row in the batch file.
// The server re-parses the CSV on each page (no staging table). Verdict/reason
// come from the persisted smoke envelope, so a clean insert keeps an empty
// reason. Works for every status, including committed.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import FilteredDataGrid from '../FilteredDataGrid';
import ErrorAlert from '../Page/ErrorAlert';
import { fetchInboundRows } from '../../api/inbound';

const PAGE_SIZES = [25, 50, 100, 200];

export default function InboundRowsViewer({
  token,
  batchId,
  headers = [],
  ns = 'people',
  height = 360,
}) {
  const { t } = useTranslation(ns);

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!token || !batchId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInboundRows(token, batchId, { page: page + 1, pageSize });
      const list = Array.isArray(data) ? data : data?.results || [];
      setRows(list);
      setCount(Number.isFinite(data?.count) ? data.count : list.length);
    } catch (err) {
      setError(err?.status === 403 ? 'forbidden' : (err?.message || t('importRowsFailed')));
    } finally {
      setLoading(false);
    }
  }, [token, batchId, page, pageSize, t]);

  useEffect(() => {
    load();
  }, [load]);

  const gridRows = useMemo(
    () => rows.map((row) => ({
      ...(row.values || {}),
      __row: row.row,
      __key: row.key,
      __verdict: row.verdict,
      __reason: row.reason,
    })),
    [rows],
  );

  const columns = useMemo(() => [
    { field: '__row', headerName: t('importColRow'), width: 80 },
    { field: '__key', headerName: t('importColKey'), width: 150, valueGetter: (v) => v || '—' },
    {
      field: '__verdict',
      headerName: t('importColVerdict'),
      width: 120,
      valueGetter: (v) => v || '—',
    },
    { field: '__reason', headerName: t('importColReason'), flex: 1, minWidth: 180, valueGetter: (v) => v || '' },
    ...headers.map((header) => ({
      field: header,
      headerName: header,
      width: 150,
      valueGetter: (_v, row) => row[header] ?? '',
    })),
  ], [headers, t]);

  if (error) {
    return (
      <ErrorAlert
        message={error === 'forbidden' ? t('importForbidden') : error}
        onRetry={error === 'forbidden' ? undefined : load}
      />
    );
  }

  const empty = count === 0;
  return (
    <Stack spacing={0.5}>
      <Stack direction="row" spacing={1} alignItems="baseline" justifyContent="space-between">
        <Typography variant="subtitle2">{t('importRowsTitle')}</Typography>
        <Typography variant="caption" color="text.secondary">
          {t('importRowsCount', { count })}
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary">{t('importRowsHint')}</Typography>
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
        dataGridProps={{ density: 'compact', hideFooterSelectedRowCount: true }}
      />
    </Stack>
  );
}
