// src/apps/people/AttendancePage.jsx
// People & Payroll — attendance records & permissions (full CRUD).
// All colours via theme tokens; apiFetch only; SystemDialog for the forms.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
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
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AddIcon from '@mui/icons-material/Add';
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
  fetchEmployees,
  fetchAttendanceRecords,
  fetchAttendancePermissions,
  createAttendanceRecord,
  updateAttendanceRecord,
  deleteAttendanceRecord,
  createAttendancePermission,
  updateAttendancePermission,
  deleteAttendancePermission,
} from '../../api/people';
import { buildEmployeeLabels, formatDate, statusColor, statusLabelKey } from './utils';

const EMPTY_RECORD = {
  employee: '',
  date: '',
  hours_worked: '',
  overtime_hours: '',
  status: 'present',
};

const EMPTY_PERMISSION = {
  employee: '',
  date: '',
  permission_type: '',
  hours: '',
  approved: false,
  notes: '',
};

const ATTENDANCE_STATUSES = ['present', 'absent', 'leave', 'permission'];

export default function AttendancePage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('attendanceTitle'));
  const { token } = useAuth();

  const [records, setRecords] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [recordDialogOpen, setRecordDialogOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [recordForm, setRecordForm] = useState({ ...EMPTY_RECORD });

  const [permissionDialogOpen, setPermissionDialogOpen] = useState(false);
  const [editingPermission, setEditingPermission] = useState(null);
  const [permissionForm, setPermissionForm] = useState({ ...EMPTY_PERMISSION });

  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [employeesData, recordsData, permissionsData] = await Promise.all([
        fetchEmployees(token),
        fetchAttendanceRecords(token),
        fetchAttendancePermissions(token),
      ]);
      const employeeList = Array.isArray(employeesData) ? employeesData : employeesData?.results || [];
      setEmployees(employeeList);
      setEmployeeLabels(buildEmployeeLabels(employeeList));
      setRecords(Array.isArray(recordsData) ? recordsData : recordsData?.results || []);
      setPermissions(Array.isArray(permissionsData) ? permissionsData : permissionsData?.results || []);
    } catch (err) {
      setError(err?.message || t('attendanceLoadError'));
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

  // ---- Attendance Records ----

  const openCreateRecord = () => {
    setEditingRecord(null);
    setRecordForm({ ...EMPTY_RECORD });
    setRecordDialogOpen(true);
  };

  const openEditRecord = (record) => {
    setEditingRecord(record);
    setRecordForm({
      employee: record.employee ?? '',
      date: record.date ? String(record.date).slice(0, 10) : '',
      hours_worked: record.hours_worked != null ? String(record.hours_worked) : '',
      overtime_hours: record.overtime_hours != null ? String(record.overtime_hours) : '',
      status: record.status ?? 'present',
    });
    setRecordDialogOpen(true);
  };

  const closeRecordDialog = () => {
    setRecordDialogOpen(false);
    setEditingRecord(null);
  };

  const handleRecordChange = (event) => {
    const { name, value } = event.target;
    setRecordForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveRecord = async () => {
    if (!recordForm.employee || !recordForm.date) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(recordForm.employee),
      date: recordForm.date,
      hours_worked: recordForm.hours_worked === '' ? 0 : Number(recordForm.hours_worked),
      overtime_hours: recordForm.overtime_hours === '' ? 0 : Number(recordForm.overtime_hours),
      status: recordForm.status,
    };

    setSaving(true);
    try {
      if (editingRecord) {
        await updateAttendanceRecord(editingRecord.id, payload, token);
      } else {
        await createAttendanceRecord(payload, token);
      }
      closeRecordDialog();
      setSnackbar({ open: true, message: t('attendanceRecordSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRecord = async (record) => {
    if (!window.confirm(t('attendanceRecordDeleteConfirm'))) return;
    try {
      await deleteAttendanceRecord(record.id, token);
      setSnackbar({ open: true, message: t('attendanceRecordDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  // ---- Attendance Permissions ----

  const openCreatePermission = () => {
    setEditingPermission(null);
    setPermissionForm({ ...EMPTY_PERMISSION });
    setPermissionDialogOpen(true);
  };

  const openEditPermission = (permission) => {
    setEditingPermission(permission);
    setPermissionForm({
      employee: permission.employee ?? '',
      date: permission.date ? String(permission.date).slice(0, 10) : '',
      permission_type: permission.permission_type ?? '',
      hours: permission.hours != null ? String(permission.hours) : '',
      approved: Boolean(permission.approved),
      notes: permission.notes ?? '',
    });
    setPermissionDialogOpen(true);
  };

  const closePermissionDialog = () => {
    setPermissionDialogOpen(false);
    setEditingPermission(null);
  };

  const handlePermissionChange = (event) => {
    const { name, value, checked, type } = event.target;
    setPermissionForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSavePermission = async () => {
    if (!permissionForm.employee || !permissionForm.date || !permissionForm.permission_type.trim()) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(permissionForm.employee),
      date: permissionForm.date,
      permission_type: permissionForm.permission_type.trim(),
      hours: permissionForm.hours === '' ? 0 : Number(permissionForm.hours),
      approved: Boolean(permissionForm.approved),
    };
    if (permissionForm.notes && permissionForm.notes.trim()) {
      payload.notes = permissionForm.notes.trim();
    }

    setSaving(true);
    try {
      if (editingPermission) {
        await updateAttendancePermission(editingPermission.id, payload, token);
      } else {
        await createAttendancePermission(payload, token);
      }
      closePermissionDialog();
      setSnackbar({ open: true, message: t('attendancePermissionSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePermission = async (permission) => {
    if (!window.confirm(t('attendancePermissionDeleteConfirm'))) return;
    try {
      await deleteAttendancePermission(permission.id, token);
      setSnackbar({ open: true, message: t('attendancePermissionDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  const renderDialogs = () => (
    <>
      <SystemDialog
        open={recordDialogOpen}
        title={editingRecord ? t('attendanceRecordEditTitle') : t('attendanceRecordCreateTitle')}
        onClose={closeRecordDialog}
        onCancel={closeRecordDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSaveRecord} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            select
            label={t('colEmployee')}
            name="employee"
            value={recordForm.employee}
            onChange={handleRecordChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colEmployee')}</MenuItem>
            {employees.map((emp) => (
              <MenuItem key={emp.id} value={emp.id}>{employeeName(emp.id)}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colDate')}
            name="date"
            value={recordForm.date}
            onChange={handleRecordChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('colHoursWorked')}
            name="hours_worked"
            value={recordForm.hours_worked}
            onChange={handleRecordChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
          />
          <TextField
            label={t('colOvertimeHours')}
            name="overtime_hours"
            value={recordForm.overtime_hours}
            onChange={handleRecordChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
          />
          <TextField
            select
            label={t('colStatus')}
            name="status"
            value={recordForm.status}
            onChange={handleRecordChange}
            fullWidth
            required
          >
            {ATTENDANCE_STATUSES.map((status) => (
              <MenuItem key={status} value={status}>{t(statusLabelKey(status))}</MenuItem>
            ))}
          </TextField>
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={permissionDialogOpen}
        title={editingPermission ? t('attendancePermissionEditTitle') : t('attendancePermissionCreateTitle')}
        onClose={closePermissionDialog}
        onCancel={closePermissionDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSavePermission} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            select
            label={t('colEmployee')}
            name="employee"
            value={permissionForm.employee}
            onChange={handlePermissionChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colEmployee')}</MenuItem>
            {employees.map((emp) => (
              <MenuItem key={emp.id} value={emp.id}>{employeeName(emp.id)}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colDate')}
            name="date"
            value={permissionForm.date}
            onChange={handlePermissionChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('colPermissionType')}
            name="permission_type"
            value={permissionForm.permission_type}
            onChange={handlePermissionChange}
            fullWidth
            required
          />
          <TextField
            label={t('colHours')}
            name="hours"
            value={permissionForm.hours}
            onChange={handlePermissionChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
          />
          <TextField
            label={t('formNotes')}
            name="notes"
            value={permissionForm.notes}
            onChange={handlePermissionChange}
            multiline
            minRows={2}
            fullWidth
          />
          <Box>
            <Switch
              checked={permissionForm.approved}
              onChange={handlePermissionChange}
              name="approved"
              color="primary"
            />
            <Typography component="span" variant="body2">{t('colApproved')}</Typography>
          </Box>
        </Stack>
      </SystemDialog>
    </>
  );

  const header = <PageHeader icon={AccessTimeIcon} title={t('attendanceTitle')} subtitle={t('attendanceSubtitle')} />;

  if (loading) {
    return (
      <PageContainer>
        {header}
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        {header}
        <ErrorAlert message={error} onRetry={loadData} />
      </PageContainer>
    );
  }

  if (records.length === 0 && permissions.length === 0) {
    return (
      <PageContainer>
        {header}
        <EmptyState
          icon={<AccessTimeIcon />}
          title={t('attendanceEmpty')}
          description={t('attendanceEmptyDesc')}
          actionLabel={t('actionAddAttendanceRecord')}
          onAction={openCreateRecord}
        />
        {renderDialogs()}
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {header}

      <Stack spacing={2}>
        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{t('attendanceRecordsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateRecord}>
              {t('actionAddAttendanceRecord')}
            </Button>
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colDate')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colHoursWorked')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colOvertimeHours')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {records.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ color: 'text.secondary' }}>{t('attendanceEmpty')}</TableCell>
                  </TableRow>
                ) : (
                  records.map((record) => {
                    const statusKey = statusLabelKey(record.status);
                    return (
                      <TableRow key={record.id} hover>
                        <TableCell>{employeeName(record.employee)}</TableCell>
                        <TableCell>{formatDate(record.date)}</TableCell>
                        <TableCell>{record.hours_worked ?? '—'}</TableCell>
                        <TableCell>{record.overtime_hours ?? '—'}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant="outlined"
                            color={statusColor(record.status)}
                            label={statusKey ? t(statusKey) : record.status}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title={tCommon('edit')}>
                            <IconButton size="small" onClick={() => openEditRecord(record)} sx={{ color: 'primary.main' }}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={tCommon('delete')}>
                            <IconButton size="small" onClick={() => handleDeleteRecord(record)} sx={{ color: 'error.main' }}>
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
        </Box>

        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{t('attendancePermissionsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreatePermission}>
              {t('actionAddAttendancePermission')}
            </Button>
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colDate')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPermissionType')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colHours')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colApproved')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {permissions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ color: 'text.secondary' }}>{t('attendanceEmpty')}</TableCell>
                  </TableRow>
                ) : (
                  permissions.map((permission) => (
                    <TableRow key={permission.id} hover>
                      <TableCell>{employeeName(permission.employee)}</TableCell>
                      <TableCell>{formatDate(permission.date)}</TableCell>
                      <TableCell>{permission.permission_type ?? '—'}</TableCell>
                      <TableCell>{permission.hours ?? '—'}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={permission.approved ? 'success' : 'default'}
                          label={permission.approved ? t('yes') : t('no')}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title={tCommon('edit')}>
                          <IconButton size="small" onClick={() => openEditPermission(permission)} sx={{ color: 'primary.main' }}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={tCommon('delete')}>
                          <IconButton size="small" onClick={() => handleDeletePermission(permission)} sx={{ color: 'error.main' }}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Stack>

      {renderDialogs()}

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
