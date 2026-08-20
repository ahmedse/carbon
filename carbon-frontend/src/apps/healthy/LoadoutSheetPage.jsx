// src/apps/healthy/LoadoutSheetPage.jsx
// Healthy Foods Factory — loadout sheet (week picker + rep table + item rows + CSV export).

import React, { useEffect, useMemo, useState } from 'react';
import { Box, Button, Chip, MenuItem, Paper, Select, Stack, Typography } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import TableChartIcon from '@mui/icons-material/TableChart';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import StandardDataGrid from '../../components/StandardDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchLoadoutSheets, fetchLoadoutWeek } from '../../api/healthy';
import { buildLoadoutCsv, formatPercent } from './utils';

/** Trigger a browser download of CSV text (side-effectful, not exported). */
function downloadCsv(filename, csv) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function LoadoutSheetPage() {
  useDocumentTitle('Loadout Sheet');
  const { token } = useAuth();
  const [weeks, setWeeks] = useState([]);
  const [week, setWeek] = useState('');
  const [sheets, setSheets] = useState([]);
  const [selectedRepCode, setSelectedRepCode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load available weeks first, then the selected week's sheets.
  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchLoadoutSheets({}, token)
      .then((data) => {
        const list = Array.isArray(data?.results) ? data.results : [];
        const distinct = [...new Set(list.map((s) => s.week_start).filter(Boolean))].sort().reverse();
        setWeeks(distinct);
        if (distinct.length) {
          setWeek(distinct[0]);
        } else {
          setSheets([]);
          setLoading(false);
        }
      })
      .catch((err) => {
        setError(err?.message || 'Unable to load loadout sheets.');
        setLoading(false);
      });
  }, [token]);

  useEffect(() => {
    if (!week) return;
    setLoading(true);
    setError(null);
    fetchLoadoutWeek(week, token)
      .then((data) => {
        const list = Array.isArray(data?.results) ? data.results : data;
        setSheets(Array.isArray(list) ? list : []);
        setSelectedRepCode((prev) => prev ?? list[0]?.rep_code ?? null);
      })
      .catch((err) => setError(err?.message || 'Unable to load this week.'))
      .finally(() => setLoading(false));
  }, [week, token]);

  const repRows = useMemo(
    () =>
      sheets.map((sheet) => {
        const items = Array.isArray(sheet.line_items) ? sheet.line_items : [];
        const forecastQty = items.reduce((sum, item) => sum + (Number(item.qty_forecast) || 0), 0);
        return {
          id: sheet.id ?? `${sheet.week_start}-${sheet.rep_code}`,
          rep_code: sheet.rep_code,
          rep_name: sheet.rep_name,
          item_count: items.length,
          forecast_qty: forecastQty,
        };
      }),
    [sheets],
  );

  const selectedSheet = sheets.find((s) => s.rep_code === selectedRepCode) || sheets[0] || null;
  const itemRows = useMemo(() => {
    const items = Array.isArray(selectedSheet?.line_items) ? selectedSheet.line_items : [];
    return items.map((item, index) => ({ id: item.id ?? `${selectedSheet.rep_code}-${index}`, ...item }));
  }, [selectedSheet]);

  const repColumns = [
    { field: 'rep_code', headerName: 'Rep code', flex: 1, minWidth: 120 },
    { field: 'rep_name', headerName: 'Rep name', flex: 1.5, minWidth: 160 },
    { field: 'item_count', headerName: 'Items', flex: 0.6, type: 'number' },
    { field: 'forecast_qty', headerName: 'Forecast qty', flex: 1, type: 'number' },
  ];

  const itemColumns = [
    { field: 'item_code', headerName: 'Item code', flex: 1, minWidth: 120 },
    { field: 'item_name', headerName: 'Item name', flex: 2, minWidth: 180 },
    { field: 'qty_forecast', headerName: 'Forecast', flex: 0.8, type: 'number' },
    { field: 'qty_actual', headerName: 'Actual', flex: 0.8, type: 'number' },
    {
      field: 'return_rate_forecast',
      headerName: 'Return rate',
      flex: 0.8,
      valueFormatter: (value) => formatPercent(value),
    },
  ];

  if (loading && weeks.length === 0) {
    return (
      <PageContainer>
        <PageHeader icon={TableChartIcon} title="Loadout Sheet" subtitle="Weekly load-out planning by rep" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={TableChartIcon} title="Loadout Sheet" subtitle="Weekly load-out planning by rep" />
        <ErrorAlert message={error} onRetry={() => window.location.reload()} />
      </PageContainer>
    );
  }

  if (weeks.length === 0) {
    return (
      <PageContainer>
        <PageHeader icon={TableChartIcon} title="Loadout Sheet" subtitle="Weekly load-out planning by rep" />
        <EmptyState
          icon={<TableChartIcon />}
          title="No loadout sheets yet"
          description="Loadout sheets are generated once the returns forecast completes. Check back after the next pipeline run."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={TableChartIcon}
        title="Loadout Sheet"
        subtitle="Weekly load-out planning by rep"
        description="Review forecast quantities per rep and item, then export the week for distribution."
        actions={
          <Button
            variant="contained"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => downloadCsv(`healthy-loadout-${week}.csv`, buildLoadoutCsv(sheets))}
          >
            Export XLS
          </Button>
        }
      />

      <Stack spacing={2}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>Week</Typography>
          <Select
            size="small"
            value={week}
            onChange={(e) => setWeek(e.target.value)}
            sx={{ minWidth: 180 }}
          >
            {weeks.map((w) => (
              <MenuItem key={w} value={w}>
                {w}
              </MenuItem>
            ))}
          </Select>
          {selectedSheet && (
            <Chip
              size="small"
              label={`${selectedSheet.rep_name || selectedSheet.rep_code} selected`}
              color="primary"
              variant="outlined"
            />
          )}
        </Box>

        <Box>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>Reps</Typography>
          <StandardDataGrid
            rows={repRows}
            columns={repColumns}
            loading={loading}
            pageSize={10}
            rowsPerPageOptions={[10, 25, 50]}
            onRowClick={(params) => setSelectedRepCode(params.row.rep_code)}
            sx={{ height: 320 }}
          />
        </Box>

        <Box>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>Items</Typography>
          <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
            <StandardDataGrid
              rows={itemRows}
              columns={itemColumns}
              loading={loading}
              pageSize={10}
              rowsPerPageOptions={[10, 25, 50]}
              sx={{ height: 320 }}
            />
          </Paper>
        </Box>
      </Stack>
    </PageContainer>
  );
}
