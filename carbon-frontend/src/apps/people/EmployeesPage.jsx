// src/apps/people/EmployeesPage.jsx
// People & Payroll — Employees (full CRUD): create, read, update, deactivate.
// Deactivate is a soft delete on the backend (sets is_active=false + governance event).
// All colours via theme tokens; apiFetch only; SystemDialog for form + read-only details.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
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
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import BlockIcon from '@mui/icons-material/Block';
import EditIcon from '@mui/icons-material/Edit';
import PeopleIcon from '@mui/icons-material/People';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
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
  createEmployee,
  updateEmployee,
  deleteEmployee,
} from '../../api/people';
import { fetchOrgUnits } from '../../api/orgUnits';
import { formatAmount, formatDate } from './utils';

const EMPTY_FORM = {
  org_unit: '',
  employee_no: '',
  full_name: '',
  nationality: '',
  basic_salary: '',
  join_date: '',
  rotation: '',
  is_active: true,
};

export default function EmployeesPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('employeesTitle'));
  const { token } = useAuth();
  const navigate = useNavigate();

  const [employees, setEmployees] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [employeesData, orgUnitsData] = await Promise.all([
        fetchEmployees(token),
        fetchOrgUnits(token),
      ]);
      setEmployees(Array.isArray(employeesData) ? employeesData : employeesData?.results || []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : []);
    } catch (err) {
      setError(err?.message || t('employeesLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openCreate = () => {
    setEditingEmployee(null);
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  };

  const openEdit = (employee) => {
    setEditingEmployee(employee);
    setForm({
      org_unit: employee.org_unit ?? '',
      employee_no: employee.employee_no ?? '',
      full_name: employee.full_name ?? '',
      nationality: employee.nationality ?? '',
      basic_salary: employee.basic_salary != null ? String(employee.basic_salary) : '',
      join_date: employee.join_date ? String(employee.join_date).slice(0, 10) : '',
      rotation: employee.rotation ?? '',
      is_active: Boolean(employee.is_active),
    });
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingEmployee(null);
  };

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (
      !form.org_unit ||
      !form.employee_no.trim() ||
      !form.full_name.trim() ||
      !String(form.basic_salary).trim() ||
      !form.join_date
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      org_unit: Number(form.org_unit),
      employee_no: form.employee_no.trim(),
      full_name: form.full_name.trim(),
      basic_salary: String(form.basic_salary).trim(),
      join_date: form.join_date,
      is_active: Boolean(form.is_active),
    };
    if (form.nationality && form.nationality.trim()) {
      payload.nationality = form.nationality.trim();
    }
    if (form.rotation && form.rotation.trim()) {
      payload.rotation = form.rotation.trim();
    }

    setSaving(true);
    try {
      if (editingEmployee) {
        await updateEmployee(editingEmployee.id, payload, token);
      } else {
        await createEmployee(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('employeeSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (employee) => {
    if (!window.confirm(t('employeeDeactivateConfirm'))) return;
    try {
      await deleteEmployee(employee.id, token);
      setSnackbar({ open: true, message: t('employeeDeactivated'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  return (
    <PageContainer>
      <PageHeader
        icon={PeopleIcon}
        title={t('employeesTitle')}
        subtitle={t('employeesSubtitle')}
        description={t('employeesDescription')}
        actions={
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddEmployee')}
          </Button>
        }
      />

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : employees.length === 0 ? (
        <EmptyState
          icon={<PeopleIcon />}
          title={t('employeesEmpty')}
          description={t('employeesEmptyDesc')}
          actionLabel={t('actionAddEmployee')}
          onAction={openCreate}
        />
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployeeNo')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colFullName')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colNationality')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colBasicSalary')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colJoinDate')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {employees.map((employee) => (
                <TableRow key={employee.id} hover>
                  <TableCell>{employee.employee_no ?? '—'}</TableCell>
                  <TableCell>{employee.full_name ?? '—'}</TableCell>
                  <TableCell>{employee.nationality ?? '—'}</TableCell>
                  <TableCell>{formatAmount(employee.basic_salary)}</TableCell>
                  <TableCell>{formatDate(employee.join_date)}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      color={employee.is_active ? 'success' : 'default'}
                      label={employee.is_active ? t('statusActive') : t('statusInactive')}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t('actionViewEmployee')}>
                      <IconButton size="small" onClick={() => navigate(`/people/employees/${employee.id}`)} sx={{ color: 'primary.main' }}>
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('actionEditEmployee')}>
                      <IconButton size="small" onClick={() => openEdit(employee)} sx={{ color: 'primary.main' }}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('actionDeactivateEmployee')}>
                      <IconButton size="small" onClick={() => handleDeactivate(employee)} sx={{ color: 'error.main' }}>
                        <BlockIcon fontSize="small" />
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
        title={editingEmployee ? t('employeeEditTitle') : t('employeeCreateTitle')}
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
            label={t('formOrgUnit')}
            name="org_unit"
            value={form.org_unit}
            onChange={handleChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('formOrgUnit')}</MenuItem>
            {orgUnits.map((unit) => (
              <MenuItem key={unit.id} value={unit.id}>{unit.name || unit.code || unit.id}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('formEmployeeNo')}
            name="employee_no"
            value={form.employee_no}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('colFullName')}
            name="full_name"
            value={form.full_name}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('formNationality')}
            name="nationality"
            value={form.nationality}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label={t('formBasicSalary')}
            name="basic_salary"
            value={form.basic_salary}
            onChange={handleChange}
            type="number"
            inputProps={{ step: '0.001', min: '0' }}
            fullWidth
            required
          />
          <TextField
            label={t('formJoinDate')}
            name="join_date"
            value={form.join_date}
            onChange={handleChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('formRotation')}
            name="rotation"
            value={form.rotation}
            onChange={handleChange}
            fullWidth
          />
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
