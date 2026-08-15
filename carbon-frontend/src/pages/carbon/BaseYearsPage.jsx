// src/pages/carbon/BaseYearsPage.jsx
// GHG Protocol base years — admin CRUD + recalculation trigger
// Pattern: SBTiTargetsPage style — MUI Table, Drawer for create/edit, zero hardcoded hex

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  Alert,
  TextField,
  MenuItem,
  CircularProgress,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stack,
  IconButton,
  Snackbar,
  Switch,
  FormControlLabel,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import ReplayIcon from '@mui/icons-material/Replay';
import { useAuth } from '../../auth/AuthContext';
import PageHeader from '../../components/Page/PageHeader';
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
      sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
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
      sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
    />
  );
}

// ── BaseYearDrawer ─────────────────────────────────────────────────────

function BaseYearDrawer({ open, baseYear, periods, onSave, onClose }) {
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
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 440, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 3, fontSize: '1rem', fontWeight: 600 }}>
          {baseYear ? 'Edit Base Year' : 'New Base Year'}
        </Typography>
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
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSubmit} sx={{ flex: 1 }}>
              {baseYear ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
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
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Trigger Base Year Recalculation</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
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
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleConfirm} variant="contained">Trigger</Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function BaseYearsPage() {
  useDocumentTitle('Base Years');
  const { user, token, availablePerspectives } = useAuth();
  const [baseYears, setBaseYears] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [recalcTarget, setRecalcTarget] = useState(null);
  const [current, setCurrent] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [byData, pData] = await Promise.all([
        fetchBaseYears(token),
        fetchReportingPeriods(token),
      ]);
      setBaseYears(Array.isArray(byData) ? byData : byData?.results || []);
      setPeriods(Array.isArray(pData) ? pData : pData?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load base years');
    } finally {
      setLoading(false);
    }
  }, [token]);

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
      } else {
        await createBaseYear(payload, token);
      }
      setDrawerOpen(false);
      setCurrent(null);
      setSnackbar({ open: true, message: 'Base year saved', severity: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to save base year');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteBaseYear(id, token);
      setDeleteConfirm(null);
      setSnackbar({ open: true, message: 'Base year deleted', severity: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete base year');
    }
  };

  const handleRecalculate = async (data) => {
    try {
      await recalculateBaseYear(recalcTarget.id, data, token);
      setRecalcTarget(null);
      setSnackbar({ open: true, message: 'Recalculation trigger created', severity: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to trigger recalculation');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <PageHeader
        title="Base Years"
        description="GHG Protocol base years with recalculation policy. A base year is the benchmark against which future emission reductions are measured."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" sx={{ mr: 0.5 }}>
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
                New Base Year
              </Button>
            )}
          </Stack>
        }
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: 'action.hover' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>ID</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Year</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Reporting Period</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Recalculation Policy</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Threshold</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Open Triggers</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Status</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Created</TableCell>
              {isAdmin && <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {baseYears.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isAdmin ? 9 : 8} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                  No base years found. Click "New Base Year" to create one.
                </TableCell>
              </TableRow>
            ) : (
              baseYears.map((by) => (
                <TableRow key={by.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{by.id}</TableCell>
                  <TableCell align="center" sx={{ fontSize: '0.82rem', fontWeight: 500 }}>{by.year}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{by.reporting_period_name || by.reporting_period || '—'}</TableCell>
                  <TableCell><PolicyChip value={by.recalculation_policy} /></TableCell>
                  <TableCell align="center" sx={{ fontSize: '0.78rem' }}>{by.significance_threshold_pct ?? '—'}%</TableCell>
                  <TableCell align="center" sx={{ fontSize: '0.78rem' }}>{by.open_triggers_count ?? 0}</TableCell>
                  <TableCell><ActiveChip value={by.is_active} /></TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{fmtDate(by.created_at)}</TableCell>
                  {isAdmin && (
                    <TableCell align="center">
                      <IconButton size="small" onClick={() => handleEdit(by)} title="Edit">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => setRecalcTarget(by)} title="Trigger recalculation">
                        <ReplayIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => setDeleteConfirm(by.id)}
                        sx={{ color: 'error.main' }}
                        title="Delete"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <BaseYearDrawer
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

      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Base Year?</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.85rem' }}>This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button onClick={() => handleDelete(deleteConfirm)} variant="contained" color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

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
