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
  IconButton,
  Snackbar,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Autorenew as RecalculateIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchCalculations,
  fetchCalculationSummary,
  recalculateCalculation,
  batchRecalculateCalculations,
} from '../../api/emissions-extended';
import PageHeader from '../../components/Page/PageHeader';
import ErrorAlert from '../../components/Page/ErrorAlert';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { useNotes } from '../../notes/NotesContext';
import {
  registerCalculationInspectorTabs,
  ScopeBadge,
  Scope2MethodChip,
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

  // ── Columns ───────────────────────────────────────────────────────────

  const columns = useMemo(() => [
    {
      field: 'period_name',
      headerName: 'Period',
      flex: 1.2,
      minWidth: 140,
      renderCell: (params) => (
        <Typography variant="body2">{params.value || params.row.period || '—'}</Typography>
      ),
    },
    {
      field: 'scope',
      headerName: 'Scope',
      width: 100,
      renderCell: (params) => <ScopeBadge value={params.value} />,
    },
    {
      field: 'scope2_method',
      headerName: 'Scope 2 method',
      width: 150,
      renderCell: (params) => (
        <Scope2MethodChip method={params.value} scope={params.row.scope} />
      ),
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
        <Typography variant="body2">{params.value || params.row.rule || '—'}</Typography>
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
                <RecalculateIcon fontSize="small" />
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
                <span>
                  <IconButton onClick={loadCalculations} size="small" disabled={loading}>
                    <RefreshIcon />
                  </IconButton>
                </span>
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

      {error && (
        <Box sx={{ px: 2.5, pb: 1 }}>
          <ErrorAlert message={error} onRetry={loadCalculations} />
        </Box>
      )}

      <FilteredDataGrid
        embedded
        rows={filteredCalculations}
        columns={columns}
        loading={loading}
        searchValue={filters.search}
        onSearchChange={(value) => setFilters((prev) => ({ ...prev, search: value }))}
        searchPlaceholder="Search periods, rules, org units…"
        filterDefs={[
          {
            key: 'scope',
            label: 'Scope',
            options: [
              { value: '1', label: 'Scope 1' },
              { value: '2', label: 'Scope 2' },
              { value: '3', label: 'Scope 3' },
            ],
          },
          {
            key: 'status',
            label: 'Status',
            options: Object.entries(STATUS_CFG).map(([value, cfg]) => ({ value, label: cfg.label })),
          },
        ]}
        filterValues={{ scope: filters.scope, status: filters.status }}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value || '' }))}
        onClearFilters={() => setFilters({ period: '', scope: '', status: '', search: '' })}
        emptyMessage="No calculations found"
        emptySubtext={filters.search || filters.scope || filters.status ? 'Try adjusting your filters.' : 'No calculations have been run yet.'}
        onRowClick={handleRowClick}
        highlightRow={(row) => row.id === selectedCalc?.id}
        checkboxSelection={isAdmin}
        rowSelectionModel={selectedRows.length
          ? { type: 'include', ids: new Set(selectedRows) }
          : { type: 'include', ids: new Set() }}
        onRowSelectionModelChange={(model) => setSelectedRows(Array.from(model?.ids || []))}
        getRowId={(row) => row.id}
      />

      {/* ── Recalculate Confirm Dialog ── */}
      <Dialog open={!!recalcConfirm} onClose={() => { if (!recalcLoading) { setRecalcConfirm(null); setRecalcTarget(null); } }}>
        <DialogTitle>Confirm Recalculation</DialogTitle>
        <DialogContent>
          {recalcConfirm === 'single' && recalcTarget && (
            <Typography variant="body2">
              Trigger recalculation for <strong>{recalcTarget.period_name || recalcTarget.id}</strong>?
              <Typography component="span" variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                This will re-run the calculation rules and update the emission values.
              </Typography>
            </Typography>
          )}
          {recalcConfirm === 'batch' && (
            <Typography variant="body2">
              Trigger recalculation for <strong>{selectedRows.length} selected</strong> calculation(s)?
              <Typography component="span" variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                All selected calculations will be re-processed.
              </Typography>
            </Typography>
          )}
          {recalcConfirm === 'all' && (
            <Typography variant="body2">
              Trigger recalculation for <strong>all {calculations.length} calculations</strong>?
              <Typography component="span" variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                This may take some time depending on the number of calculations.
              </Typography>
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
