// src/apps/people/CertificationsPage.jsx
// People & Payroll — Certifications (full CRUD) with expiry urgency (NSR-6A).
// Sorted expired → soonest; Status chip; SearchSelect pickers; ConfirmDialog delete.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  IconButton,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
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
import SystemDialog from '../../components/SystemDialog';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import { SearchSelect } from '../../components/Form';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchCertifications,
  createCertification,
  updateCertification,
  deleteCertification,
} from '../../api/people';
import CertExpiryChip, { CertExpiryLegend } from './components/CertExpiryChip';
import EmployeePicker from './EmployeePicker';
import {
  labelsFromRows,
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
  const [searchValue, setSearchValue] = useState('');
  const [gridFilters, setGridFilters] = useState({ urgency: '' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const certificationsData = await fetchCertifications(token);
      const certificationList = Array.isArray(certificationsData)
        ? certificationsData
        : certificationsData?.results || [];
      setCertifications(certificationList);
      setEmployeeLabels(labelsFromRows(certificationList));
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

  const urgencyOf = (certification) => expiryUrgency(certification.expiry_date) || 'valid';

  const filteredCertifications = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return sortedCertifications.filter((certification) => {
      if (gridFilters.urgency && urgencyOf(certification) !== gridFilters.urgency) return false;
      if (!q) return true;
      const hay = [
        employeeName(certification.employee),
        refLabel(certification.cert_type),
        refCode(certification.cert_type),
        certification.number,
        formatDate(certification.issued_date),
        formatDate(certification.expiry_date),
        certification.notes,
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [sortedCertifications, searchValue, gridFilters, employeeLabels, t]);

  const filterDefs = useMemo(() => [
    {
      key: 'urgency',
      label: t('colStatus'),
      emptyLabel: t('filterAll'),
      options: [
        { value: 'expired', label: t('certsTabExpired') },
        { value: 'critical', label: t('certsLegendCritical') },
        { value: 'warning', label: t('certsLegendWarning') },
        { value: 'notice', label: t('certsLegendNotice') },
        { value: 'valid', label: t('certsTabValid') },
      ],
    },
  ], [t]);

  const columns = useMemo(() => [
    {
      field: 'employee',
      headerName: t('colEmployee'),
      flex: 1,
      minWidth: 160,
      valueGetter: (value) => employeeName(value),
    },
    {
      field: 'cert_type',
      headerName: t('colCertType'),
      width: 160,
      valueGetter: (value) => refLabel(value) || refCode(value) || '—',
    },
    { field: 'number', headerName: t('colCertNumber'), width: 140, valueGetter: (value) => value || '—' },
    { field: 'issued_date', headerName: t('colIssuedDate'), width: 130, valueGetter: (value) => formatDate(value) },
    {
      field: 'expiry_date',
      headerName: t('colExpiryDate'),
      width: 140,
      valueGetter: (value) => (value ? formatDate(value) : t('certsTabNoExpiry')),
    },
    {
      field: 'status',
      headerName: t('colStatus'),
      width: 150,
      sortable: false,
      valueGetter: (_value, row) => urgencyOf(row),
      renderCell: (params) => <CertExpiryChip expiryDate={params.row.expiry_date} />,
    },
    { field: 'notes', headerName: t('colNotes'), flex: 1, minWidth: 140, valueGetter: (value) => value || '—' },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 110,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <>
          <Tooltip title={t('actionEditCertification')}>
            <IconButton size="small" onClick={() => openEdit(params.row)} sx={{ color: 'primary.main' }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('actionDeleteCertification')}>
            <IconButton size="small" onClick={() => setDeleteTarget(params.row)} sx={{ color: 'error.main' }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      ),
    },
  ], [t, employeeLabels]);

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
      ) : (
        <Box>
          <FilteredDataGrid
            embedded
            rows={filteredCertifications}
            columns={columns}
            searchValue={searchValue}
            onSearchChange={setSearchValue}
            filterDefs={filterDefs}
            filterValues={gridFilters}
            onFilterChange={(key, value) => setGridFilters((prev) => ({ ...prev, [key]: value }))}
            onClearFilters={() => {
              setSearchValue('');
              setGridFilters({ urgency: '' });
            }}
            emptyMessage={t('certificationsEmpty')}
            emptySubtext={t('certificationsEmptyDesc')}
            pageSize={25}
            height={560}
            dataGridProps={{
              getRowClassName: (params) => {
                const urg = expiryUrgency(params.row.expiry_date);
                return urg === 'expired' || urg === 'critical' ? 'cert-urgent-row' : '';
              },
              sx: {
                '& .cert-urgent-row': { bgcolor: 'error.50' },
              },
            }}
          />
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
          <EmployeePicker
            token={token}
            label={t('colEmployee')}
            value={form.employee}
            initialLabel={employeeLabels[form.employee]}
            required
            onChange={(id) => setForm((prev) => ({ ...prev, employee: id || '' }))}
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
