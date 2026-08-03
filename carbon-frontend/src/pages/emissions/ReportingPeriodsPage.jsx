// src/pages/emissions/ReportingPeriodsPage.jsx
// E2-F1 — State-machine driven period management
// Replaces raw status dropdown with transition action buttons
// All colours via theme.palette, zero hardcoded hex

import React, { useEffect, useState, useCallback } from 'react';
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
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
  Lock as LockIcon,
  LockOpen as UnlockIcon,
  CheckCircle as ApproveIcon,
  Close as RejectIcon,
  Send as SubmitIcon,
  PlayArrow as OpenIcon,
  Archive as CloseIcon,
} from '@mui/icons-material';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchReportingPeriods,
  createReportingPeriod,
  updateReportingPeriod,
  deleteReportingPeriod,
  submitPeriod,
  openPeriod,
  lockPeriod,
  closePeriod,
} from '../../api/emissions-extended';

// ── Period status config ────────────────────────────────────────────────

const STATUS_CFG = {
  draft:     { label: 'Draft',     color: 'default' },
  open:      { label: 'Open',      color: 'info' },
  locked:    { label: 'Locked',    color: 'warning' },
  submitted: { label: 'Submitted', color: 'secondary' },
  verified:  { label: 'Verified',  color: 'success' },
  rejected:  { label: 'Rejected',  color: 'error' },
  closed:    { label: 'Closed',    color: 'default' },
};

// ── State machine: which transitions are valid per status ───────────────

const VALID_TRANSITIONS = {
  draft:     ['open'],
  open:      ['locked'],
  locked:    ['submitted', 'open'],
  submitted: ['verified', 'rejected'],
  rejected:  ['submitted'],
  verified:  ['closed'],
  closed:    [],
};

// ── Transition button config ────────────────────────────────────────────

const TRANSITION_BTN = {
  open:      { label: 'Open',      icon: <OpenIcon fontSize="small" />,     color: 'info' },
  locked:    { label: 'Lock',      icon: <LockIcon fontSize="small" />,    color: 'warning' },
  submitted: { label: 'Submit',    icon: <SubmitIcon fontSize="small" />,   color: 'primary' },
  verified:  { label: 'Verify',    icon: <ApproveIcon fontSize="small" />,  color: 'success' },
  rejected:  { label: 'Reject',    icon: <RejectIcon fontSize="small" />,   color: 'error' },
  closed:    { label: 'Close',     icon: <CloseIcon fontSize="small" />,    color: 'default' },
};

// ── Actions that require admin privilege ────────────────────────────────

const ADMIN_ACTIONS = new Set(['lock', 'close', 'verified', 'rejected']);

export default function ReportingPeriodsPage() {
  useDocumentTitle("Reporting Periods");
  const { token, canManageAllModules } = useAuth();
  const isAdmin = canManageAllModules();

  const [error, setError] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [form, setForm] = useState({
    name: '',
    start_date: '',
    end_date: '',
    period_type: 'annual',
    status: 'draft',
    is_baseline: false,
    description: '',
  });

  const loadPeriods = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchReportingPeriods(token);
      setPeriods(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load reporting periods');
      console.error('Error loading periods:', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadPeriods();
  }, [loadPeriods]);

  // ── Transition handler ────────────────────────────────────────────────

  const handleTransition = async (period, action) => {
    setActionLoading(true);
    try {
      const actionMap = {
        open:      () => openPeriod(period.id, token),
        locked:    () => lockPeriod(period.id, token),
        submitted: () => submitPeriod(period.id, token),
        // verified/rejected go through verification record API;
        // here they are gateways shown when there's a pending verification record
        verified:  () => { throw new Error('Use the Verification Workflow page to verify/reject.'); },
        rejected:  () => { throw new Error('Use the Verification Workflow page to verify/reject.'); },
        closed:    () => closePeriod(period.id, token),
      };
      if (actionMap[action]) {
        await actionMap[action]();
        setSnackbar({ open: true, message: `Period "${period.name}" → ${STATUS_CFG[action]?.label || action}`, severity: 'success' });
        await loadPeriods();
      }
    } catch (err) {
      setSnackbar({ open: true, message: err.message || `Transition to ${action} failed`, severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  // ── CRUD dialog handlers ──────────────────────────────────────────────

  const handleOpenDialog = (period = null) => {
    if (period) {
      setEditingPeriod(period);
      setForm({
        name: period.name,
        start_date: period.start_date,
        end_date: period.end_date,
        period_type: period.period_type || 'annual',
        status: period.status || 'draft',
        is_baseline: period.is_baseline || false,
        description: period.description || '',
      });
    } else {
      setEditingPeriod(null);
      setForm({
        name: '',
        start_date: '',
        end_date: '',
        period_type: 'annual',
        status: 'draft',
        is_baseline: false,
        description: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingPeriod(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSave = async () => {
    if (!form.name || !form.start_date || !form.end_date || !form.period_type) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      setError(null);
      if (editingPeriod) {
        await updateReportingPeriod(editingPeriod.id, form, token);
      } else {
        await createReportingPeriod(form, token);
      }
      handleCloseDialog();
      await loadPeriods();
    } catch (err) {
      setError(err.message || 'Failed to save reporting period');
      console.error('Error saving period:', err);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this reporting period?')) {
      try {
        setError(null);
        await deleteReportingPeriod(id, token);
        await loadPeriods();
      } catch (err) {
        setError(err.message || 'Failed to delete reporting period');
        console.error('Error deleting period:', err);
      }
    }
  };

  // ── Compute visible transition buttons for a period ───────────────────

  const getTransitionButtons = (period) => {
    const transitions = VALID_TRANSITIONS[period.status] || [];
    return transitions
      .filter((t) => !ADMIN_ACTIONS.has(t) || isAdmin)
      .map((t) => {
        const cfg = TRANSITION_BTN[t];
        if (!cfg) return null;
        return (
          <Tooltip key={t} title={cfg.label}>
            <IconButton
              size="small"
              color={cfg.color}
              disabled={actionLoading}
              onClick={() => handleTransition(period, t)}
            >
              {cfg.icon}
            </IconButton>
          </Tooltip>
        );
      })
      .filter(Boolean);
  };

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <Box sx={{ p: 3 }}>
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Reporting Periods
        </Typography>
        <Stack direction="row" gap={1}>
          <Tooltip title="Refresh">
            <IconButton
              onClick={loadPeriods}
              size="small"
              disabled={loading}
              sx={{ color: 'primary.main' }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            New Period
          </Button>
        </Stack>
      </Stack>

      <Paper sx={{ overflow: 'auto' }}>
        <TableContainer>
          <Table>
            <TableHead sx={{ backgroundColor: 'action.hover' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Start Date</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>End Date</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Transitions</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                    <Stack direction="row" spacing={1} justifyContent="center" alignItems="center">
                      <CircularProgress size={18} />
                      <Typography color="text.secondary">Loading...</Typography>
                    </Stack>
                  </TableCell>
                </TableRow>
              ) : periods.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">No reporting periods found</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                periods.map((period) => {
                  const cfg = STATUS_CFG[period.status] || STATUS_CFG.draft;
                  const buttons = getTransitionButtons(period);
                  return (
                    <TableRow key={period.id} hover>
                      <TableCell>
                        <Typography sx={{ fontWeight: 500, fontSize: '0.85rem' }}>
                          {period.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={period.period_type || 'annual'} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{new Date(period.start_date).toLocaleDateString()}</TableCell>
                      <TableCell>{new Date(period.end_date).toLocaleDateString()}</TableCell>
                      <TableCell>
                        <Chip
                          label={cfg.label}
                          size="small"
                          color={cfg.color}
                          variant="outlined"
                          sx={{ fontWeight: 600 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={0.5}>
                          {buttons.length > 0 ? buttons : (
                            <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>
                              Terminal
                            </Typography>
                          )}
                        </Stack>
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            onClick={() => handleOpenDialog(period)}
                            sx={{ color: 'primary.main' }}
                            disabled={actionLoading}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            onClick={() => handleDelete(period.id)}
                            sx={{ color: 'error.main' }}
                            disabled={actionLoading}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* ── Create/Edit Dialog ── */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingPeriod ? 'Edit Reporting Period' : 'Create New Reporting Period'}
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2}>
            <TextField
              label="Period Name"
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="e.g., FY 2024"
              fullWidth
            />
            <TextField
              label="Start Date"
              name="start_date"
              type="date"
              value={form.start_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="End Date"
              name="end_date"
              type="date"
              value={form.end_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              select
              label="Period Type"
              name="period_type"
              value={form.period_type}
              onChange={handleChange}
              fullWidth
              required
            >
              <MenuItem value="annual">Annual</MenuItem>
              <MenuItem value="quarterly">Quarterly</MenuItem>
              <MenuItem value="monthly">Monthly</MenuItem>
              <MenuItem value="custom">Custom</MenuItem>
            </TextField>
            {/* Status is read-only in edit mode — managed by state machine */}
            {editingPeriod && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Status (state-machine managed)
                </Typography>
                <Chip
                  label={(STATUS_CFG[form.status] || STATUS_CFG.draft).label}
                  size="small"
                  color={(STATUS_CFG[form.status] || STATUS_CFG.draft).color}
                  variant="outlined"
                  sx={{ fontWeight: 600 }}
                />
              </Box>
            )}
            {!editingPeriod && (
              <TextField
                select
                label="Status"
                name="status"
                value={form.status}
                onChange={handleChange}
                fullWidth
                required
              >
                <MenuItem value="draft">Draft</MenuItem>
                <MenuItem value="open">Open for Data Entry</MenuItem>
              </TextField>
            )}
            <TextField
              label="Description"
              name="description"
              value={form.description}
              onChange={handleChange}
              placeholder="Optional description"
              multiline
              rows={3}
              fullWidth
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_baseline}
                  onChange={handleChange}
                  name="is_baseline"
                />
              }
              label="Baseline Period (used for year-over-year comparisons)"
            />
          </Stack>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button variant="contained" onClick={handleSave}>
            {editingPeriod ? 'Update' : 'Create'}
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
