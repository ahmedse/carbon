// src/apps/people/CertificationsPage.jsx
// People & Payroll — Certifications (full CRUD) with expiry urgency (NSR-6A).
// Sorted expired → soonest; Status chip; SearchSelect pickers; ConfirmDialog delete.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  IconButton,
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
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import SchoolIcon from '@mui/icons-material/School';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import { SearchSelect } from '../../components/Form';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchCertifications,
  fetchEmployees,
  createCertification,
  updateCertification,
  deleteCertification,
} from '../../api/people';
import CertExpiryChip, { CertExpiryLegend } from './components/CertExpiryChip';
import {
  buildEmployeeLabels,
  daysUntilExpiry,
  expiryUrgency,
  formatDate,
  refCode,
  refLabel,
} from './utils';

const EMPTY_FORM = {
  employee: '',
  cert_type: '',
  number: '',
  issued_date: '',
  expiry_date: '',
  notes: '',
};

export default function CertificationsPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('certificationsTitle'));
  const { token } = useAuth();
  const certTypeRef = useReferenceOptions('cert_type');

  const [certifications, setCertifications] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingCertification, setEditingCertification] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [certificationsData, employeesData] = await Promise.all([
        fetchCertifications(token),
        fetchEmployees(token),
      ]);
      const certificationList = Array.isArray(certificationsData)
        ? certificationsData
        : certificationsData?.results || [];
      const employeeList = Array.isArray(employeesData)
        ? employeesData
        : employeesData?.results || [];
      setCertifications(certificationList);
      setEmployees(employeeList);
      setEmployeeLabels(buildEmployeeLabels(employeeList));
    } catch (err) {
      setError(err?.message || t('certificationsLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const sortedCertifications = useMemo(() => {
    return [...certifications].sort((a, b) => {
      const da = daysUntilExpiry(a.expiry_date) ?? Infinity;
      const db = daysUntilExpiry(b.expiry_date) ?? Infinity;
      return da - db;
    });
  }, [certifications]);

  const employeeOptions = useMemo(
    () =>
      employees.map((employee) => ({
        value: employee.id,
        label: `${employee.employee_no ?? '—'} — ${employee.full_name ?? ''}`,
      })),
    [employees],
  );

  const employeeName = (id) => employeeLabels[id] ?? id ?? '—';

  const showError = (err) => {
    setSnackbar({
      open: true,
      message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
      severity: 'error',
    });
  };

  const openCreate = () => {
    setEditingCertification(null);
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  };

  const openEdit = (certification) => {
    setEditingCertification(certification);
    setForm({
      employee: certification.employee ?? '',
      cert_type: refCode(certification.cert_type),
      number: certification.number ?? '',
      issued_date: certification.issued_date
        ? String(certification.issued_date).slice(0, 10)
        : '',
      expiry_date: certification.expiry_date
        ? String(certification.expiry_date).slice(0, 10)
        : '',
      notes: certification.notes ?? '',
    });
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingCertification(null);
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (!form.employee || !form.cert_type.trim() || !form.number.trim()) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(form.employee),
      cert_type: form.cert_type.trim(),
      number: form.number.trim(),
      issued_date: form.issued_date || null,
      expiry_date: form.expiry_date || null,
    };
    if (form.notes && form.notes.trim()) {
      payload.notes = form.notes.trim();
    }

    setSaving(true);
    try {
      if (editingCertification) {
        await updateCertification(editingCertification.id, payload, token);
      } else {
        await createCertification(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('certificationSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await deleteCertification(deleteTarget.id, token);
      setDeleteTarget(null);
      setSnackbar({ open: true, message: t('certificationDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setDeleting(false);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  return (
    <PageContainer>
      <PageHeader
        icon={SchoolIcon}
        title={t('certificationsTitle')}
        subtitle={t('certificationsSubtitle')}
        description={t('certificationsDescription')}
        actions={
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddCertification')}
          </Button>
        }
      />

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : certifications.length === 0 ? (
        <EmptyState
          icon={<SchoolIcon />}
          title={t('certificationsEmpty')}
          description={t('certificationsEmptyDesc')}
          actionLabel={t('actionAddCertification')}
          onAction={openCreate}
        />
      ) : (
        <Box>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCertType')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCertNumber')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colIssuedDate')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colExpiryDate')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colNotes')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedCertifications.map((certification) => {
                  const urg = expiryUrgency(certification.expiry_date);
                  const isUrgent = urg === 'expired' || urg === 'critical';
                  return (
                    <TableRow
                      key={certification.id}
                      hover
                      sx={{ bgcolor: isUrgent ? 'error.50' : undefined }}
                    >
                      <TableCell>{employeeName(certification.employee)}</TableCell>
                      <TableCell>
                        {refLabel(certification.cert_type) || refCode(certification.cert_type) || '—'}
                      </TableCell>
                      <TableCell>{certification.number ?? '—'}</TableCell>
                      <TableCell>{formatDate(certification.issued_date)}</TableCell>
                      <TableCell>
                        {certification.expiry_date ? (
                          formatDate(certification.expiry_date)
                        ) : (
                          <Typography component="span" variant="body2" color="text.disabled">
                            {t('certsTabNoExpiry')}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <CertExpiryChip expiryDate={certification.expiry_date} />
                      </TableCell>
                      <TableCell>{certification.notes || '—'}</TableCell>
                      <TableCell align="right">
                        <Tooltip title={t('actionEditCertification')}>
                          <IconButton
                            size="small"
                            onClick={() => openEdit(certification)}
                            sx={{ color: 'primary.main' }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t('actionDeleteCertification')}>
                          <IconButton
                            size="small"
                            onClick={() => setDeleteTarget(certification)}
                            sx={{ color: 'error.main' }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
          <CertExpiryLegend />
        </Box>
      )}

      <SystemDialog
        open={openDialog}
        title={editingCertification ? t('certificationEditTitle') : t('certificationCreateTitle')}
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
          <SearchSelect
            label={t('colEmployee')}
            options={employeeOptions}
            value={form.employee}
            onChange={(v) => setForm((prev) => ({ ...prev, employee: v?.value ?? '' }))}
            required
            clearable={false}
          />
          <SearchSelect
            label={t('colCertType')}
            options={certTypeRef.options}
            value={form.cert_type}
            onChange={(v) => setForm((prev) => ({ ...prev, cert_type: v?.value ?? '' }))}
            loading={certTypeRef.loading}
            error={certTypeRef.error}
            onRetry={certTypeRef.refetch}
            required
            clearable={false}
          />
          <TextField
            label={t('colCertNumber')}
            name="number"
            value={form.number}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('colIssuedDate')}
            name="issued_date"
            value={form.issued_date}
            onChange={handleChange}
            fullWidth
            type="date"
            InputLabelProps={{ shrink: true }}
            helperText={t('fieldOptional')}
          />
          <TextField
            label={t('colExpiryDate')}
            name="expiry_date"
            value={form.expiry_date}
            onChange={handleChange}
            fullWidth
            type="date"
            InputLabelProps={{ shrink: true }}
            helperText={t('fieldOptional')}
          />
          <TextField
            label={t('colNotes')}
            name="notes"
            value={form.notes}
            onChange={handleChange}
            fullWidth
            multiline
            minRows={2}
          />
        </Stack>
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={t('certificationDeleteTitle')}
        message={t('certificationDeleteConfirm')}
        confirmLabel={tCommon('delete')}
        cancelLabel={tCommon('cancel')}
        destructive
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

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
