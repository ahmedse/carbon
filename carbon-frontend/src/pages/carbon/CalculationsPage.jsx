// src/pages/carbon/CalculationsPage.jsx
// Calculations Browser — Phase 04 G2
// DataGrid of calculation runs with scope badges, filter bar, row-click detail panel
// Pattern: EntityDetailShell-inspired (grid + right panel with tabs)
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import {
  Autorenew as RecalculateIcon,
  CheckCircleOutline as VerifiedIcon,
  Close as CloseIcon,
  ErrorOutline as FailedIcon,
  HelpOutline as PendingIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  Schedule as ScheduledIcon,
} from '@mui/icons-material';
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

// ── Scope config ─────────────────────────────────────────────────────────

const SCOPE_CFG = {
  1: { label: 'Scope 1', palette: 'success' },
  2: { label: 'Scope 2', palette: 'info' },
  3: { label: 'Scope 3', palette: 'warning' },
};

// ── Status config ────────────────────────────────────────────────────────

const STATUS_CFG = {
  draft:      { label: 'Draft',      palette: 'default', Icon: PendingIcon },
  pending:    { label: 'Pending',    palette: 'warning', Icon: ScheduledIcon },
  calculated: { label: 'Calculated', palette: 'success', Icon: VerifiedIcon },
  failed:     { label: 'Failed',     palette: 'error',   Icon: FailedIcon },
  verified:   { label: 'Verified',   palette: 'info',    Icon: VerifiedIcon },
  rejected:   { label: 'Rejected',   palette: 'error',   Icon: FailedIcon },
};

// ── Helpers ──────────────────────────────────────────────────────────────

function ScopeBadge({ value }) {
  const theme = useTheme();
  const cfg = SCOPE_CFG[value] || SCOPE_CFG[1];
  const p = theme.palette[cfg.palette];
  return (
    <Chip
      label={cfg.label}
      size="small"
      sx={{
        height: 20,
        fontSize: '0.68rem',
        fontWeight: 700,
        bgcolor: p?.[50] || (p?.light + '30'),
        color: p?.dark || p?.main,
        border: 'none',
        '& .MuiChip-label': { px: 1 },
      }}
    />
  );
}

function StatusChip({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.draft;
  const Icon = cfg.Icon;
  return (
    <Chip
      icon={<Icon sx={{ fontSize: '13px !important' }} />}
      label={cfg.label}
      size="small"
      color={cfg.palette === 'default' ? undefined : cfg.palette}
      variant="outlined"
      sx={{ height: 20, fontSize: '0.68rem', '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: '4px' } }}
    />
  );
}

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function fmtNum(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Right Panel Detail Tabs ─────────────────────────────────────────────

function OverviewTab({ calc }) {
  if (!calc) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
          Select a calculation to view details.
        </Typography>
      </Box>
    );
  }

  const details = [
    { label: 'Period',           value: calc.period_name || calc.period || '—' },
    { label: 'Scope',            value: <ScopeBadge value={calc.scope} /> },
    { label: 'Status',           value: <StatusChip status={calc.status} /> },
    { label: 'Total tCO₂e',      value: fmtNum(calc.total_emissions || calc.total_co2e) },
    { label: 'Rule Used',        value: calc.rule_name || calc.rule || '—' },
    { label: 'Rule Version',     value: calc.rule_version || '—' },
    { label: 'Org Unit',         value: calc.org_unit_name || calc.org_unit || '—' },
    { label: 'Data Sources',     value: calc.data_source_count != null ? String(calc.data_source_count) : '—' },
    { label: 'Rows Processed',   value: calc.rows_processed != null ? String(calc.rows_processed) : '—' },
    { label: 'Last Calculated',  value: fmtDate(calc.last_calculated || calc.updated_at) },
    { label: 'Calculated By',    value: calc.calculated_by_name || calc.calculated_by || '—' },
  ];

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2, fontSize: '0.8rem' }}>
      <Typography sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem', color: 'text.secondary' }}>
        Calculation Metadata
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 0.5 }}>
        {details.map(({ label, value }) => (
          <Box
            key={label}
            sx={{
              display: 'grid',
              gridTemplateColumns: '120px 1fr',
              gap: 1,
              py: 0.75,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{label}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
              {typeof value === 'string' ? (
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: 'text.primary' }}>{value}</Typography>
              ) : value}
            </Box>
          </Box>
        ))}
      </Box>

      {calc.traceability_notes && (
        <Box sx={{ pt: 1 }}>
          <Typography sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem', color: 'text.secondary', mb: 1 }}>
            Traceability
          </Typography>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{calc.traceability_notes}</Typography>
        </Box>
      )}
    </Box>
  );
}

function DataQualityTab({ calc }) {
  if (!calc) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
          Select a calculation to view data quality metrics.
        </Typography>
      </Box>
    );
  }

  const dq = calc.data_quality || {};
  const completeness = dq.completeness_score ?? calc.dq_completeness;
  const accuracy = dq.accuracy_score ?? calc.dq_accuracy;
  const timeliness = dq.timeliness_score ?? calc.dq_timeliness;

  const metrics = [
    { label: 'Completeness', value: completeness, good: 80, warn: 60 },
    { label: 'Accuracy',     value: accuracy,     good: 80, warn: 60 },
    { label: 'Timeliness',   value: timeliness,   good: 80, warn: 60 },
  ];

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem', color: 'text.secondary' }}>
        Data Quality Metrics
      </Typography>
      {metrics.every(m => m.value == null) ? (
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
          No quality metrics available for this calculation.
        </Typography>
      ) : (
        metrics.map(({ label, value, good, warn }) => {
          const pct = value != null ? Math.round(value) : null;
          let color = 'text.secondary';
          if (pct != null) {
            color = pct >= good ? 'success.main' : pct >= warn ? 'warning.main' : 'error.main';
          }
          return (
            <Box key={label}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{label}</Typography>
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color }}>{pct != null ? `${pct}%` : 'N/A'}</Typography>
              </Box>
              {pct != null && (
                <LinearProgress
                  variant="determinate"
                  value={pct}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    bgcolor: 'action.hover',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: color,
                    },
                  }}
                />
              )}
            </Box>
          );
        })
      )}

      {calc.dq_issues && calc.dq_issues.length > 0 && (
        <Box sx={{ pt: 1 }}>
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: 'error.main', mb: 1 }}>
            {calc.dq_issues.length} Issue{calc.dq_issues.length > 1 ? 's' : ''}
          </Typography>
          {calc.dq_issues.map((issue, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, py: 0.5, alignItems: 'flex-start' }}>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'error.main', mt: 0.5, flexShrink: 0 }} />
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{issue}</Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function CalculationsPage() {
  const { user, token } = useAuth();
  const isAdmin = user?.is_superuser || user?.is_staff;

  // Data
  const [calculations, setCalculations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCalc, setSelectedCalc] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailTab, setDetailTab] = useState(0);

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

  // Load detail when row selected
  useEffect(() => {
    if (!selectedCalc) return;
    setDetailLoading(true);
    fetchCalculationSummary(selectedCalc.id, token)
      .then((data) => setSelectedCalc((prev) => ({ ...prev, ...data })))
      .catch(() => { /* detail load failed silently; row data still shown */ })
      .finally(() => setDetailLoading(false));
  }, [selectedCalc?.id]); // eslint-disable-line

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleRowClick = (params) => {
    setSelectedCalc(params.row);
    setDetailTab(0);
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
        <Typography sx={{ fontSize: '0.8rem', fontWeight: 500 }}>{params.value || params.row.period || '—'}</Typography>
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
        <Typography sx={{ fontSize: '0.78rem' }}>{params.value || params.row.rule || '—'}</Typography>
      ),
    },
    {
      field: 'last_calculated',
      headerName: 'Last Calculated',
      width: 160,
      valueFormatter: (value) => fmtDate(value),
    },
  ], []);

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

  // ── States ────────────────────────────────────────────────────────────

  const detailPanelCalc = selectedCalc;

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ px: 2.5, pt: 2, pb: 0 }}>
        <PageHeader
          title="Calculations Browser"
          subtitle="View and manage emission calculations across periods and scopes"
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
                  <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
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

      {/* Main Content: Grid + Detail Panel */}
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
              autoHeight
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
                minHeight: 400,
                bgcolor: 'background.paper',
                '& .MuiDataGrid-cell': { outline: 'none' },
                '& .MuiDataGrid-row.Mui-selected': {
                  bgcolor: 'action.selected',
                },
              }}
            />
          )}
        </Box>

        {/* Right Detail Panel */}
        <Box
          sx={{
            width: 360,
            flexShrink: 0,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            bgcolor: 'background.paper',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* Panel Header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 1.5,
              py: 1,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {detailPanelCalc ? detailPanelCalc.period_name || 'Calculation' : 'Details'}
            </Typography>
            {detailPanelCalc && (
              <IconButton size="small" onClick={() => setSelectedCalc(null)}>
                <CloseIcon sx={{ fontSize: 16 }} />
              </IconButton>
            )}
          </Box>

          {/* Panel Tabs */}
          {detailPanelCalc && (
            <Tabs
              value={detailTab}
              onChange={(_, v) => setDetailTab(v)}
              sx={{
                minHeight: 36,
                px: 1,
                '& .MuiTab-root': { minHeight: 36, fontSize: '0.72rem', textTransform: 'none', px: 1 },
              }}
            >
              <Tab label="Overview" />
              <Tab label="Data Quality" />
            </Tabs>
          )}

          {/* Panel Content */}
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            {detailLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress size={24} />
              </Box>
            ) : detailTab === 0 ? (
              <OverviewTab calc={detailPanelCalc} />
            ) : (
              <DataQualityTab calc={detailPanelCalc} />
            )}
          </Box>

          {/* Panel Actions (recalculate from detail) */}
          {detailPanelCalc && isAdmin && !detailLoading && (
            <Box sx={{ p: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
              <Button
                fullWidth
                variant="outlined"
                size="small"
                startIcon={<RecalculateIcon />}
                onClick={() => { setRecalcTarget(detailPanelCalc); setRecalcConfirm('single'); }}
                disabled={recalcLoading}
              >
                Recalculate This Calculation
              </Button>
            </Box>
          )}
        </Box>
      </Box>

      {/* ── Recalculate Confirm Dialog ── */}
      <Dialog open={!!recalcConfirm} onClose={() => { if (!recalcLoading) { setRecalcConfirm(null); setRecalcTarget(null); } }}>
        <DialogTitle>Confirm Recalculation</DialogTitle>
        <DialogContent>
          {recalcConfirm === 'single' && recalcTarget && (
            <Typography sx={{ fontSize: '0.85rem' }}>
              Trigger recalculation for <strong>{recalcTarget.period_name || recalcTarget.id}</strong>?
              <Box component="span" sx={{ display: 'block', mt: 1, fontSize: '0.78rem', color: 'text.secondary' }}>
                This will re-run the calculation rules and update the emission values.
              </Box>
            </Typography>
          )}
          {recalcConfirm === 'batch' && (
            <Typography sx={{ fontSize: '0.85rem' }}>
              Trigger recalculation for <strong>{selectedRows.length} selected</strong> calculation(s)?
              <Box component="span" sx={{ display: 'block', mt: 1, fontSize: '0.78rem', color: 'text.secondary' }}>
                All selected calculations will be re-processed.
              </Box>
            </Typography>
          )}
          {recalcConfirm === 'all' && (
            <Typography sx={{ fontSize: '0.85rem' }}>
              Trigger recalculation for <strong>all {calculations.length} calculations</strong>?
              <Box component="span" sx={{ display: 'block', mt: 1, fontSize: '0.78rem', color: 'text.secondary' }}>
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
    </Box>
  );
}
