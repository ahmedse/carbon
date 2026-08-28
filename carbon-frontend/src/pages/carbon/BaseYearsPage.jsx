// src/pages/carbon/BaseYearsPage.jsx
// GHG Protocol base years — admin CRUD + recalculation trigger
// Canonical shell: FilteredDataGrid + SystemDialog + ConfirmDialog (see EmissionFactorsPage / GWPReferencePage)
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  TextField,
  MenuItem,
  Stack,
  IconButton,
  Switch,
  FormControlLabel,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { FONT } from '../../theme/themeTokens';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import ReplayIcon from '@mui/icons-material/Replay';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import {
  fetchBaseYears,
  createBaseYear,
  updateBaseYear,
  deleteBaseYear,
  recalculateBaseYear,
  fetchReportingPeriods,
} from '../../api/emissions-extended';

// ── PolicyChip ─────────────────────────────────────────────────────────

const POLICY_CHIP = {
  significant_only: { label: 'Significant Only', color: 'info' },
  all_changes: { label: 'All Changes', color: 'warning' },
  never: { label: 'Fixed (Never)', color: 'default' },
};

function PolicyChip({ value }) {
  const meta = POLICY_CHIP[value] || { label: value, color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

function ActiveChip({ value }) {
  return (
    <Chip
      label={value ? 'Active' : 'Inactive'}
      size="small"
      color={value ? 'success' : 'default'}
      variant="filled"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── BaseYearDialog ─────────────────────────────────────────────────────

function BaseYearDialog({ open, baseYear, periods, onSave, onClose }) {
  const [form, setForm] = useState({
    year: '',
    reporting_period: '',
    recalculation_policy: 'significant_only',
    significance_threshold_pct: '5.00',
    description: '',
    is_active: true,
  });

  useEffect(() => {
    if (baseYear) {
      setForm({
        year: baseYear.year ?? '',
        reporting_period: baseYear.reporting_period ?? '',
        recalculation_policy: baseYear.recalculation_policy || 'significant_only',
        significance_threshold_pct: baseYear.significance_threshold_pct ?? '5.00',
        description: baseYear.description || '',
        is_active: baseYear.is_active ?? true,
      });
    } else {
      setForm({
        year: '',
        reporting_period: '',
        recalculation_policy: 'significant_only',
        significance_threshold_pct: '5.00',
        description: '',
        is_active: true,
      });
    }
  }, [baseYear, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => onSave(form);

  return (
    <SystemDialog
      open={open}
      title={baseYear ? 'Edit Base Year' : 'New Base Year'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          {baseYear ? 'Update' : 'Create'}
        </Button>
      }
      width={540}
      height={620}
      minWidth={420}
      minHeight={460}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <TextField
            label="Year"
            name="year"
            type="number"
            value={form.year}
            onChange={handleChange}
            fullWidth
            required
            size="small"
            inputProps={{ min: 2000, max: 2100 }}
          />
          <TextField
            label="Reporting Period"
            select
            name="reporting_period"
            value={form.reporting_period}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          >
            {periods.map((p) => (
              <MenuItem key={p.id} value={p.id}>{p.name || `Period ${p.id}`}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Recalculation Policy"
            select
            name="recalculation_policy"
            value={form.recalculation_policy}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="significant_only">Recalculate only for significant changes</MenuItem>
            <MenuItem value="all_changes">Recalculate for all structural changes</MenuItem>
            <MenuItem value="never">Fixed base year — do not recalculate</MenuItem>
          </TextField>
          <TextField
            label="Significance Threshold (%)"
            name="significance_threshold_pct"
            type="number"
            value={form.significance_threshold_pct}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ min: 0, max: 100, step: 0.01 }}
          />
          <TextField
            label="Description"
            name="description"
            value={form.description}
            onChange={handleChange}
            fullWidth
            multiline
            rows={3}
            size="small"
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              />
            }
            label="Active"
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── RecalculateDialog ──────────────────────────────────────────────────

function RecalculateDialog({ open, onClose, onConfirm }) {
  const [form, setForm] = useState({
    trigger_type: 'threshold_exceeded',
    variance_pct: '',
    description: '',
  });

  useEffect(() => {
    if (open) {
      setForm({ trigger_type: 'threshold_exceeded', variance_pct: '', description: '' });
    }
  }, [open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleConfirm = () => {
    onConfirm({
      trigger_type: form.trigger_type,
      variance_pct: form.variance_pct ? Number(form.variance_pct) : null,
      description: form.description || 'Manual recalculation requested',
    });
  };

  return (
    <SystemDialog
      open={open}
      title="Trigger Base Year Recalculation"
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={handleConfirm}>
          Trigger
        </Button>
      }
      width={540}
      height={420}
      minWidth={420}
      minHeight={340}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <TextField
            label="Trigger Type"
            select
            name="trigger_type"
            value={form.trigger_type}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="structural_change">Structural Change</MenuItem>
            <MenuItem value="methodology_change">Methodology Change</MenuItem>
            <MenuItem value="error_correction">Error Correction</MenuItem>
            <MenuItem value="threshold_exceeded">Significance Threshold Exceeded</MenuItem>
          </TextField>
          <TextField
            label="Variance (%)"
            name="variance_pct"
            type="number"
            value={form.variance_pct}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ min: 0, max: 1000, step: 0.01 }}
          />
          <TextField
            label="Description"
            name="description"
            value={form.description}
            onChange={handleChange}
            fullWidth
            multiline
            rows={3}
            size="small"
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function BaseYearsPage() {
  useDocumentTitle('Base Years');
  const { user, token, availablePerspectives } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [baseYears, setBaseYears] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [recalcTarget, setRecalcTarget] = useState(null);
  const [current, setCurrent] = useState(null);
  const [searchText, setSearchText] = useState('');

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [byData, pData] = await Promise.all([
        fetchBaseYears(token),
        fetchReportingPeriods(token),
      ]);
      setBaseYears(Array.isArray(byData) ? byData : byData?.results || []);
      setPeriods(Array.isArray(pData) ? pData : pData?.results || []);
    } catch (err) {
      notifyFromError(err, 'Failed to load base years');
      setBaseYears([]);
      setPeriods([]);
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = () => {
    setCurrent(null);
    setDrawerOpen(true);
  };

  const handleEdit = (baseYear) => {
    setCurrent(baseYear);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    const payload = {
      ...formData,
      year: formData.year ? Number(formData.year) : null,
      reporting_period: formData.reporting_period ? Number(formData.reporting_period) : null,
      significance_threshold_pct: formData.significance_threshold_pct != null && formData.significance_threshold_pct !== ''
        ? Number(formData.significance_threshold_pct)
        : null,
    };
    try {
      if (current) {
        await updateBaseYear(current.id, payload, token);
        notify({ message: 'Base year updated', type: 'success' });
      } else {
        await createBaseYear(payload, token);
        notify({ message: 'Base year created', type: 'success' });
      }
      setDrawerOpen(false);
      setCurrent(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to save base year');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteBaseYear(id, token);
      notify({ message: 'Base year deleted', type: 'success' });
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete base year');
    }
  };

  const handleRecalculate = async (data) => {
    try {
      await recalculateBaseYear(recalcTarget.id, data, token);
      notify({ message: 'Recalculation trigger created', type: 'success' });
      setRecalcTarget(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to trigger recalculation');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  const filteredBaseYears = useMemo(() => {
    let filtered = baseYears;
    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        (by) =>
          (by.year != null && String(by.year).includes(query)) ||
          (by.reporting_period_name && by.reporting_period_name.toLowerCase().includes(query)) ||
          (by.recalculation_policy && by.recalculation_policy.toLowerCase().includes(query))
      );
    }
    return filtered;
  }, [baseYears, searchText]);

  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'year',
      headerName: 'Year',
      width: 90,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => value ?? '—',
    },
    {
      field: 'reporting_period',
      headerName: 'Reporting Period',
      flex: 1,
      minWidth: 160,
      valueGetter: (value, row) => row.reporting_period_name || row.reporting_period || '—',
    },
    {
      field: 'recalculation_policy',
      headerName: 'Recalculation Policy',
      width: 190,
      renderCell: (params) => <PolicyChip value={params.value} />,
    },
    {
      field: 'significance_threshold_pct',
      headerName: 'Threshold',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      valueGetter: (value, row) =>
        row.significance_threshold_pct != null ? `${row.significance_threshold_pct}%` : '—',
    },
    {
      field: 'open_triggers_count',
      headerName: 'Open Triggers',
      width: 130,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => value ?? 0,
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 100,
      renderCell: (params) => <ActiveChip value={params.value} />,
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 120,
      valueFormatter: (value) => fmtDate(value),
    },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 150,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => handleEdit(params.row)}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" onClick={() => setRecalcTarget(params.row)}>
                  <ReplayIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm(params.row.id)}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            ),
          },
        ]
      : []),
  ];

  return (
    <>
      <FilteredDataGrid
        title="Base Years"
        subtitle={`${filteredBaseYears.length} of ${baseYears.length} base years`}
        description="GHG Protocol base years with recalculation policy. A base year is the benchmark against which future emission reductions are measured."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" aria-label="Refresh base years">
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleCreate}>
                New Base Year
              </Button>
            )}
          </Stack>
        }
        rows={filteredBaseYears}
        loading={loading}
        columns={columns}
        countLabel={`${filteredBaseYears.length} of ${baseYears.length} base years`}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[]}
        onClearFilters={() => setSearchText('')}
        emptyMessage="No base years found"
        emptySubtext="Try adjusting your search"
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <BaseYearDialog
        open={drawerOpen}
        baseYear={current}
        periods={periods}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      <RecalculateDialog
        open={!!recalcTarget}
        onClose={() => setRecalcTarget(null)}
        onConfirm={handleRecalculate}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Base Year?"
        message="This action cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </>
  );
}
