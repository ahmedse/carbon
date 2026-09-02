// src/apps/people/BenefitsPage.jsx
// People & Payroll — benefit types & employee benefits (full CRUD).
// All colours via theme tokens; apiFetch only; SystemDialog for the forms.

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
import CardGiftcardIcon from '@mui/icons-material/CardGiftcard';
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
  fetchBenefitTypes,
  fetchEmployeeBenefits,
  createBenefitType,
  updateBenefitType,
  deleteBenefitType,
  createEmployeeBenefit,
  updateEmployeeBenefit,
  deleteEmployeeBenefit,
} from '../../api/people';
import { buildBenefitTypeLabels, buildEmployeeLabels, formatAmount, formatDate } from './utils';

const BENEFIT_CATEGORIES = ['accommodation', 'vehicle', 'medical', 'school', 'tickets', 'other'];

const EMPTY_TYPE = {
  code: '',
  name: '',
  category: '',
  is_eosi_base: false,
  is_taxable: false,
};

const EMPTY_BEN = {
  employee: '',
  benefit_type: '',
  monthly_amount: '',
  effective_start: '',
  effective_end: '',
};

export default function BenefitsPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('benefitsTitle'));
  const { token } = useAuth();

  const [benefitTypes, setBenefitTypes] = useState([]);
  const [benefits, setBenefits] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [benefitTypeLabels, setBenefitTypeLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [typeDialogOpen, setTypeDialogOpen] = useState(false);
  const [editingType, setEditingType] = useState(null);
  const [typeForm, setTypeForm] = useState({ ...EMPTY_TYPE });

  const [benDialogOpen, setBenDialogOpen] = useState(false);
  const [editingBen, setEditingBen] = useState(null);
  const [benForm, setBenForm] = useState({ ...EMPTY_BEN });

  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [employeesData, typesData, benefitsData] = await Promise.all([
        fetchEmployees(token),
        fetchBenefitTypes(token),
        fetchEmployeeBenefits(token),
      ]);
      const employeeList = Array.isArray(employeesData) ? employeesData : employeesData?.results || [];
      const typeList = Array.isArray(typesData) ? typesData : typesData?.results || [];
      const benefitList = Array.isArray(benefitsData) ? benefitsData : benefitsData?.results || [];
      setEmployees(employeeList);
      setEmployeeLabels(buildEmployeeLabels(employeeList));
      setBenefitTypes(typeList);
      setBenefitTypeLabels(buildBenefitTypeLabels(typeList));
      setBenefits(benefitList);
    } catch (err) {
      setError(err?.message || t('benefitsLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const employeeName = (id) => employeeLabels[id] ?? id ?? '—';
  const benefitTypeName = (id) => benefitTypeLabels[id] ?? id ?? '—';

  const showError = (err) => {
    setSnackbar({
      open: true,
      message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
      severity: 'error',
    });
  };

  // ---- Benefit Types ----

  const openCreateType = () => {
    setEditingType(null);
    setTypeForm({ ...EMPTY_TYPE });
    setTypeDialogOpen(true);
  };

  const openEditType = (type) => {
    setEditingType(type);
    setTypeForm({
      code: type.code ?? '',
      name: type.name ?? '',
      category: type.category ?? '',
      is_eosi_base: Boolean(type.is_eosi_base),
      is_taxable: Boolean(type.is_taxable),
    });
    setTypeDialogOpen(true);
  };

  const closeTypeDialog = () => {
    setTypeDialogOpen(false);
    setEditingType(null);
  };

  const handleTypeChange = (event) => {
    const { name, value, checked, type } = event.target;
    setTypeForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSaveType = async () => {
    if (!typeForm.code.trim() || !typeForm.name.trim() || !typeForm.category) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      code: typeForm.code.trim(),
      name: typeForm.name.trim(),
      category: typeForm.category,
      is_eosi_base: Boolean(typeForm.is_eosi_base),
      is_taxable: Boolean(typeForm.is_taxable),
    };

    setSaving(true);
    try {
      if (editingType) {
        await updateBenefitType(editingType.id, payload, token);
      } else {
        await createBenefitType(payload, token);
      }
      closeTypeDialog();
      setSnackbar({ open: true, message: t('benefitTypeSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteType = async (type) => {
    if (!window.confirm(t('benefitTypeDeleteConfirm'))) return;
    try {
      await deleteBenefitType(type.id, token);
      setSnackbar({ open: true, message: t('benefitTypeDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  // ---- Employee Benefits ----

  const openCreateBen = () => {
    setEditingBen(null);
    setBenForm({ ...EMPTY_BEN });
    setBenDialogOpen(true);
  };

  const openEditBen = (benefit) => {
    setEditingBen(benefit);
    setBenForm({
      employee: benefit.employee ?? '',
      benefit_type: benefit.benefit_type ?? '',
      monthly_amount: benefit.monthly_amount != null ? String(benefit.monthly_amount) : '',
      effective_start: benefit.effective_start ? String(benefit.effective_start).slice(0, 10) : '',
      effective_end: benefit.effective_end ? String(benefit.effective_end).slice(0, 10) : '',
    });
    setBenDialogOpen(true);
  };

  const closeBenDialog = () => {
    setBenDialogOpen(false);
    setEditingBen(null);
  };

  const handleBenChange = (event) => {
    const { name, value } = event.target;
    setBenForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveBen = async () => {
    if (
      !benForm.employee ||
      !benForm.benefit_type ||
      !String(benForm.monthly_amount).trim() ||
      !benForm.effective_start
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(benForm.employee),
      benefit_type: Number(benForm.benefit_type),
      monthly_amount: String(benForm.monthly_amount).trim(),
      effective_start: benForm.effective_start,
      effective_end: benForm.effective_end ? benForm.effective_end : null,
    };

    setSaving(true);
    try {
      if (editingBen) {
        await updateEmployeeBenefit(editingBen.id, payload, token);
      } else {
        await createEmployeeBenefit(payload, token);
      }
      closeBenDialog();
      setSnackbar({ open: true, message: t('employeeBenefitSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBen = async (benefit) => {
    if (!window.confirm(t('employeeBenefitDeleteConfirm'))) return;
    try {
      await deleteEmployeeBenefit(benefit.id, token);
      setSnackbar({ open: true, message: t('employeeBenefitDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  const renderDialogs = () => (
    <>
      <SystemDialog
        open={typeDialogOpen}
        title={editingType ? t('benefitTypeEditTitle') : t('benefitTypeCreateTitle')}
        onClose={closeTypeDialog}
        onCancel={closeTypeDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSaveType} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            label={t('colCode')}
            name="code"
            value={typeForm.code}
            onChange={handleTypeChange}
            fullWidth
            required
          />
          <TextField
            label={t('colName')}
            name="name"
            value={typeForm.name}
            onChange={handleTypeChange}
            fullWidth
            required
          />
          <TextField
            select
            label={t('colCategory')}
            name="category"
            value={typeForm.category}
            onChange={handleTypeChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colCategory')}</MenuItem>
            {BENEFIT_CATEGORIES.map((category) => (
              <MenuItem key={category} value={category}>{category}</MenuItem>
            ))}
          </TextField>
          <FormControlLabel
            control={
              <Switch
                checked={typeForm.is_eosi_base}
                onChange={handleTypeChange}
                name="is_eosi_base"
                color="primary"
              />
            }
            label={t('colEosiBase')}
          />
          <FormControlLabel
            control={
              <Switch
                checked={typeForm.is_taxable}
                onChange={handleTypeChange}
                name="is_taxable"
                color="primary"
              />
            }
            label={t('colTaxable')}
          />
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={benDialogOpen}
        title={editingBen ? t('employeeBenefitEditTitle') : t('employeeBenefitCreateTitle')}
        onClose={closeBenDialog}
        onCancel={closeBenDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSaveBen} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            select
            label={t('colEmployee')}
            name="employee"
            value={benForm.employee}
            onChange={handleBenChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colEmployee')}</MenuItem>
            {employees.map((emp) => (
              <MenuItem key={emp.id} value={emp.id}>{employeeName(emp.id)}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label={t('colBenefitType')}
            name="benefit_type"
            value={benForm.benefit_type}
            onChange={handleBenChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colBenefitType')}</MenuItem>
            {benefitTypes.map((type) => (
              <MenuItem key={type.id} value={type.id}>{benefitTypeName(type.id)}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colMonthlyAmount')}
            name="monthly_amount"
            value={benForm.monthly_amount}
            onChange={handleBenChange}
            type="number"
            slotProps={{ htmlInput: { step: '0.001' } }}
            fullWidth
            required
          />
          <TextField
            label={t('colEffectiveStart')}
            name="effective_start"
            value={benForm.effective_start}
            onChange={handleBenChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('colEffectiveEnd')}
            name="effective_end"
            value={benForm.effective_end}
            onChange={handleBenChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
          />
        </Stack>
      </SystemDialog>
    </>
  );

  const header = <PageHeader icon={CardGiftcardIcon} title={t('benefitsTitle')} subtitle={t('benefitsSubtitle')} />;

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

  if (benefitTypes.length === 0 && benefits.length === 0) {
    return (
      <PageContainer>
        {header}
        <EmptyState
          icon={<CardGiftcardIcon />}
          title={t('benefitsEmpty')}
          description={t('benefitsEmptyDesc')}
          actionLabel={t('actionAddBenefitType')}
          onAction={openCreateType}
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
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{t('benefitTypesTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateType}>
              {t('actionAddBenefitType')}
            </Button>
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCode')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colName')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCategory')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEosiBase')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colTaxable')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {benefitTypes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ color: 'text.secondary' }}>{t('benefitsEmpty')}</TableCell>
                  </TableRow>
                ) : (
                  benefitTypes.map((type) => (
                    <TableRow key={type.id} hover>
                      <TableCell>{type.code ?? '—'}</TableCell>
                      <TableCell>{type.name ?? '—'}</TableCell>
                      <TableCell>{type.category ?? '—'}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={type.is_eosi_base ? 'success' : 'default'}
                          label={type.is_eosi_base ? t('yes') : t('no')}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={type.is_taxable ? 'success' : 'default'}
                          label={type.is_taxable ? t('yes') : t('no')}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title={tCommon('edit')}>
                          <IconButton size="small" onClick={() => openEditType(type)} sx={{ color: 'primary.main' }}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={tCommon('delete')}>
                          <IconButton size="small" onClick={() => handleDeleteType(type)} sx={{ color: 'error.main' }}>
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

        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{t('employeeBenefitsTitle')}</Typography>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateBen}>
              {t('actionAddEmployeeBenefit')}
            </Button>
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colBenefitType')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colMonthlyAmount')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEffectiveStart')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEffectiveEnd')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {benefits.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ color: 'text.secondary' }}>{t('benefitsEmpty')}</TableCell>
                  </TableRow>
                ) : (
                  benefits.map((benefit) => (
                    <TableRow key={benefit.id} hover>
                      <TableCell>{employeeLabels[benefit.employee] ?? benefit.employee ?? '—'}</TableCell>
                      <TableCell>{benefitTypeLabels[benefit.benefit_type] ?? benefit.benefit_type ?? '—'}</TableCell>
                      <TableCell>{formatAmount(benefit.monthly_amount)}</TableCell>
                      <TableCell>{formatDate(benefit.effective_start)}</TableCell>
                      <TableCell>{formatDate(benefit.effective_end)}</TableCell>
                      <TableCell align="right">
                        <Tooltip title={tCommon('edit')}>
                          <IconButton size="small" onClick={() => openEditBen(benefit)} sx={{ color: 'primary.main' }}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={tCommon('delete')}>
                          <IconButton size="small" onClick={() => handleDeleteBen(benefit)} sx={{ color: 'error.main' }}>
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
