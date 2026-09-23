// src/apps/people/AttendancePage.jsx
// People & Payroll — attendance records & permissions (full CRUD).
// All colours via theme tokens; apiFetch only; SystemDialog for the forms.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Snackbar,
  Stack,
  Switch,
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
import SystemDialog from '../../components/SystemDialog';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchAttendanceRecords,
  fetchAttendancePermissions,
  createAttendanceRecord,
  updateAttendanceRecord,
  deleteAttendanceRecord,
  createAttendancePermission,
  updateAttendancePermission,
  deleteAttendancePermission,
} from '../../api/people';
import { labelsFromRows, formatDate, statusColor, statusLabelKey } from './utils';
import EmployeePicker from './EmployeePicker';

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
  const [recordSearch, setRecordSearch] = useState('');
  const [recordFilters, setRecordFilters] = useState({ status: '' });
  const [permissionSearch, setPermissionSearch] = useState('');
  const [permissionFilters, setPermissionFilters] = useState({ approved: '' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [recordsData, permissionsData] = await Promise.all([
        fetchAttendanceRecords(token),
        fetchAttendancePermissions(token),
      ]);
      const recordList = Array.isArray(recordsData) ? recordsData : recordsData?.results || [];
      const permissionList = Array.isArray(permissionsData) ? permissionsData : permissionsData?.results || [];
      setRecords(recordList);
      setPermissions(permissionList);
      setEmployeeLabels(labelsFromRows([...recordList, ...permissionList]));
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
          <EmployeePicker
            token={token}
            label={t('colEmployee')}
            value={recordForm.employee}
            initialLabel={employeeLabels[recordForm.employee]}
            required
            onChange={(id) => setRecordForm((prev) => ({ ...prev, employee: id || '' }))}
          />
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
          <EmployeePicker
            token={token}
            label={t('colEmployee')}
            value={permissionForm.employee}
            initialLabel={employeeLabels[permissionForm.employee]}
            required
            onChange={(id) => setPermissionForm((prev) => ({ ...prev, employee: id || '' }))}
          />
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

  const filteredRecords = useMemo(() => {
    const q = recordSearch.trim().toLowerCase();
    return records.filter((record) => {
      if (recordFilters.status && record.status !== recordFilters.status) return false;
      if (!q) return true;
      const statusKey = statusLabelKey(record.status);
      const hay = [
        employeeName(record.employee),
        formatDate(record.date),
        record.hours_worked,
        record.overtime_hours,
        record.status,
        statusKey ? t(statusKey) : '',
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [records, recordSearch, recordFilters, employeeLabels, t]);

  const filteredPermissions = useMemo(() => {
    const q = permissionSearch.trim().toLowerCase();
    return permissions.filter((permission) => {
      if (permissionFilters.approved === 'yes' && !permission.approved) return false;
      if (permissionFilters.approved === 'no' && permission.approved) return false;
      if (!q) return true;
      const hay = [
        employeeName(permission.employee),
        formatDate(permission.date),
        permission.permission_type,
        permission.hours,
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [permissions, permissionSearch, permissionFilters, employeeLabels]);

  const recordFilterDefs = useMemo(() => [
    {
      key: 'status',
      label: t('filterStatus'),
      emptyLabel: t('filterAll'),
      options: ['present', 'absent', 'leave', 'permission'].map((value) => ({
        value,
        label: t(statusLabelKey(value)),
      })),
    },
  ], [t]);

  const permissionFilterDefs = useMemo(() => [
    {
      key: 'approved',
      label: t('colApproved'),
      emptyLabel: t('filterAll'),
      options: [
        { value: 'yes', label: t('yes') },
        { value: 'no', label: t('no') },
      ],
    },
  ], [t]);

  const recordColumns = useMemo(() => [
    {
      field: 'employee',
      headerName: t('colEmployee'),
      flex: 1,
      minWidth: 160,
      valueGetter: (value) => employeeName(value),
    },
    { field: 'date', headerName: t('colDate'), width: 130, valueGetter: (value) => formatDate(value) },
    { field: 'hours_worked', headerName: t('colHoursWorked'), width: 130, valueGetter: (value) => value ?? '—' },
    { field: 'overtime_hours', headerName: t('colOvertimeHours'), width: 140, valueGetter: (value) => value ?? '—' },
    {
      field: 'status',
      headerName: t('colStatus'),
      width: 140,
      valueGetter: (value) => {
        const key = statusLabelKey(value);
        return key ? t(key) : (value || '—');
      },
      renderCell: (params) => (
        <Chip size="small" variant="outlined" color={statusColor(params.row.status)} label={params.value} />
      ),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 110,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <>
          <Tooltip title={tCommon('edit')}>
            <IconButton size="small" onClick={() => openEditRecord(params.row)} sx={{ color: 'primary.main' }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={tCommon('delete')}>
            <IconButton size="small" onClick={() => handleDeleteRecord(params.row)} sx={{ color: 'error.main' }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      ),
    },
  ], [t, tCommon, employeeLabels]);

  const permissionColumns = useMemo(() => [
    {
      field: 'employee',
      headerName: t('colEmployee'),
      flex: 1,
      minWidth: 160,
      valueGetter: (value) => employeeName(value),
    },
    { field: 'date', headerName: t('colDate'), width: 130, valueGetter: (value) => formatDate(value) },
    { field: 'permission_type', headerName: t('colPermissionType'), width: 160, valueGetter: (value) => value || '—' },
    { field: 'hours', headerName: t('colHours'), width: 100, valueGetter: (value) => value ?? '—' },
    {
      field: 'approved',
      headerName: t('colApproved'),
      width: 120,
      valueGetter: (value) => (value ? t('yes') : t('no')),
      renderCell: (params) => (
        <Chip
          size="small"
          variant="outlined"
          color={params.row.approved ? 'success' : 'default'}
          label={params.value}
        />
      ),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 110,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <>
          <Tooltip title={tCommon('edit')}>
            <IconButton size="small" onClick={() => openEditPermission(params.row)} sx={{ color: 'primary.main' }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={tCommon('delete')}>
            <IconButton size="small" onClick={() => handleDeletePermission(params.row)} sx={{ color: 'error.main' }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      ),
    },
  ], [t, tCommon, employeeLabels]);

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

  return (
    <PageContainer>
      {header}

      <Stack spacing={3}>
        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle2">{t('attendanceRecordsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateRecord}>
              {t('actionAddAttendanceRecord')}
            </Button>
          </Stack>
          <FilteredDataGrid
            embedded
            rows={filteredRecords}
            columns={recordColumns}
            searchValue={recordSearch}
            onSearchChange={setRecordSearch}
            filterDefs={recordFilterDefs}
            filterValues={recordFilters}
            onFilterChange={(key, value) => setRecordFilters((prev) => ({ ...prev, [key]: value }))}
            onClearFilters={() => {
              setRecordSearch('');
              setRecordFilters({ status: '' });
            }}
            emptyMessage={t('attendanceEmpty')}
            emptySubtext={t('attendanceEmptyDesc')}
            pageSize={25}
            height={420}
          />
        </Box>

        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle2">{t('attendancePermissionsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreatePermission}>
              {t('actionAddAttendancePermission')}
            </Button>
          </Stack>
          <FilteredDataGrid
            embedded
            rows={filteredPermissions}
            columns={permissionColumns}
            searchValue={permissionSearch}
            onSearchChange={setPermissionSearch}
            filterDefs={permissionFilterDefs}
            filterValues={permissionFilters}
            onFilterChange={(key, value) => setPermissionFilters((prev) => ({ ...prev, [key]: value }))}
            onClearFilters={() => {
              setPermissionSearch('');
              setPermissionFilters({ approved: '' });
            }}
            emptyMessage={t('attendanceEmpty')}
            emptySubtext={t('attendanceEmptyDesc')}
            pageSize={25}
            height={420}
          />
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
