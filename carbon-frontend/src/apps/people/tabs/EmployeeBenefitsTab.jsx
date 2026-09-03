// src/apps/people/tabs/EmployeeBenefitsTab.jsx
// Per-employee benefits bindings (full CRUD). The employee is pinned to the
// current 360 record; benefit *types* are reference data managed in App Config.
// Assignment dropdown lists active benefit types only (retired types are shown
// if already assigned). Manage-gated via PEOPLE_MANAGE.

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
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CardGiftcardIcon from '@mui/icons-material/CardGiftcard';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useTranslation } from 'react-i18next';
import EmptyState from '../../../components/Page/EmptyState';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import StandardDataGrid from '../../../components/StandardDataGrid';
import { useNotification } from '../../../components/NotificationProvider';
import { useAuth } from '../../../auth/AuthContext';
import { PEOPLE_MANAGE } from '../../../capabilities';
import {
  fetchBenefitTypes,
  createEmployeeBenefit,
  updateEmployeeBenefit,
  deleteEmployeeBenefit,
} from '../../../api/people';
import { buildBenefitTypeLabels, formatAmount, formatDate } from '../utils';

const EMPTY_BEN = {
  benefit_type: '',
  monthly_amount: '',
  effective_start: '',
  effective_end: '',
};

const tipHeader = (tip) => (params) => (
  <Tooltip title={tip} arrow enterDelay={400} placement="top">
    <span>{params.colDef.headerName}</span>
  </Tooltip>
);

export default function EmployeeBenefitsTab({ entityData, additionalProps }) {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { notify } = useNotification();
  const token = additionalProps?.token;
  const onSaved = additionalProps?.onSaved;
  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;

  const { isGlobalAdminFlag, userCapabilities } = useAuth();
  const caps = Array.isArray(userCapabilities) ? userCapabilities : [];
  const canManage = isGlobalAdminFlag === true || caps.includes(PEOPLE_MANAGE);

  const [benefitTypes, setBenefitTypes] = useState([]);
  const [benefitTypeLabels, setBenefitTypeLabels] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_BEN });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // Rows are derived from the 360 payload (already loaded on the detail page).
  const rows = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    return (emp.benefits || [])
      .filter((b) => b.employee === empId)
      .map((b) => ({ ...b, _active: !b.effective_end || b.effective_end >= today }))
      .sort((a, b) => String(a.effective_start).localeCompare(String(b.effective_start)));
  }, [emp.benefits, empId]);

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    fetchBenefitTypes(token)
      .then((data) => {
        if (!mounted) return;
        const list = Array.isArray(data) ? data : data?.results || [];
        setBenefitTypes(list);
        setBenefitTypeLabels(buildBenefitTypeLabels(list));
      })
      .catch(() => {});
    return () => { mounted = false; };
  }, [token]);

  const typeName = (id) => benefitTypeLabels[id] ?? id ?? '—';

  // Active types only for new assignments; keep the current type when editing.
  const selectableTypes = useMemo(() => {
    const active = benefitTypes.filter((ty) => ty.is_active !== false);
    if (editing) {
      const cur = benefitTypes.find((ty) => ty.id === editing.benefit_type);
      if (cur && !active.some((ty) => ty.id === cur.id)) active.unshift(cur);
    }
    return active;
  }, [benefitTypes, editing]);

  const showError = (err) => {
    const fb = err?.feedback;
    setSnackbar({
      open: true,
      message: fb?.detail || fb?.title || err?.message || t('actionError'),
      severity: 'error',
    });
  };

  const openCreate = useCallback(() => {
    setEditing(null);
    setForm({ ...EMPTY_BEN });
    setDialogOpen(true);
  }, []);

  const openEdit = useCallback((benefit) => {
    setEditing(benefit);
    setForm({
      benefit_type: benefit.benefit_type ?? '',
      monthly_amount: benefit.monthly_amount != null ? String(benefit.monthly_amount) : '',
      effective_start: benefit.effective_start ? String(benefit.effective_start).slice(0, 10) : '',
      effective_end: benefit.effective_end ? String(benefit.effective_end).slice(0, 10) : '',
    });
    setDialogOpen(true);
  }, []);

  const closeDialog = useCallback(() => {
    setDialogOpen(false);
    setEditing(null);
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (!form.benefit_type || !String(form.monthly_amount).trim() || !form.effective_start) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    const payload = {
      employee: Number(empId),
      benefit_type: Number(form.benefit_type),
      monthly_amount: String(form.monthly_amount).trim(),
      effective_start: form.effective_start,
      effective_end: form.effective_end ? form.effective_end : null,
    };
    setSaving(true);
    try {
      if (editing) {
        await updateEmployeeBenefit(editing.id, payload, token);
      } else {
        await createEmployeeBenefit(payload, token);
      }
      closeDialog();
      notify({ message: t('employeeBenefitSaved'), type: 'success' });
      onSaved?.();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const requestDelete = useCallback((row) => setDeleteTarget(row), []);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteEmployeeBenefit(deleteTarget.id, token);
      setDeleteTarget(null);
      notify({ message: t('employeeBenefitDeleted'), type: 'success' });
      onSaved?.();
    } catch (err) {
      setDeleteTarget(null);
      showError(err);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  const columns = useMemo(() => [
    {
      field: 'benefit_type',
      headerName: t('colBenefitType'),
      flex: 1.4,
      minWidth: 180,
      renderHeader: tipHeader(t('colBenefitTypeTip')),
      valueGetter: (v) => benefitTypeLabels[v] ?? v ?? '—',
    },
    {
      field: 'monthly_amount',
      headerName: t('colMonthlyAmount'),
      flex: 1,
      minWidth: 140,
      type: 'number',
      renderHeader: tipHeader(t('colMonthlyAmountTip')),
      valueGetter: (v) => (v == null || v === '' ? null : Number(v)),
      renderCell: (p) => formatAmount(p.value),
    },
    {
      field: 'effective_start',
      headerName: t('colEffectiveStart'),
      flex: 1,
      minWidth: 130,
      renderHeader: tipHeader(t('colEffectiveStartTip')),
      renderCell: (p) => formatDate(p.value),
    },
    {
      field: 'effective_end',
      headerName: t('colEffectiveEnd'),
      flex: 1,
      minWidth: 130,
      renderHeader: tipHeader(t('colEffectiveEndTip')),
      renderCell: (p) => formatDate(p.value),
    },
    {
      field: '_active',
      headerName: t('colStatus'),
      flex: 0.8,
      minWidth: 100,
      renderHeader: tipHeader(t('colBenefitStatusTip')),
      renderCell: (p) => (
        <Chip
          size="small"
          color={p.value ? 'success' : 'default'}
          label={p.value ? t('statusActive') : t('statusInactive')}
        />
      ),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 90,
      sortable: false,
      filterable: false,
      renderHeader: tipHeader(t('colActionsTip')),
      renderCell: (p) => (
        <Box sx={{ display: 'flex', gap: 0.25 }}>
          <Tooltip title={tCommon('edit')}>
            <IconButton size="small" aria-label={tCommon('edit')} onClick={() => openEdit(p.row)} sx={{ color: 'primary.main' }}>
              <EditIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title={tCommon('delete')}>
            <IconButton size="small" aria-label={tCommon('delete')} onClick={() => requestDelete(p.row)} sx={{ color: 'error.main' }}>
              <DeleteIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], [t, tCommon, benefitTypeLabels, openEdit, requestDelete]);

  const renderDialog = () => (
    <SystemDialog
      open={dialogOpen}
      title={editing ? t('employeeBenefitEditTitle') : t('employeeBenefitCreateTitle')}
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
          label={t('colBenefitType')}
          name="benefit_type"
          value={form.benefit_type}
          onChange={handleChange}
          fullWidth
          required
        >
          <MenuItem value="" disabled>{t('colBenefitType')}</MenuItem>
          {selectableTypes.map((type) => (
            <MenuItem key={type.id} value={type.id}>
              {typeName(type.id)}{type.is_active === false ? ` (${t('statusInactive')})` : ''}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label={t('colMonthlyAmount')}
          name="monthly_amount"
          value={form.monthly_amount}
          onChange={handleChange}
          type="number"
          slotProps={{ htmlInput: { step: '0.001' } }}
          fullWidth
          required
        />
        <TextField
          label={t('colEffectiveStart')}
          name="effective_start"
          value={form.effective_start}
          onChange={handleChange}
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
          fullWidth
          required
        />
        <TextField
          label={t('colEffectiveEnd')}
          name="effective_end"
          value={form.effective_end}
          onChange={handleChange}
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
          fullWidth
        />
      </Stack>
    </SystemDialog>
  );

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.25 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{t('employeeBenefitsTitle')}</Typography>
        {canManage && (
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddEmployeeBenefit')}
          </Button>
        )}
      </Box>

      {rows.length === 0 ? (
        <EmptyState
          icon={<CardGiftcardIcon />}
          title={t('employeeBenefitsEmpty')}
          description={t('employeeBenefitsEmptyDesc')}
          actionLabel={canManage ? t('actionAddEmployeeBenefit') : undefined}
          onAction={canManage ? openCreate : undefined}
        />
      ) : (
        <StandardDataGrid rows={rows} columns={columns} pageSize={25} sx={{ height: 440 }} />
      )}

      {canManage && renderDialog()}

      {canManage && (
        <ConfirmDialog
          open={!!deleteTarget}
          message={t('employeeBenefitDeleteConfirm')}
          confirmLabel={tCommon('delete')}
          destructive
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={5000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
