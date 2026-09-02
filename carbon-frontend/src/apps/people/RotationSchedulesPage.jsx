// src/apps/people/RotationSchedulesPage.jsx
// People & Payroll — Rotation Schedules (full CRUD): create, read, update, delete.
// `config` is a JSON object — edited as a JSON textarea and validated with JSON.parse.
// All colours via theme tokens; apiFetch only; SystemDialog for the form.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
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
import AddIcon from '@mui/icons-material/Add';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchRotationSchedules,
  fetchEmployees,
  createRotationSchedule,
  updateRotationSchedule,
  deleteRotationSchedule,
} from '../../api/people';
import { buildEmployeeLabels, formatDate } from './utils';

const EMPTY_FORM = {
  employee: '',
  pattern: '',
  start_date: '',
  is_active: true,
  config: '{}',
};

/** Pretty-print a config object for the JSON textarea. */
function configToText(config) {
  if (config == null) return '{}';
  try {
    return JSON.stringify(config, null, 2);
  } catch (_e) {
    return '{}';
  }
}

/** Short one-line JSON summary for the table cell. */
function configSummary(config) {
  if (config == null) return '—';
  const text = JSON.stringify(config);
  return text.length > 60 ? `${text.slice(0, 57)}…` : text;
}

export default function RotationSchedulesPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('rotationTitle'));
  const { token } = useAuth();

  const [schedules, setSchedules] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [configError, setConfigError] = useState('');
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [schedulesData, employeesData] = await Promise.all([
        fetchRotationSchedules(token),
        fetchEmployees(token),
      ]);
      const scheduleList = Array.isArray(schedulesData) ? schedulesData : schedulesData?.results || [];
      const employeeList = Array.isArray(employeesData) ? employeesData : employeesData?.results || [];
      setSchedules(scheduleList);
      setEmployees(employeeList);
      setEmployeeLabels(buildEmployeeLabels(employeeList));
    } catch (err) {
      setError(err?.message || t('rotationLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const employeeName = (id) => employeeLabels[id] ?? id ?? '—';

  const showError = (err) => {
    setSnackbar({
      open: true,
      message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
      severity: 'error',
    });
  };

  const openCreate = () => {
    setEditingSchedule(null);
    setForm({ ...EMPTY_FORM });
    setConfigError('');
    setOpenDialog(true);
  };

  const openEdit = (schedule) => {
    setEditingSchedule(schedule);
    setForm({
      employee: schedule.employee ?? '',
      pattern: schedule.pattern ?? '',
      start_date: schedule.start_date ? String(schedule.start_date).slice(0, 10) : '',
      is_active: Boolean(schedule.is_active),
      config: configToText(schedule.config),
    });
    setConfigError('');
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingSchedule(null);
    setConfigError('');
  };

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (!form.employee || !form.pattern.trim() || !form.start_date) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    // Validate the JSON config client-side — on error show a field error and do NOT submit.
    let parsedConfig = {};
    const rawConfig = (form.config || '').trim();
    if (rawConfig) {
      try {
        parsedConfig = JSON.parse(rawConfig);
      } catch (_e) {
        setConfigError(t('rotationConfigInvalid'));
        return;
      }
    }

    const payload = {
      employee: Number(form.employee),
      pattern: form.pattern.trim(),
      start_date: form.start_date,
      is_active: Boolean(form.is_active),
      config: parsedConfig,
    };

    setSaving(true);
    try {
      if (editingSchedule) {
        await updateRotationSchedule(editingSchedule.id, payload, token);
      } else {
        await createRotationSchedule(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('rotationSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (schedule) => {
    if (!window.confirm(t('rotationDeleteConfirm'))) return;
    try {
      await deleteRotationSchedule(schedule.id, token);
      setSnackbar({ open: true, message: t('rotationDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  return (
    <PageContainer>
      <PageHeader
        icon={AutorenewIcon}
        title={t('rotationTitle')}
        subtitle={t('rotationSubtitle')}
        description={t('rotationDescription')}
        actions={
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddRotation')}
          </Button>
        }
      />

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : schedules.length === 0 ? (
        <EmptyState
          icon={<AutorenewIcon />}
          title={t('rotationEmpty')}
          description={t('rotationEmptyDesc')}
          actionLabel={t('actionAddRotation')}
          onAction={openCreate}
        />
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPattern')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStartDate')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colIsActive')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colConfig')}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {schedules.map((schedule) => (
                <TableRow key={schedule.id} hover>
                  <TableCell>{employeeName(schedule.employee)}</TableCell>
                  <TableCell>{schedule.pattern ?? '—'}</TableCell>
                  <TableCell>{formatDate(schedule.start_date)}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      color={schedule.is_active ? 'success' : 'default'}
                      label={schedule.is_active ? t('yes') : t('no')}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      component="span"
                      sx={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'text.secondary' }}
                    >
                      {configSummary(schedule.config)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t('actionEditRotation')}>
                      <IconButton size="small" onClick={() => openEdit(schedule)} sx={{ color: 'primary.main' }}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('actionDeleteRotation')}>
                      <IconButton size="small" onClick={() => handleDelete(schedule)} sx={{ color: 'error.main' }}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <SystemDialog
        open={openDialog}
        title={editingSchedule ? t('rotationEditTitle') : t('rotationCreateTitle')}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            select
            label={t('colEmployee')}
            name="employee"
            value={form.employee}
            onChange={handleChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colEmployee')}</MenuItem>
            {employees.map((employee) => (
              <MenuItem key={employee.id} value={employee.id}>
                {employee.employee_no ?? '—'} — {employee.full_name ?? ''}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colPattern')}
            name="pattern"
            value={form.pattern}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('colStartDate')}
            name="start_date"
            value={form.start_date}
            onChange={handleChange}
            fullWidth
            required
            type="date"
            InputLabelProps={{ shrink: true }}
          />
          <Box>
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={handleChange}
                  name="is_active"
                  color="primary"
                />
              }
              label={t('formIsActive')}
            />
          </Box>
          <TextField
            label={t('formConfig')}
            name="config"
            value={form.config}
            onChange={handleChange}
            fullWidth
            multiline
            minRows={4}
            spellCheck={false}
            error={Boolean(configError)}
            helperText={configError || undefined}
          />
        </Stack>
      </SystemDialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </PageContainer>
  );
}
