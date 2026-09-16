// src/apps/people/PoliciesPage.jsx
// People & Payroll — Leave Policy Registry (LPR-1B). Dense CRUD grid + lifecycle
// (draft → active → deprecated) with a create/edit dialog. All colours via theme
// tokens; apiFetch only; SystemDialog for the form; FONT tokens for typography.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
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
import PublishIcon from '@mui/icons-material/Publish';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTranslation } from 'react-i18next';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import ErrorAlert from '../../components/Page/ErrorAlert';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchLeavePolicies,
  createLeavePolicy,
  updateLeavePolicy,
  deprecateLeavePolicy,
  propagateLeavePolicy,
} from '../../api/people';
import { formatDate } from './utils';
import { FONT } from '../../theme/themeTokens';

const EMPTY_FORM = {
  name: '',
  description: '',
  leave_type: '',
  status: 'active',
  effective_from: '',
  effective_to: '',
  default_entitled_days: '0',
  max_carryover_days: '0',
  is_carryover_allowed: false,
  accrual_method: 'upfront',
  gender_restriction: 'any',
  requires_approval: true,
  min_service_days: '0',
  applies_to_contract_types: '',
  applies_to_kuwaitization: 'any',
  applies_to_rotations: '',
  category: '',
  tags: '',
  notes: '',
};

const STATUS_OPTIONS = ['draft', 'active', 'deprecated'];

function statusChipColor(status) {
  if (status === 'draft') return 'warning';
  if (status === 'active') return 'success';
  return 'default';
}

function splitComma(value) {
  return String(value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function PoliciesPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const navigate = useNavigate();
  useDocumentTitle(t('policiesTitle'));
  const { token } = useAuth();

  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({ leave_type: '', status: '', category: '', tag: '' });

  const [openDialog, setOpenDialog] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  const [deprecateTarget, setDeprecateTarget] = useState(null);
  const [deprecating, setDeprecating] = useState(false);

  const [propagateAllRunning, setPropagateAllRunning] = useState(false);

  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchLeavePolicies(token);
      setPolicies(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err?.message || t('policiesLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const leaveTypeOptions = useMemo(() => {
    const set = new Set();
    policies.forEach((p) => { if (p.leave_type) set.add(p.leave_type); });
    return [...set].sort();
  }, [policies]);

  const categoryOptions = useMemo(() => {
    const set = new Set();
    policies.forEach((p) => { if (p.category) set.add(p.category); });
    return [...set].sort();
  }, [policies]);

  const tagOptions = useMemo(() => {
    const set = new Set();
    policies.forEach((p) => {
      if (Array.isArray(p.tags)) p.tags.forEach((tag) => { if (tag) set.add(tag); });
    });
    return [...set].sort();
  }, [policies]);

  const filterDefs = useMemo(() => [
    {
      key: 'category',
      label: t('filterCategory'),
      emptyLabel: t('filterAll'),
      options: categoryOptions.map((code) => ({ value: code, label: code })),
    },
    {
      key: 'leave_type',
      label: t('filterLeaveType'),
      emptyLabel: t('filterAll'),
      options: leaveTypeOptions.map((code) => ({ value: code, label: code })),
    },
    {
      key: 'tag',
      label: t('filterTag'),
      emptyLabel: t('filterAll'),
      options: tagOptions.map((tag) => ({ value: tag, label: tag })),
    },
    {
      key: 'status',
      label: t('filterStatus'),
      emptyLabel: t('filterAll'),
      options: STATUS_OPTIONS.map((s) => ({ value: s, label: t(`status${s.charAt(0).toUpperCase()}${s.slice(1)}`) })),
    },
  ], [t, leaveTypeOptions, categoryOptions, tagOptions]);

  const filteredRows = useMemo(() => {
    const needle = searchValue.trim().toLowerCase();
    return policies.filter((p) => {
      if (filters.category && p.category !== filters.category) return false;
      if (filters.leave_type && p.leave_type !== filters.leave_type) return false;
      if (filters.tag && !(Array.isArray(p.tags) && p.tags.includes(filters.tag))) return false;
      if (filters.status && p.status !== filters.status) return false;
      if (needle) {
        const hay = `${p.name ?? ''} ${p.category ?? ''} ${p.leave_type_label ?? ''} ${p.leave_type ?? ''} ${Array.isArray(p.tags) ? p.tags.join(' ') : ''}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [policies, filters, searchValue]);

  const openCreate = () => {
    setEditingPolicy(null);
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  };

  const openEdit = (policy) => {
    setEditingPolicy(policy);
    setForm({
      name: policy.name ?? '',
      description: policy.description ?? '',
      leave_type: policy.leave_type ?? '',
      status: policy.status ?? 'active',
      effective_from: policy.effective_from ?? '',
      effective_to: policy.effective_to ?? '',
      default_entitled_days: String(policy.default_entitled_days ?? '0'),
      max_carryover_days: String(policy.max_carryover_days ?? '0'),
      is_carryover_allowed: Boolean(policy.is_carryover_allowed),
      accrual_method: policy.accrual_method ?? 'upfront',
      gender_restriction: policy.gender_restriction ?? 'any',
      requires_approval: Boolean(policy.requires_approval),
      min_service_days: String(policy.min_service_days ?? '0'),
      applies_to_contract_types: Array.isArray(policy.applies_to_contract_types)
        ? policy.applies_to_contract_types.join(', ')
        : (policy.applies_to_contract_types ?? ''),
      applies_to_kuwaitization: policy.applies_to_kuwaitization ?? 'any',
      applies_to_rotations: Array.isArray(policy.applies_to_rotations)
        ? policy.applies_to_rotations.join(', ')
        : (policy.applies_to_rotations ?? ''),
      category: policy.category ?? '',
      tags: Array.isArray(policy.tags) ? policy.tags.join(', ') : (policy.tags ?? ''),
      notes: policy.notes ?? '',
    });
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingPolicy(null);
  };

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.leave_type.trim()) {
      setSnackbar({ open: true, message: t('policyFormValidation'), severity: 'error' });
      return;
    }

    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      leave_type: form.leave_type.trim(),
      status: form.status || 'active',
      effective_from: form.effective_from || null,
      effective_to: form.effective_to || null,
      default_entitled_days: parseFloat(form.default_entitled_days) || 0,
      max_carryover_days: parseFloat(form.max_carryover_days) || 0,
      is_carryover_allowed: Boolean(form.is_carryover_allowed),
      accrual_method: form.accrual_method || 'upfront',
      gender_restriction: form.gender_restriction || 'any',
      requires_approval: Boolean(form.requires_approval),
      min_service_days: parseInt(form.min_service_days, 10) || 0,
      applies_to_contract_types: splitComma(form.applies_to_contract_types),
      applies_to_kuwaitization: form.applies_to_kuwaitization || 'any',
      applies_to_rotations: splitComma(form.applies_to_rotations),
      category: form.category.trim(),
      tags: splitComma(form.tags),
      notes: form.notes,
    };

    setSaving(true);
    try {
      if (editingPolicy) {
        await updateLeavePolicy(editingPolicy.id, payload, token);
      } else {
        await createLeavePolicy(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('policySaved'), severity: 'success' });
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

  const confirmDeprecate = async () => {
    if (!deprecateTarget || deprecating) return;
    setDeprecating(true);
    try {
      await deprecateLeavePolicy(deprecateTarget.id, token);
      setDeprecateTarget(null);
      setSnackbar({ open: true, message: t('policyDeprecated'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    } finally {
      setDeprecating(false);
    }
  };

  const handlePropagateAll = async () => {
    if (propagateAllRunning) return;
    setPropagateAllRunning(true);
    try {
      const data = await fetchLeavePolicies(token);
      const all = Array.isArray(data) ? data : (data?.results || []);
      const active = all.filter((p) => p.status === 'active' || (!p.status && p.is_active));
      if (active.length === 0) {
        setSnackbar({ open: true, message: t('propagateAllEmpty'), severity: 'info' });
        return;
      }
      const year = new Date().getFullYear();
      let created = 0;
      let updated = 0;
      let failed = 0;
      for (const policy of active) {
        try {
          const res = await propagateLeavePolicy(policy.id, { year, dry_run: false }, token);
          created += Number(res?.will_create ?? res?.created ?? 0);
          updated += Number(res?.will_update ?? res?.updated ?? 0);
        } catch {
          failed += 1;
        }
      }
      const succeeded = active.length - failed;
      const payload = { policies: succeeded, created, updated, failed };
      setSnackbar({
        open: true,
        message: failed > 0 ? t('propagateAllPartial', payload) : t('propagateAllSummary', payload),
        severity: failed > 0 ? 'warning' : 'success',
      });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    } finally {
      setPropagateAllRunning(false);
    }
  };

  const columns = useMemo(() => {
    const nameCell = (params) => {
      const title = params.row.name || '—';
      const desc = params.row.description || '';
      return (
        <Tooltip title={desc || title} enterDelay={400}>
          <Typography noWrap sx={{ ...FONT.body2, fontWeight: 600, width: '100%' }}>
            {title}
          </Typography>
        </Tooltip>
      );
    };

    const tagsCell = (params) => {
      const tags = Array.isArray(params.row.tags) ? params.row.tags.filter(Boolean) : [];
      if (tags.length === 0) return '—';
      const visible = tags.slice(0, 3);
      const extra = tags.length - visible.length;
      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            minWidth: 0,
            overflow: 'hidden',
            width: '100%',
          }}
        >
          {visible.map((tag) => (
            <Chip
              key={tag}
              size="small"
              variant="outlined"
              label={tag}
              sx={{ height: 20, maxWidth: 96, '& .MuiChip-label': { px: 0.75, ...FONT.caption } }}
            />
          ))}
          {extra > 0 && (
            <Typography sx={{ ...FONT.caption, color: 'text.secondary', flexShrink: 0 }}>
              +{extra}
            </Typography>
          )}
        </Box>
      );
    };

    return [
      { field: 'name', headerName: t('colName'), flex: 1.2, minWidth: 220, renderCell: nameCell },
      {
        field: 'tags',
        headerName: t('colTags'),
        flex: 0.9,
        minWidth: 160,
        sortable: false,
        renderCell: tagsCell,
      },
      {
        field: 'category',
        headerName: t('colCategory'),
        width: 130,
        renderCell: (p) => (p.row.category ? <Chip size="small" variant="filled" color="primary" label={p.row.category} /> : '—'),
      },
      {
        field: 'leave_type',
        headerName: t('colLeaveType'),
        width: 140,
        renderCell: (p) => (
          <Chip size="small" variant="outlined" label={p.row.leave_type_label || p.row.leave_type || '—'} />
        ),
      },
      {
        field: 'status',
        headerName: t('colStatus'),
        width: 110,
        renderCell: (p) => (
          <Chip
            size="small"
            color={statusChipColor(p.value)}
            label={p.value ? t(`status${p.value.charAt(0).toUpperCase()}${p.value.slice(1)}`) : '—'}
          />
        ),
      },
      { field: 'default_entitled_days', headerName: t('colDefaultDays'), width: 140, valueGetter: (v) => v ?? '—' },
      { field: 'employee_count', headerName: t('colEmployeeCount'), width: 110, valueGetter: (v) => v ?? '—' },
      { field: 'effective_from', headerName: t('colEffectiveFrom'), width: 130, valueGetter: (v) => formatDate(v) },
      {
        field: 'actions',
        headerName: t('colActions'),
        width: 120,
        sortable: false,
        filterable: false,
        renderCell: (p) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            <Tooltip title={t('actionViewPolicy')}>
              <IconButton size="small" onClick={() => navigate(`/people/policies/${p.row.id}`)} sx={{ color: 'primary.main' }}>
                <VisibilityIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t('actionEditPolicy')}>
              <IconButton size="small" onClick={() => openEdit(p.row)} sx={{ color: 'primary.main' }}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t('actionDeprecatePolicy')}>
              <IconButton size="small" onClick={() => setDeprecateTarget(p.row)} sx={{ color: 'error.main' }}>
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      },
    ];
  }, [t, navigate]);

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  if (error) {
    return (
      <PageContainer>
        <ErrorAlert message={error} onRetry={loadData} />
      </PageContainer>
    );
  }

  return (
    <>
      <FilteredDataGrid
        title={t('policiesTitle')}
        subtitle={t('policiesSubtitle')}
        description={t('policiesDescription')}
        actions={
          <>
            <Button
              variant="outlined"
              size="small"
              startIcon={propagateAllRunning ? <CircularProgress size={14} color="inherit" /> : <PublishIcon />}
              onClick={handlePropagateAll}
              disabled={propagateAllRunning || loading}
            >
              {propagateAllRunning ? t('propagateAllRunning') : t('actionPropagateAll')}
            </Button>
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
              {t('actionNewPolicy')}
            </Button>
          </>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={t('policiesCount', { count: filteredRows.length, total: policies.length })}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ leave_type: '', status: '', category: '', tag: '' });
        }}
        emptyMessage={t('policiesEmpty')}
        emptySubtext={t('policiesEmptyDesc')}
      />

      {/* Create / edit dialog */}
      <SystemDialog
        open={openDialog}
        title={editingPolicy ? t('policyEditTitle') : t('policyCreateTitle')}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? t('saving') : tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField label={t('formName')} name="name" value={form.name} onChange={handleChange} fullWidth required />
          <TextField label={t('formDescription')} name="description" value={form.description} onChange={handleChange} fullWidth multiline minRows={2} />
          <TextField
            label={t('colLeaveType')}
            name="leave_type"
            value={form.leave_type}
            onChange={handleChange}
            fullWidth
            required
            placeholder="annual / sick / emergency / maternity / paternity / unpaid"
          />
          <Stack direction="row" spacing={2}>
            <TextField select size="small" label={t('formStatus')} name="status" value={form.status} onChange={handleChange} fullWidth>
              {STATUS_OPTIONS.map((status) => (
                <MenuItem key={status} value={status}>{t(`status${status.charAt(0).toUpperCase()}${status.slice(1)}`)}</MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label={t('colAccrual')} name="accrual_method" value={form.accrual_method} onChange={handleChange} fullWidth>
              <MenuItem value="upfront">{t('accrualUpfront')}</MenuItem>
              <MenuItem value="monthly">{t('accrualMonthly')}</MenuItem>
            </TextField>
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField size="small" label={t('formEffectiveFrom')} name="effective_from" value={form.effective_from} onChange={handleChange} type="date" slotProps={{ inputLabel: { shrink: true } }} fullWidth />
            <TextField size="small" label={t('formEffectiveTo')} name="effective_to" value={form.effective_to} onChange={handleChange} type="date" slotProps={{ inputLabel: { shrink: true } }} fullWidth />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField size="small" label={t('colDefaultDays')} name="default_entitled_days" value={form.default_entitled_days} onChange={handleChange} type="number" slotProps={{ htmlInput: { step: '0.5' } }} fullWidth />
            <TextField size="small" label={t('colMaxCarryover')} name="max_carryover_days" value={form.max_carryover_days} onChange={handleChange} type="number" slotProps={{ htmlInput: { step: '0.5' } }} fullWidth />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField select size="small" label={t('colGender')} name="gender_restriction" value={form.gender_restriction} onChange={handleChange} fullWidth>
              <MenuItem value="any">{t('genderAny')}</MenuItem>
              <MenuItem value="male">{t('genderMale')}</MenuItem>
              <MenuItem value="female">{t('genderFemale')}</MenuItem>
            </TextField>
            <TextField size="small" label={t('colMinService')} name="min_service_days" value={form.min_service_days} onChange={handleChange} type="number" slotProps={{ htmlInput: { step: '1', min: '0' } }} fullWidth />
          </Stack>
          <TextField label={t('formContractTypes')} name="applies_to_contract_types" value={form.applies_to_contract_types} onChange={handleChange} fullWidth helperText={t('formContractTypesHint')} />
          <Stack direction="row" spacing={2}>
            <TextField select size="small" label={t('formKuwaitization')} name="applies_to_kuwaitization" value={form.applies_to_kuwaitization} onChange={handleChange} fullWidth helperText={t('formKuwaitizationHint')}>
              <MenuItem value="any">{t('kuwaitiAny')}</MenuItem>
              <MenuItem value="kuwaiti">{t('kuwaitiKuwaiti')}</MenuItem>
              <MenuItem value="non_kuwaiti">{t('kuwaitiNonKuwaiti')}</MenuItem>
            </TextField>
            <TextField label={t('formRotations')} name="applies_to_rotations" value={form.applies_to_rotations} onChange={handleChange} fullWidth helperText={t('formRotationsHint')} />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField label={t('formCategory')} name="category" value={form.category} onChange={handleChange} fullWidth helperText={t('formCategoryHint')} />
            <TextField label={t('formTags')} name="tags" value={form.tags} onChange={handleChange} fullWidth helperText={t('formTagsHint')} />
          </Stack>
          <TextField label={t('colNotes')} name="notes" value={form.notes} onChange={handleChange} fullWidth multiline minRows={2} />
          <Stack direction="row" spacing={3}>
            <FormControlLabel
              control={<Switch checked={form.is_carryover_allowed} onChange={handleChange} name="is_carryover_allowed" color="primary" />}
              label={t('colCarryoverAllowed')}
            />
            <FormControlLabel
              control={<Switch checked={form.requires_approval} onChange={handleChange} name="requires_approval" color="primary" />}
              label={t('colRequiresApproval')}
            />
          </Stack>
        </Stack>
      </SystemDialog>

      {/* Deprecate confirm */}
      <ConfirmDialog
        open={Boolean(deprecateTarget)}
        title={t('actionDeprecatePolicy')}
        message={t('policyDeprecateConfirm', { name: deprecateTarget?.name || deprecateTarget?.leave_type_label || '' })}
        confirmLabel={t('actionDeprecatePolicy')}
        cancelLabel={t('cancel')}
        destructive
        onConfirm={confirmDeprecate}
        onCancel={() => setDeprecateTarget(null)}
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
    </>
  );
}
