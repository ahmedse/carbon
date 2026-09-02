// src/apps/people/LeavePage.jsx
// People & Payroll — Leave (full CRUD): leave records + leave entitlements (accrual).
// Approval/rejection is a PATCH { status } on the leave record — no dedicated endpoint.
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
import CancelIcon from '@mui/icons-material/Cancel';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
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
  fetchLeaveRecords,
  fetchLeaveEntitlements,
  createLeaveRecord,
  updateLeaveRecord,
  deleteLeaveRecord,
  createLeaveEntitlement,
  updateLeaveEntitlement,
  deleteLeaveEntitlement,
} from '../../api/people';
import { buildEmployeeLabels, formatDate, statusColor, statusLabelKey } from './utils';

const EMPTY_RECORD = {
  employee: '',
  leave_type: '',
  start_date: '',
  end_date: '',
  days: '',
  status: 'draft',
};

const EMPTY_ENT = {
  employee: '',
  year: '',
  leave_type: '',
  entitled_days: '',
  used_days: '0',
  carried_forward: '0',
  notes: '',
};

const LEAVE_STATUSES = ['draft', 'submitted', 'approved', 'rejected', 'cancelled'];

export default function LeavePage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('leaveTitle'));
  const { token } = useAuth();

  const [records, setRecords] = useState([]);
  const [entitlements, setEntitlements] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [recordDialogOpen, setRecordDialogOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [recordForm, setRecordForm] = useState({ ...EMPTY_RECORD });

  const [entDialogOpen, setEntDialogOpen] = useState(false);
  const [editingEnt, setEditingEnt] = useState(null);
  const [entForm, setEntForm] = useState({ ...EMPTY_ENT });

  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [employeesData, recordsData, entitlementsData] = await Promise.all([
        fetchEmployees(token),
        fetchLeaveRecords(token),
        fetchLeaveEntitlements(token),
      ]);
      const employeeList = Array.isArray(employeesData) ? employeesData : employeesData?.results || [];
      setEmployees(employeeList);
      setEmployeeLabels(buildEmployeeLabels(employeeList));
      setRecords(Array.isArray(recordsData) ? recordsData : recordsData?.results || []);
      setEntitlements(Array.isArray(entitlementsData) ? entitlementsData : entitlementsData?.results || []);
    } catch (err) {
      setError(err?.message || t('leaveLoadError'));
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

  // ---- Leave Records ----

  const openCreateRecord = () => {
    setEditingRecord(null);
    setRecordForm({ ...EMPTY_RECORD });
    setRecordDialogOpen(true);
  };

  const openEditRecord = (record) => {
    setEditingRecord(record);
    setRecordForm({
      employee: record.employee ?? '',
      leave_type: record.leave_type ?? '',
      start_date: record.start_date ? String(record.start_date).slice(0, 10) : '',
      end_date: record.end_date ? String(record.end_date).slice(0, 10) : '',
      days: record.days != null ? String(record.days) : '',
      status: record.status ?? 'draft',
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
    if (
      !recordForm.employee ||
      !recordForm.leave_type.trim() ||
      !recordForm.start_date ||
      !recordForm.end_date ||
      !String(recordForm.days).trim()
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(recordForm.employee),
      leave_type: recordForm.leave_type.trim(),
      start_date: recordForm.start_date,
      end_date: recordForm.end_date,
      days: String(recordForm.days).trim(),
      status: recordForm.status,
    };

    setSaving(true);
    try {
      if (editingRecord) {
        await updateLeaveRecord(editingRecord.id, payload, token);
      } else {
        await createLeaveRecord(payload, token);
      }
      closeRecordDialog();
      setSnackbar({ open: true, message: t('leaveRecordSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async (record) => {
    try {
      await updateLeaveRecord(record.id, { status: 'approved' }, token);
      setSnackbar({ open: true, message: t('leaveApproved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  const handleReject = async (record) => {
    try {
      await updateLeaveRecord(record.id, { status: 'rejected' }, token);
      setSnackbar({ open: true, message: t('leaveRejected'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  const handleDeleteRecord = async (record) => {
    if (!window.confirm(t('leaveRecordDeleteConfirm'))) return;
    try {
      await deleteLeaveRecord(record.id, token);
      setSnackbar({ open: true, message: t('leaveRecordDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  // ---- Leave Entitlements ----

  const openCreateEnt = () => {
    setEditingEnt(null);
    setEntForm({ ...EMPTY_ENT });
    setEntDialogOpen(true);
  };

  const openEditEnt = (entitlement) => {
    setEditingEnt(entitlement);
    setEntForm({
      employee: entitlement.employee ?? '',
      year: entitlement.year ?? '',
      leave_type: entitlement.leave_type ?? '',
      entitled_days: entitlement.entitled_days != null ? String(entitlement.entitled_days) : '',
      used_days: entitlement.used_days != null ? String(entitlement.used_days) : '0',
      carried_forward: entitlement.carried_forward != null ? String(entitlement.carried_forward) : '0',
      notes: entitlement.notes ?? '',
    });
    setEntDialogOpen(true);
  };

  const closeEntDialog = () => {
    setEntDialogOpen(false);
    setEditingEnt(null);
  };

  const handleEntChange = (event) => {
    const { name, value } = event.target;
    setEntForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveEnt = async () => {
    if (
      !entForm.employee ||
      !entForm.year ||
      !entForm.leave_type.trim() ||
      !String(entForm.entitled_days).trim()
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(entForm.employee),
      year: Number(entForm.year),
      leave_type: entForm.leave_type.trim(),
      entitled_days: String(entForm.entitled_days).trim(),
      used_days: String(entForm.used_days).trim(),
      carried_forward: String(entForm.carried_forward).trim(),
    };
    if (entForm.notes && entForm.notes.trim()) {
      payload.notes = entForm.notes.trim();
    }

    setSaving(true);
    try {
      if (editingEnt) {
        await updateLeaveEntitlement(editingEnt.id, payload, token);
      } else {
        await createLeaveEntitlement(payload, token);
      }
      closeEntDialog();
      setSnackbar({ open: true, message: t('leaveEntitlementSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEnt = async (entitlement) => {
    if (!window.confirm(t('leaveEntitlementDeleteConfirm'))) return;
    try {
      await deleteLeaveEntitlement(entitlement.id, token);
      setSnackbar({ open: true, message: t('leaveEntitlementDeleted'), severity: 'success' });
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
        title={editingRecord ? t('leaveRecordEditTitle') : t('leaveRecordCreateTitle')}
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
            label={t('colLeaveType')}
            name="leave_type"
            value={recordForm.leave_type}
            onChange={handleRecordChange}
            fullWidth
            required
          />
          <TextField
            label={t('colStartDate')}
            name="start_date"
            value={recordForm.start_date}
            onChange={handleRecordChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('colEndDate')}
            name="end_date"
            value={recordForm.end_date}
            onChange={handleRecordChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('colDays')}
            name="days"
            value={recordForm.days}
            onChange={handleRecordChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
            required
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
            {LEAVE_STATUSES.map((status) => (
              <MenuItem key={status} value={status}>{t(statusLabelKey(status))}</MenuItem>
            ))}
          </TextField>
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={entDialogOpen}
        title={editingEnt ? t('leaveEntitlementEditTitle') : t('leaveEntitlementCreateTitle')}
        onClose={closeEntDialog}
        onCancel={closeEntDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSaveEnt} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            select
            label={t('colEmployee')}
            name="employee"
            value={entForm.employee}
            onChange={handleEntChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colEmployee')}</MenuItem>
            {employees.map((emp) => (
              <MenuItem key={emp.id} value={emp.id}>{employeeName(emp.id)}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colYear')}
            name="year"
            value={entForm.year}
            onChange={handleEntChange}
            type="number"
            slotProps={{ htmlInput: { step: '1', min: '2000' } }}
            fullWidth
            required
          />
          <TextField
            label={t('colLeaveType')}
            name="leave_type"
            value={entForm.leave_type}
            onChange={handleEntChange}
            fullWidth
            required
          />
          <TextField
            label={t('colEntitledDays')}
            name="entitled_days"
            value={entForm.entitled_days}
            onChange={handleEntChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
            required
          />
          <TextField
            label={t('colUsedDays')}
            name="used_days"
            value={entForm.used_days}
            onChange={handleEntChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
          />
          <TextField
            label={t('formCarriedForward')}
            name="carried_forward"
            value={entForm.carried_forward}
            onChange={handleEntChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.01' } }}
            fullWidth
          />
          <TextField
            label={t('formNotes')}
            name="notes"
            value={entForm.notes}
            onChange={handleEntChange}
            multiline
            minRows={2}
            fullWidth
          />
        </Stack>
      </SystemDialog>
    </>
  );

  const header = <PageHeader icon={EventAvailableIcon} title={t('leaveTitle')} subtitle={t('leaveSubtitle')} />;

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

  if (records.length === 0 && entitlements.length === 0) {
    return (
      <PageContainer>
        {header}
        <EmptyState
          icon={<EventAvailableIcon />}
          title={t('leaveEmpty')}
          description={t('leaveEmptyDesc')}
          actionLabel={t('actionAddLeaveRecord')}
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
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{t('leaveRecordsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateRecord}>
              {t('actionAddLeaveRecord')}
            </Button>
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colLeaveType')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStartDate')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEndDate')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colDays')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {records.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ color: 'text.secondary' }}>{t('leaveEmpty')}</TableCell>
                  </TableRow>
                ) : (
                  records.map((record) => {
                    const statusKey = statusLabelKey(record.status);
                    const actionable = record.status === 'draft' || record.status === 'submitted';
                    return (
                      <TableRow key={record.id} hover>
                        <TableCell>{employeeName(record.employee)}</TableCell>
                        <TableCell>{record.leave_type ?? '—'}</TableCell>
                        <TableCell>{formatDate(record.start_date)}</TableCell>
                        <TableCell>{formatDate(record.end_date)}</TableCell>
                        <TableCell>{record.days ?? '—'}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant="outlined"
                            color={statusColor(record.status)}
                            label={statusKey ? t(statusKey) : record.status}
                          />
                        </TableCell>
                        <TableCell align="right">
                          {actionable && (
                            <>
                              <Tooltip title={t('actionApprove')}>
                                <IconButton size="small" onClick={() => handleApprove(record)} sx={{ color: 'success.main' }}>
                                  <CheckCircleIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title={t('actionReject')}>
                                <IconButton size="small" onClick={() => handleReject(record)} sx={{ color: 'warning.main' }}>
                                  <CancelIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </>
                          )}
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
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{t('leaveEntitlementsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateEnt}>
              {t('actionAddLeaveEntitlement')}
            </Button>
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colYear')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colLeaveType')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEntitledDays')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colUsedDays')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCarriedForward')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {entitlements.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ color: 'text.secondary' }}>{t('leaveEmpty')}</TableCell>
                  </TableRow>
                ) : (
                  entitlements.map((entitlement) => (
                    <TableRow key={entitlement.id} hover>
                      <TableCell>{employeeName(entitlement.employee)}</TableCell>
                      <TableCell>{entitlement.year ?? '—'}</TableCell>
                      <TableCell>{entitlement.leave_type ?? '—'}</TableCell>
                      <TableCell>{entitlement.entitled_days ?? '—'}</TableCell>
                      <TableCell>{entitlement.used_days ?? '—'}</TableCell>
                      <TableCell>{entitlement.carried_forward ?? '—'}</TableCell>
                      <TableCell align="right">
                        <Tooltip title={tCommon('edit')}>
                          <IconButton size="small" onClick={() => openEditEnt(entitlement)} sx={{ color: 'primary.main' }}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={tCommon('delete')}>
                          <IconButton size="small" onClick={() => handleDeleteEnt(entitlement)} sx={{ color: 'error.main' }}>
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
