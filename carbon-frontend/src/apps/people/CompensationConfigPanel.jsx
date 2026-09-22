// src/apps/people/CompensationConfigPanel.jsx
// Compensation components + plan matrix admin for People Config (NSR-5B).
// Full CRUD: create / PATCH / soft-DELETE (deactivate).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControlLabel,
  IconButton,
  MenuItem,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import { useTranslation } from 'react-i18next';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import StandardDataGrid from '../../components/StandardDataGrid';
import { SearchSelect } from '../../components/Form';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchCompensationComponents,
  createCompensationComponent,
  updateCompensationComponent,
  deleteCompensationComponent,
  fetchCompensationPlan,
  createCompensationPlan,
  updateCompensationPlan,
  deleteCompensationPlan,
} from '../../api/people';
import { formatDate } from './utils';

const DIRECTIONS = ['earning', 'deduction'];
const FREQUENCIES = ['monthly', 'annual'];

const EMPTY_COMPONENT = {
  code: '',
  name: '',
  name_ar: '',
  direction: 'earning',
  category: '',
  is_eosi_base: false,
  is_gosi_base: false,
  is_wps_relevant: true,
  is_taxable: false,
  is_variable: false,
  sort_order: '100',
  is_active: true,
};

const EMPTY_PLAN = {
  pay_grade_code: '',
  job_family_code: '',
  component: '',
  amount: '',
  currency: 'KWD',
  frequency: 'monthly',
  effective_start: '',
  effective_end: '',
  is_active: true,
};

export default function CompensationConfigPanel() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { token, isGlobalAdminFlag } = useAuth();
  const canMutate = isGlobalAdminFlag === true;

  const [components, setComponents] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [compDialog, setCompDialog] = useState(false);
  const [planDialog, setPlanDialog] = useState(false);
  const [editingComp, setEditingComp] = useState(null);
  const [editingPlan, setEditingPlan] = useState(null);
  const [compForm, setCompForm] = useState({ ...EMPTY_COMPONENT });
  const [planForm, setPlanForm] = useState({ ...EMPTY_PLAN });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null); // { kind: 'comp'|'plan', row }
  const [deleting, setDeleting] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [compData, planData] = await Promise.all([
        fetchCompensationComponents(token),
        fetchCompensationPlan(token),
      ]);
      setComponents(Array.isArray(compData) ? compData : (compData?.results || []));
      setPlans(Array.isArray(planData) ? planData : (planData?.results || []));
    } catch (err) {
      setError(err?.message || t('compensationConfigLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { loadData(); }, [loadData]);

  const showError = (err) => {
    const fb = err?.feedback;
    const message = fb?.detail || fb?.title || err?.message || err?.detail || t('actionError');
    setSnackbar({ open: true, message, severity: 'error' });
  };

  const handleCompChange = (event) => {
    const { name, value, checked, type } = event.target;
    setCompForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handlePlanChange = (event) => {
    const { name, value, checked, type } = event.target;
    setPlanForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const openCompCreate = () => {
    setEditingComp(null);
    setCompForm({ ...EMPTY_COMPONENT });
    setCompDialog(true);
  };

  const openCompEdit = (row) => {
    setEditingComp(row);
    setCompForm({
      code: row.code || '',
      name: row.name || '',
      name_ar: row.name_ar || '',
      direction: row.direction || 'earning',
      category: row.category || '',
      is_eosi_base: Boolean(row.is_eosi_base),
      is_gosi_base: Boolean(row.is_gosi_base),
      is_wps_relevant: row.is_wps_relevant !== false,
      is_taxable: Boolean(row.is_taxable),
      is_variable: Boolean(row.is_variable),
      sort_order: String(row.sort_order ?? 100),
      is_active: row.is_active !== false,
    });
    setCompDialog(true);
  };

  const openPlanCreate = () => {
    setEditingPlan(null);
    setPlanForm({ ...EMPTY_PLAN });
    setPlanDialog(true);
  };

  const openPlanEdit = (row) => {
    setEditingPlan(row);
    setPlanForm({
      pay_grade_code: row.pay_grade_code || '',
      job_family_code: row.job_family_code || '',
      component: String(row.component ?? ''),
      amount: row.amount != null ? String(row.amount) : '',
      currency: row.currency || 'KWD',
      frequency: row.frequency || 'monthly',
      effective_start: row.effective_start || '',
      effective_end: row.effective_end || '',
      is_active: row.is_active !== false,
    });
    setPlanDialog(true);
  };

  const saveComponent = async () => {
    if (!compForm.code.trim() || !compForm.name.trim() || !compForm.direction) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    const payload = {
      code: compForm.code.trim(),
      name: compForm.name.trim(),
      name_ar: compForm.name_ar.trim(),
      direction: compForm.direction,
      category: compForm.category.trim(),
      is_eosi_base: Boolean(compForm.is_eosi_base),
      is_gosi_base: Boolean(compForm.is_gosi_base),
      is_wps_relevant: Boolean(compForm.is_wps_relevant),
      is_taxable: Boolean(compForm.is_taxable),
      is_variable: Boolean(compForm.is_variable),
      sort_order: parseInt(compForm.sort_order, 10) || 100,
      is_active: Boolean(compForm.is_active),
    };
    setSaving(true);
    try {
      if (editingComp) {
        await updateCompensationComponent(editingComp.id, payload, token);
      } else {
        await createCompensationComponent(payload, token);
      }
      setCompDialog(false);
      setEditingComp(null);
      setSnackbar({ open: true, message: t('compensationComponentSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const savePlan = async () => {
    if (!planForm.component || !planForm.amount || !planForm.effective_start) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    const amount = Number(planForm.amount);
    if (Number.isNaN(amount)) {
      setSnackbar({ open: true, message: t('compensationAmountInvalid'), severity: 'error' });
      return;
    }
    const payload = {
      org_unit: null,
      pay_grade_code: planForm.pay_grade_code.trim(),
      job_family_code: planForm.job_family_code.trim(),
      component: Number(planForm.component),
      amount,
      currency: planForm.currency.trim() || 'KWD',
      frequency: planForm.frequency || 'monthly',
      effective_start: planForm.effective_start,
      effective_end: planForm.effective_end || null,
      is_active: Boolean(planForm.is_active),
    };
    setSaving(true);
    try {
      if (editingPlan) {
        await updateCompensationPlan(editingPlan.id, payload, token);
      } else {
        await createCompensationPlan(payload, token);
      }
      setPlanDialog(false);
      setEditingPlan(null);
      setSnackbar({ open: true, message: t('compensationPlanSaved'), severity: 'success' });
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
      if (deleteTarget.kind === 'comp') {
        await deleteCompensationComponent(deleteTarget.row.id, token);
        setSnackbar({ open: true, message: t('compensationComponentDeleted'), severity: 'success' });
      } else {
        await deleteCompensationPlan(deleteTarget.row.id, token);
        setSnackbar({ open: true, message: t('compensationPlanDeleted'), severity: 'success' });
      }
      setDeleteTarget(null);
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setDeleting(false);
    }
  };

  const componentOptions = useMemo(
    () => components.map((c) => ({ value: String(c.id), label: `${c.code} — ${c.name}` })),
    [components],
  );

  const componentColumns = useMemo(() => {
    const cols = [
      { field: 'code', headerName: t('colCode'), flex: 1, minWidth: 110 },
      { field: 'name', headerName: t('colName'), flex: 1.4, minWidth: 160 },
      {
        field: 'direction',
        headerName: t('colDirection'),
        width: 110,
        renderCell: (p) => (
          <Chip
            size="small"
            color={p.value === 'earning' ? 'success' : 'warning'}
            variant="outlined"
            label={t(`compDirection_${p.value}`, { defaultValue: p.value || '—' })}
          />
        ),
      },
      { field: 'category', headerName: t('colCategory'), width: 120, valueGetter: (v) => v || '—' },
      {
        field: 'is_eosi_base',
        headerName: t('colEosiBase'),
        width: 100,
        renderCell: (p) => (p.value ? t('yes') : t('no')),
      },
      {
        field: 'is_gosi_base',
        headerName: t('colGosiBase'),
        width: 100,
        renderCell: (p) => (p.value ? t('yes') : t('no')),
      },
      { field: 'sort_order', headerName: t('colSortOrder'), width: 90 },
    ];
    if (canMutate) {
      cols.push({
        field: 'actions',
        headerName: t('colActions'),
        width: 90,
        sortable: false,
        filterable: false,
        renderCell: (p) => (
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            <Tooltip title={tCommon('edit')}>
              <IconButton size="small" aria-label={tCommon('edit')} onClick={() => openCompEdit(p.row)} sx={{ color: 'primary.main' }}>
                <EditIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title={tCommon('delete')}>
              <IconButton size="small" aria-label={tCommon('delete')} onClick={() => setDeleteTarget({ kind: 'comp', row: p.row })} sx={{ color: 'error.main' }}>
                <DeleteIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      });
    }
    return cols;
  }, [t, tCommon, canMutate]);

  const planColumns = useMemo(() => {
    const cols = [
      { field: 'pay_grade_code', headerName: t('colPayGrade'), width: 110, valueGetter: (v) => v || '—' },
      { field: 'job_family_code', headerName: t('colJobFamily'), width: 120, valueGetter: (v) => v || '—' },
      {
        field: 'component_code',
        headerName: t('colComponent'),
        flex: 1,
        minWidth: 120,
        valueGetter: (_v, row) => row.component_code || row.component || '—',
      },
      {
        field: 'amount',
        headerName: t('colAmount'),
        width: 110,
        valueGetter: (_v, row) => `${row.amount ?? '—'} ${row.currency || ''}`.trim(),
      },
      {
        field: 'frequency',
        headerName: t('colFrequency'),
        width: 100,
        valueGetter: (v) => (v ? t(`compFrequency_${v}`, { defaultValue: v }) : '—'),
      },
      {
        field: 'effective_start',
        headerName: t('colEffectiveFrom'),
        width: 120,
        valueGetter: (v) => formatDate(v),
      },
      {
        field: 'effective_end',
        headerName: t('colEffectiveTo'),
        width: 120,
        valueGetter: (v) => formatDate(v),
      },
    ];
    if (canMutate) {
      cols.push({
        field: 'actions',
        headerName: t('colActions'),
        width: 90,
        sortable: false,
        filterable: false,
        renderCell: (p) => (
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            <Tooltip title={tCommon('edit')}>
              <IconButton size="small" aria-label={tCommon('edit')} onClick={() => openPlanEdit(p.row)} sx={{ color: 'primary.main' }}>
                <EditIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title={tCommon('delete')}>
              <IconButton size="small" aria-label={tCommon('delete')} onClick={() => setDeleteTarget({ kind: 'plan', row: p.row })} sx={{ color: 'error.main' }}>
                <DeleteIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      });
    }
    return cols;
  }, [t, tCommon, canMutate]);

  if (loading) return <LoadingSkeleton variant="table" />;
  if (error) return <ErrorAlert message={error} onRetry={loadData} />;

  return (
    <Stack spacing={3}>
      <Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} sx={{ mb: 1 }}>
          <Box>
            <Typography variant="subtitle1">{t('compensationComponentsTitle')}</Typography>
            <Typography variant="caption" color="text.secondary">{t('compensationComponentsHint')}</Typography>
          </Box>
          {canMutate && (
            <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={openCompCreate}>
              {t('actionAddCompensationComponent')}
            </Button>
          )}
        </Stack>
        {components.length === 0 ? (
          <EmptyState
            icon={<AccountBalanceWalletIcon />}
            title={t('compensationComponentsEmpty')}
            description={t('compensationComponentsEmptyDesc')}
            actionLabel={canMutate ? t('actionAddCompensationComponent') : undefined}
            onAction={canMutate ? openCompCreate : undefined}
          />
        ) : (
          <StandardDataGrid
            rows={components}
            columns={componentColumns}
            getRowId={(r) => r.id}
            density="compact"
            disableRowSelectionOnClick
            pageSize={25}
            sx={{ height: 360 }}
          />
        )}
      </Box>

      <Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} sx={{ mb: 1 }}>
          <Box>
            <Typography variant="subtitle1">{t('compensationPlanTitle')}</Typography>
            <Typography variant="caption" color="text.secondary">{t('compensationPlanHint')}</Typography>
          </Box>
          {canMutate && (
            <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={openPlanCreate} disabled={components.length === 0}>
              {t('actionAddCompensationPlan')}
            </Button>
          )}
        </Stack>
        {plans.length === 0 ? (
          <EmptyState
            icon={<AccountBalanceWalletIcon />}
            title={t('compensationPlanEmpty')}
            description={t('compensationPlanEmptyDesc')}
            actionLabel={canMutate && components.length > 0 ? t('actionAddCompensationPlan') : undefined}
            onAction={canMutate && components.length > 0 ? openPlanCreate : undefined}
          />
        ) : (
          <StandardDataGrid
            rows={plans}
            columns={planColumns}
            getRowId={(r) => r.id}
            density="compact"
            disableRowSelectionOnClick
            pageSize={25}
            sx={{ height: 360 }}
          />
        )}
      </Box>

      <SystemDialog
        open={compDialog}
        title={editingComp ? t('compensationComponentEditTitle') : t('compensationComponentCreateTitle')}
        onClose={() => setCompDialog(false)}
        onCancel={() => setCompDialog(false)}
        height={520}
        actions={(
          <Button size="small" variant="contained" onClick={saveComponent} disabled={saving}>
            {saving ? t('saving') : tCommon('save')}
          </Button>
        )}
      >
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              size="small"
              fullWidth
              required
              name="code"
              label={t('colCode')}
              value={compForm.code}
              onChange={handleCompChange}
              disabled={Boolean(editingComp)}
            />
            <TextField size="small" fullWidth required select name="direction" label={t('colDirection')} value={compForm.direction} onChange={handleCompChange}>
              {DIRECTIONS.map((d) => (
                <MenuItem key={d} value={d}>{t(`compDirection_${d}`)}</MenuItem>
              ))}
            </TextField>
          </Stack>
          <TextField size="small" fullWidth required name="name" label={t('colName')} value={compForm.name} onChange={handleCompChange} />
          <TextField size="small" fullWidth name="name_ar" label={t('formNameAr')} value={compForm.name_ar} onChange={handleCompChange} />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField size="small" fullWidth name="category" label={t('colCategory')} value={compForm.category} onChange={handleCompChange} />
            <TextField size="small" fullWidth name="sort_order" label={t('colSortOrder')} value={compForm.sort_order} onChange={handleCompChange} />
          </Stack>
          <Stack direction="row" flexWrap="wrap" gap={1}>
            <FormControlLabel control={<Switch size="small" name="is_eosi_base" checked={compForm.is_eosi_base} onChange={handleCompChange} />} label={t('colEosiBase')} />
            <FormControlLabel control={<Switch size="small" name="is_gosi_base" checked={compForm.is_gosi_base} onChange={handleCompChange} />} label={t('colGosiBase')} />
            <FormControlLabel control={<Switch size="small" name="is_wps_relevant" checked={compForm.is_wps_relevant} onChange={handleCompChange} />} label={t('colWpsRelevant')} />
            <FormControlLabel control={<Switch size="small" name="is_taxable" checked={compForm.is_taxable} onChange={handleCompChange} />} label={t('colTaxable')} />
            <FormControlLabel control={<Switch size="small" name="is_variable" checked={compForm.is_variable} onChange={handleCompChange} />} label={t('colVariable')} />
            <FormControlLabel control={<Switch size="small" name="is_active" checked={compForm.is_active} onChange={handleCompChange} />} label={t('colActive')} />
          </Stack>
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={planDialog}
        title={editingPlan ? t('compensationPlanEditTitle') : t('compensationPlanCreateTitle')}
        onClose={() => setPlanDialog(false)}
        onCancel={() => setPlanDialog(false)}
        height={480}
        actions={(
          <Button size="small" variant="contained" onClick={savePlan} disabled={saving}>
            {saving ? t('saving') : tCommon('save')}
          </Button>
        )}
      >
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <SearchSelect
            label={t('colComponent')}
            options={componentOptions}
            value={planForm.component}
            onChange={(v) => setPlanForm((prev) => ({ ...prev, component: v?.value ?? '' }))}
            required
            clearable={false}
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField size="small" fullWidth name="pay_grade_code" label={t('colPayGrade')} value={planForm.pay_grade_code} onChange={handlePlanChange} />
            <TextField size="small" fullWidth name="job_family_code" label={t('colJobFamily')} value={planForm.job_family_code} onChange={handlePlanChange} />
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField size="small" fullWidth required name="amount" label={t('colAmount')} value={planForm.amount} onChange={handlePlanChange} />
            <TextField size="small" fullWidth name="currency" label={t('colCurrency')} value={planForm.currency} onChange={handlePlanChange} />
            <TextField size="small" fullWidth select name="frequency" label={t('colFrequency')} value={planForm.frequency} onChange={handlePlanChange}>
              {FREQUENCIES.map((f) => (
                <MenuItem key={f} value={f}>{t(`compFrequency_${f}`)}</MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              size="small"
              fullWidth
              required
              type="date"
              name="effective_start"
              label={t('colEffectiveFrom')}
              value={planForm.effective_start}
              onChange={handlePlanChange}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              size="small"
              fullWidth
              type="date"
              name="effective_end"
              label={t('colEffectiveTo')}
              value={planForm.effective_end}
              onChange={handlePlanChange}
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
          <FormControlLabel
            control={<Switch size="small" name="is_active" checked={planForm.is_active} onChange={handlePlanChange} />}
            label={t('colActive')}
          />
        </Stack>
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={deleteTarget?.kind === 'plan' ? t('compensationPlanDeleteTitle') : t('compensationComponentDeleteTitle')}
        message={deleteTarget?.kind === 'plan' ? t('compensationPlanDeleteConfirm') : t('compensationComponentDeleteConfirm')}
        confirmLabel={tCommon('delete')}
        cancelLabel={tCommon('cancel')}
        destructive
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} variant="filled" onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Stack>
  );
}
