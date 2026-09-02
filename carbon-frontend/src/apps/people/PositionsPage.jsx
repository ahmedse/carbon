// src/apps/people/PositionsPage.jsx
// People & Payroll — Positions (full CRUD): create, read, update, delete.
// All colours via theme tokens; apiFetch only; SystemDialog for the form.

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
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
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
  fetchPositions,
  fetchEmployees,
  createPosition,
  updatePosition,
  deletePosition,
} from '../../api/people';
import { fetchOrgUnits } from '../../api/orgUnits';

const EMPTY_FORM = {
  org_unit: '',
  code: '',
  title: '',
  grade: '',
  reports_to: '',
  is_management: false,
  status: 'filled',
  fte: '1',
  job_family_code: '',
};

export default function PositionsPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('positionsTitle'));
  const { token } = useAuth();

  const [positions, setPositions] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingPosition, setEditingPosition] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [positionsData, orgUnitsData, employeesData] = await Promise.all([
        fetchPositions(token),
        fetchOrgUnits(token),
        fetchEmployees(token),
      ]);
      setPositions(Array.isArray(positionsData) ? positionsData : positionsData?.results || []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : []);
      setEmployees(Array.isArray(employeesData) ? employeesData : employeesData?.results || []);
    } catch (err) {
      setError(err?.message || t('positionsLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const orgUnitName = (id) => {
    const unit = orgUnits.find((u) => u.id === id);
    return unit?.name || unit?.code || '—';
  };

  const positionLabel = (id) => {
    const position = positions.find((p) => p.id === id);
    return position ? `${position.code} — ${position.title}` : '—';
  };

  const incumbentLabel = (positionId) => {
    const employee = employees.find((e) => e.position === positionId);
    return employee ? `${employee.employee_no} — ${employee.full_name}` : t('incumbentUnassigned');
  };

  const openCreate = () => {
    setEditingPosition(null);
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  };

  const openEdit = (position) => {
    setEditingPosition(position);
    setForm({
      org_unit: position.org_unit ?? '',
      code: position.code ?? '',
      title: position.title ?? '',
      grade: position.grade ?? '',
      reports_to: position.reports_to ?? '',
      is_management: Boolean(position.is_management),
      status: position.status ?? 'filled',
      fte: position.fte ?? '1',
      job_family_code: position.job_family_code ?? '',
    });
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingPosition(null);
  };

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (!form.org_unit || !form.code.trim() || !form.title.trim()) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      org_unit: Number(form.org_unit),
      code: form.code.trim(),
      title: form.title.trim(),
      is_management: Boolean(form.is_management),
      reports_to: form.reports_to ? Number(form.reports_to) : null,
      status: form.status || 'filled',
      fte: form.fte,
      job_family_code: (form.job_family_code || '').trim(),
    };
    if (form.grade && form.grade.trim()) {
      payload.grade = form.grade.trim();
    }

    setSaving(true);
    try {
      if (editingPosition) {
        await updatePosition(editingPosition.id, payload, token);
      } else {
        await createPosition(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('positionSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || t('actionError'),
        severity: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (position) => {
    if (!window.confirm(t('positionDeleteConfirm'))) return;
    try {
      await deletePosition(position.id, token);
      setSnackbar({ open: true, message: t('positionDeleted'), severity: 'success' });
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
        icon={AccountTreeIcon}
        title={t('positionsTitle')}
        subtitle={t('positionsSubtitle')}
        description={t('positionsDescription')}
        actions={
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddPosition')}
          </Button>
        }
      />

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : positions.length === 0 ? (
        <EmptyState
          icon={<AccountTreeIcon />}
          title={t('positionsEmpty')}
          description={t('positionsEmptyDesc')}
          actionLabel={t('actionAddPosition')}
          onAction={openCreate}
        />
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCode')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colTitle')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colOrgUnit')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colGrade')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colFte')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colJobFamilyCode')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colIncumbent')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colReportsTo')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colIsManagement')}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {positions.map((position) => (
                <TableRow key={position.id} hover>
                  <TableCell>{position.code ?? '—'}</TableCell>
                  <TableCell>{position.title ?? '—'}</TableCell>
                  <TableCell>{orgUnitName(position.org_unit)}</TableCell>
                  <TableCell>{position.grade ?? '—'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      color={
                        position.status === 'filled'
                          ? 'success'
                          : position.status === 'open'
                            ? 'info'
                            : position.status === 'frozen'
                              ? 'warning'
                              : 'default'
                      }
                      label={
                        position.status === 'proposed'
                          ? t('statusProposed')
                          : position.status === 'open'
                            ? t('statusOpen')
                            : position.status === 'filled'
                              ? t('statusFilled')
                              : position.status === 'frozen'
                                ? t('statusFrozen')
                                : position.status === 'closed'
                                  ? t('statusClosed')
                                  : position.status ?? '—'
                      }
                    />
                  </TableCell>
                  <TableCell>{position.fte ?? '—'}</TableCell>
                  <TableCell>{position.job_family_code || '—'}</TableCell>
                  <TableCell>{incumbentLabel(position.id)}</TableCell>
                  <TableCell>{position.reports_to ? positionLabel(position.reports_to) : '—'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      color={position.is_management ? 'info' : 'default'}
                      label={position.is_management ? t('yes') : t('no')}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t('actionEditPosition')}>
                      <IconButton size="small" onClick={() => openEdit(position)} sx={{ color: 'primary.main' }}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('actionDeletePosition')}>
                      <IconButton size="small" onClick={() => handleDelete(position)} sx={{ color: 'error.main' }}>
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
        title={editingPosition ? t('positionEditTitle') : t('positionCreateTitle')}
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
            label={t('colCode')}
            name="code"
            value={form.code}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('colTitle')}
            name="title"
            value={form.title}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('formGrade')}
            name="grade"
            value={form.grade}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            select
            label={t('formStatus')}
            name="status"
            value={form.status}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="proposed">{t('statusProposed')}</MenuItem>
            <MenuItem value="open">{t('statusOpen')}</MenuItem>
            <MenuItem value="filled">{t('statusFilled')}</MenuItem>
            <MenuItem value="frozen">{t('statusFrozen')}</MenuItem>
            <MenuItem value="closed">{t('statusClosed')}</MenuItem>
          </TextField>
          <TextField
            label={t('formFte')}
            name="fte"
            value={form.fte}
            onChange={handleChange}
            fullWidth
            type="number"
            inputProps={{ step: '0.01', min: '0' }}
          />
          <TextField
            label={t('formJobFamilyCode')}
            name="job_family_code"
            value={form.job_family_code}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            select
            label={t('formReportsTo')}
            name="reports_to"
            value={form.reports_to}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="">—</MenuItem>
            {positions
              .filter((p) => !editingPosition || p.id !== editingPosition.id)
              .map((p) => (
                <MenuItem key={p.id} value={p.id}>{p.code} — {p.title}</MenuItem>
              ))}
          </TextField>
          <FormControlLabel
            control={
              <Switch
                checked={form.is_management}
                onChange={handleChange}
                name="is_management"
                color="primary"
              />
            }
            label={t('formIsManagement')}
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
