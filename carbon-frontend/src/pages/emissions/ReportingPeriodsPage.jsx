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
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';

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

// (Moved inside component — labels need t())

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

// ── Actions that require admin privilege ────────────────────────────────

const ADMIN_ACTIONS = new Set(['lock', 'close', 'verified', 'rejected']);

export default function ReportingPeriodsPage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('reportingPeriodsTitle'));
  const { token, canManageAllModules } = useAuth();
  const isAdmin = canManageAllModules();

  const STATUS_CFG = {
    draft:     { label: t('statusDraft'),     color: 'default' },
    open:      { label: t('statusOpen'),      color: 'info' },
    locked:    { label: t('statusLocked'),    color: 'warning' },
    submitted: { label: t('statusSubmitted'), color: 'secondary' },
    verified:  { label: t('statusVerified'),  color: 'success' },
    rejected:  { label: t('statusRejected'),  color: 'error' },
    closed:    { label: t('statusClosed'),    color: 'default' },
  };

  const TRANSITION_BTN = {
    open:      { label: t('actionOpen'),      icon: <OpenIcon fontSize="small" />,     color: 'info' },
    locked:    { label: t('actionLock'),      icon: <LockIcon fontSize="small" />,    color: 'warning' },
    submitted: { label: t('actionSubmit'),    icon: <SubmitIcon fontSize="small" />,   color: 'primary' },
    verified:  { label: t('actionVerify'),    icon: <ApproveIcon fontSize="small" />,  color: 'success' },
    rejected:  { label: t('actionReject'),    icon: <RejectIcon fontSize="small" />,   color: 'error' },
    closed:    { label: t('actionClose'),     icon: <CloseIcon fontSize="small" />,    color: 'default' },
  };

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
      setError(err.message || t('failedToLoadPeriods'));
      console.error('Error loading periods:', err);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

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
        setSnackbar({ open: true, message: t('periodTransitioned', { name: period.name, status: STATUS_CFG[action]?.label || action }), severity: 'success' });
        await loadPeriods();
      }
    } catch (err) {
      setSnackbar({ open: true, message: err.message || t('transitionFailed', { action }), severity: 'error' });
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
      setError(t('fillRequiredFields'));
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
      setError(err.message || t('failedToSavePeriod'));
      console.error('Error saving period:', err);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm(t('confirmDeletePeriod'))) {
      try {
        setError(null);
        await deleteReportingPeriod(id, token);
        await loadPeriods();
      } catch (err) {
        setError(err.message || t('failedToDeletePeriod'));
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
    <PageContainer>
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          {t('reportingPeriodsTitle')}
        </Typography>
        <Stack direction="row" gap={1}>
          <Tooltip title={t('refresh')}>
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
            {t('newPeriod')}
          </Button>
        </Stack>
      </Stack>

      <Paper sx={{ overflow: 'auto' }}>
        <TableContainer>
          <Table>
            <TableHead sx={{ backgroundColor: 'action.hover' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>{t('name')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('periodType')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('startDate')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('endDate')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('statusLabel')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('transitions')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">{t('actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                    <Stack direction="row" spacing={1} justifyContent="center" alignItems="center">
                      <CircularProgress size={18} />
                      <Typography color="text.secondary">{t('loading')}</Typography>
                    </Stack>
                  </TableCell>
                </TableRow>
              ) : periods.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">{t('noPeriodsFound')}</Typography>
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
                              {t('terminal')}
                            </Typography>
                          )}
                        </Stack>
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title={t('edit')}>
                          <IconButton
                            size="small"
                            onClick={() => handleOpenDialog(period)}
                            sx={{ color: 'primary.main' }}
                            disabled={actionLoading}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t('delete')}>
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
          {editingPeriod ? t('editPeriodTitle') : t('createPeriodTitle')}
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2}>
            <TextField
              label={t('periodName')}
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder={t('periodNamePlaceholder')}
              fullWidth
            />
            <TextField
              label={t('startDate')}
              name="start_date"
              type="date"
              value={form.start_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label={t('endDate')}
              name="end_date"
              type="date"
              value={form.end_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              select
              label={t('periodType')}
              name="period_type"
              value={form.period_type}
              onChange={handleChange}
              fullWidth
              required
            >
              <MenuItem value="annual">{t('annual')}</MenuItem>
              <MenuItem value="quarterly">{t('quarterly')}</MenuItem>
              <MenuItem value="monthly">{t('monthly')}</MenuItem>
              <MenuItem value="custom">{t('custom')}</MenuItem>
            </TextField>
            {/* Status is read-only in edit mode — managed by state machine */}
            {editingPeriod && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  {t('statusManaged')}
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
                label={t('statusLabel')}
                name="status"
                value={form.status}
                onChange={handleChange}
                fullWidth
                required
              >
                <MenuItem value="draft">{t('statusDraft')}</MenuItem>
                <MenuItem value="open">{t('openForDataEntry')}</MenuItem>
              </TextField>
            )}
            <TextField
              label={t('descriptionLabel')}
              name="description"
              value={form.description}
              onChange={handleChange}
              placeholder={t('descriptionPlaceholder')}
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
              label={t('baselinePeriod')}
            />
          </Stack>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCloseDialog}>{t('cancel')}</Button>
          <Button variant="contained" onClick={handleSave}>
            {editingPeriod ? t('update') : t('create')}
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
