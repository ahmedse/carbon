// src/pages/carbon/CalculationsPage.jsx
// Calculations Browser — Phase 04 G2
// DataGrid of calculation runs with scope badges, filter bar, and a per-row
// Recalculate action. Row details render in the global Contextual Inspector
// drawer via registerCalculationInspectorTabs (ADR-0019).
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import {
  Autorenew as RecalculateIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { FONT } from '../../theme/themeTokens';
import PageContainer from '../../components/layout/PageContainer';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchCalculations,
  fetchCalculationSummary,
  recalculateCalculation,
  batchRecalculateCalculations,
} from '../../api/emissions-extended';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import { useNotes } from '../../notes/NotesContext';
import {
  registerCalculationInspectorTabs,
  ScopeBadge,
  StatusChip,
  fmtDate,
  fmtNum,
  STATUS_CFG,
} from '../../inspector/tabs/calculationTabs';

// ── Main Component ─────────────────────────────────────────────────────

export default function CalculationsPage() {
  useDocumentTitle("Calculations");
  const { user, token, availablePerspectives } = useAuth();
  const isAdmin = user?.is_superuser || user?.is_staff || (availablePerspectives || []).includes('carbon-admin');

  // Data
  const [calculations, setCalculations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCalc, setSelectedCalc] = useState(null);

  // Filters
  const [filters, setFilters] = useState({ period: '', scope: '', status: '', search: '' });

  // Recalculate state
  const [recalcLoading, setRecalcLoading] = useState(false);
  const [recalcConfirm, setRecalcConfirm] = useState(null); // null | 'single' | 'batch'
  const [recalcTarget, setRecalcTarget] = useState(null);
  const [selectedRows, setSelectedRows] = useState([]);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // ── Load ──────────────────────────────────────────────────────────────

  const loadCalculations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCalculations(filters, token);
      setCalculations(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load calculations');
    } finally {
      setLoading(false);
    }
  }, [filters, token]);

  useEffect(() => {
    loadCalculations();
  }, [loadCalculations]);

  // Enrich the selected row with the full summary so the inspector drawer can
  // render richer metadata (data quality, traceability, calculated by, …).
  useEffect(() => {
    if (!selectedCalc) return;
    fetchCalculationSummary(selectedCalc.id, token)
      .then((data) => setSelectedCalc((prev) => ({ ...prev, ...data })))
      .catch(() => { /* detail load failed silently; row data still shown */ });
  }, [selectedCalc?.id]); // eslint-disable-line

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleRowClick = (params) => {
    setSelectedCalc(params.row);
  };

  const handleRecalculateSingle = async () => {
    if (!recalcTarget) return;
    setRecalcLoading(true);
    try {
      await recalculateCalculation(recalcTarget.id, token);
      setSnackbar({ open: true, message: `Recalculation triggered for ${recalcTarget.period_name || recalcTarget.id}`, severity: 'success' });
      setRecalcConfirm(null);
      setRecalcTarget(null);
      await loadCalculations();
    } catch (err) {
      setSnackbar({ open: true, message: err.message || 'Recalculation failed', severity: 'error' });
    } finally {
      setRecalcLoading(false);
    }
  };

  const handleBatchRecalculate = async () => {
    if (!selectedRows.length) return;
    setRecalcLoading(true);
    try {
      await batchRecalculateCalculations(selectedRows, token);
      setSnackbar({ open: true, message: `Batch recalculation triggered for ${selectedRows.length} item(s)`, severity: 'success' });
      setRecalcConfirm(null);
      setSelectedRows([]);
      await loadCalculations();
    } catch (err) {
      setSnackbar({ open: true, message: err.message || 'Batch recalculation failed', severity: 'error' });
    } finally {
      setRecalcLoading(false);
    }
  };

  const handleFilterChange = (field) => (e) => {
    setFilters((prev) => ({ ...prev, [field]: e.target.value }));
  };

  // ── Columns ───────────────────────────────────────────────────────────

  const columns = useMemo(() => [
    {
      field: 'period_name',
      headerName: 'Period',
      flex: 1.2,
      minWidth: 140,
      renderCell: (params) => (
        <Typography sx={{ ...FONT.body, fontWeight: 500 }}>{params.value || params.row.period || '—'}</Typography>
      ),
    },
    {
      field: 'scope',
      headerName: 'Scope',
      width: 100,
      renderCell: (params) => <ScopeBadge value={params.value} />,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => <StatusChip status={params.value} />,
    },
    {
      field: 'total_co2e',
      headerName: 'tCO₂e',
      width: 110,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => fmtNum(value),
    },
    {
      field: 'rule_name',
      headerName: 'Rule Used',
      flex: 1,
      minWidth: 130,
      renderCell: (params) => (
        <Typography sx={{ ...FONT.body }}>{params.value || params.row.rule || '—'}</Typography>
      ),
    },
    {
      field: 'last_calculated',
      headerName: 'Last Calculated',
      width: 160,
      valueFormatter: (value) => fmtDate(value),
    },
    ...(isAdmin ? [{
      field: 'actions',
      headerName: '',
      width: 90,
      sortable: false,
      disableColumnMenu: true,
      renderCell: ({ row }) => (
        <Stack direction="row" spacing={0.25} onClick={(e) => e.stopPropagation()}>
          <Tooltip title="Recalculate">
            <span>
              <IconButton
                size="small"
                disabled={recalcLoading}
                onClick={() => { setRecalcTarget(row); setRecalcConfirm('single'); }}
              >
                <RecalculateIcon sx={{ fontSize: '0.9375rem' }} />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      ),
    }] : []),
  ], [isAdmin, recalcLoading]);

  // ── Filtered list (client-side) ──────────────────────────────────────

  const filteredCalculations = useMemo(() => {
    if (!filters.search) return calculations;
    const q = filters.search.toLowerCase();
    return calculations.filter(
      (c) =>
        (c.period_name || '').toLowerCase().includes(q) ||
        (c.rule_name || '').toLowerCase().includes(q) ||
        (c.org_unit_name || '').toLowerCase().includes(q)
    );
  }, [calculations, filters.search]);

  // ── Contextual Inspector (global drawer) ────────────────────────────────

  const { setContexts } = useNotes();

  // Register the calculation tabs once; unregister on unmount.
  useEffect(() => registerCalculationInspectorTabs(), []);

  // Expose the selected calculation as the active inspector context with a
  // payload fast-path ({ entityData }) so the tabs render without a refetch.
  const inspectorContext = useMemo(
    () => [{
      entityType: 'calculation',
      entityId: selectedCalc?.id ?? null,
      label: selectedCalc?.period_name || selectedCalc?.period || 'Calculation',
      payload: { entityData: selectedCalc },
    }],
    [selectedCalc],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <PageContainer sx={{ height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ px: 2.5, pt: 2, pb: 0 }}>
        <PageHeader
          title="Calculations Browser"
          subtitle="View and manage emission calculations across periods and scopes"
          description="Each row is a calculation result: emission factor × activity data = tCO₂e. Filter by scope, status, and period. Recalculate or batch-process for audit readiness."
          actions={
            <Stack direction="row" spacing={1}>
              <Tooltip title="Refresh">
                <IconButton onClick={loadCalculations} size="small" disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
              {selectedRows.length > 0 && isAdmin && (
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<RecalculateIcon />}
                  onClick={() => { setRecalcConfirm('batch'); }}
                  disabled={recalcLoading}
                >
                  Recalculate Selected ({selectedRows.length})
                </Button>
              )}
              {isAdmin && (
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<RecalculateIcon />}
                  onClick={() => {
                    setRecalcConfirm('all');
                  }}
                  disabled={recalcLoading || calculations.length === 0}
                >
                  Recalculate All
                </Button>
              )}
            </Stack>
          }
        />
      </Box>

      {/* Filter Bar */}
      <Box sx={{ px: 2.5, py: 1.5 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center">
          <TextField
            placeholder="Search periods, rules, org units…"
            size="small"
            value={filters.search}
            onChange={handleFilterChange('search')}
            sx={{ flex: 1, minWidth: 200 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="scope-filter-label">Scope</InputLabel>
            <Select
              labelId="scope-filter-label"
              value={filters.scope}
              label="Scope"
              onChange={handleFilterChange('scope')}
            >
              <MenuItem value="">All Scopes</MenuItem>
              <MenuItem value="1">Scope 1</MenuItem>
              <MenuItem value="2">Scope 2</MenuItem>
              <MenuItem value="3">Scope 3</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="status-filter-label">Status</InputLabel>
            <Select
              labelId="status-filter-label"
              value={filters.status}
              label="Status"
              onChange={handleFilterChange('status')}
            >
              <MenuItem value="">All Statuses</MenuItem>
              {Object.entries(STATUS_CFG).map(([key, cfg]) => (
                <MenuItem key={key} value={key}>{cfg.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Box>

      {error && (
        <Box sx={{ px: 2.5, pb: 1 }}>
          <ErrorAlert message={error} onRetry={loadCalculations} />
        </Box>
      )}

      {/* Main Content: Grid */}
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden', px: 2.5, pb: 2, gap: 2 }}>
        {/* DataGrid */}
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {loading ? (
            <LoadingSkeleton variant="table" />
          ) : filteredCalculations.length === 0 ? (
            <EmptyState
              icon={<RecalculateIcon />}
              title="No calculations found"
              description={filters.search || filters.scope || filters.status ? 'Try adjusting your filters.' : 'No calculations have been run yet.'}
              actionLabel={!filters.search && !filters.scope && !filters.status ? 'Refresh' : undefined}
              onAction={loadCalculations}
            />
          ) : (
            <DataGrid
              rows={filteredCalculations}
              columns={columns}
              pageSizeOptions={[25, 50, 100]}
              initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
              disableRowSelectionOnClick
              checkboxSelection={isAdmin}
              {...(isAdmin ? {
                rowSelectionModel: selectedRows,
                onRowSelectionModelChange: (ids) => setSelectedRows(ids),
              } : {})}
              onRowClick={handleRowClick}
              getRowId={(row) => row.id}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 2,
                height: '100%',
                bgcolor: 'background.paper',
                '& .MuiDataGrid-cell': { outline: 'none' },
                '& .MuiDataGrid-row.Mui-selected': {
                  bgcolor: 'action.selected',
                },
              }}
            />
          )}
        </Box>
      </Box>

      {/* ── Recalculate Confirm Dialog ── */}
      <Dialog open={!!recalcConfirm} onClose={() => { if (!recalcLoading) { setRecalcConfirm(null); setRecalcTarget(null); } }}>
        <DialogTitle>Confirm Recalculation</DialogTitle>
        <DialogContent>
          {recalcConfirm === 'single' && recalcTarget && (
            <Typography sx={{ ...FONT.body }}>
              Trigger recalculation for <strong>{recalcTarget.period_name || recalcTarget.id}</strong>?
              <Box component="span" sx={{ display: 'block', mt: 1, ...FONT.bodySmall, color: 'text.secondary' }}>
                This will re-run the calculation rules and update the emission values.
              </Box>
            </Typography>
          )}
          {recalcConfirm === 'batch' && (
            <Typography sx={{ ...FONT.body }}>
              Trigger recalculation for <strong>{selectedRows.length} selected</strong> calculation(s)?
              <Box component="span" sx={{ display: 'block', mt: 1, ...FONT.bodySmall, color: 'text.secondary' }}>
                All selected calculations will be re-processed.
              </Box>
            </Typography>
          )}
          {recalcConfirm === 'all' && (
            <Typography sx={{ ...FONT.body }}>
              Trigger recalculation for <strong>all {calculations.length} calculations</strong>?
              <Box component="span" sx={{ display: 'block', mt: 1, ...FONT.bodySmall, color: 'text.secondary' }}>
                This may take some time depending on the number of calculations.
              </Box>
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setRecalcConfirm(null); setRecalcTarget(null); }} disabled={recalcLoading}>
            Cancel
          </Button>
          <Button
            onClick={recalcConfirm === 'single' ? handleRecalculateSingle : handleBatchRecalculate}
            variant="contained"
            disabled={recalcLoading}
            startIcon={recalcLoading ? <CircularProgress size={16} /> : <RecalculateIcon />}
          >
            {recalcLoading ? 'Recalculating…' : 'Confirm'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Snackbar ── */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </PageContainer>
  );
}
