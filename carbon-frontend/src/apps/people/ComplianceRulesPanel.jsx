// src/apps/people/ComplianceRulesPanel.jsx
// Compliance Rules CRUD for People Config (NSR-5B). SystemDialog + api helpers only.

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
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTranslation } from 'react-i18next';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import StandardDataGrid from '../../components/StandardDataGrid';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchComplianceRules,
  createComplianceRule,
  updateComplianceRule,
  deleteComplianceRule,
} from '../../api/people';
import { formatDate } from './utils';
import { FONT } from '../../theme/themeTokens';

const CATEGORIES = ['leave', 'eosi', 'gosi', 'wps', 'overtime', 'payroll', 'other'];

const EMPTY_FORM = {
  rule_id: '',
  version: '',
  name: '',
  description: '',
  jurisdiction: 'KW',
  category: 'other',
  effective_date: '',
  formula_ref: '',
  source_citation: '',
  inputs_schema: '{}',
  is_authoritative: false,
};

function tipHeader(tip) {
  return (params) => (
    <Tooltip title={tip} arrow enterDelay={400} placement="top">
      <span>{params.colDef.headerName}</span>
    </Tooltip>
  );
}

export default function ComplianceRulesPanel() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { token } = useAuth();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchComplianceRules(token);
      setRows(Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []));
    } catch (err) {
      setError(err?.message || t('configLoadError'));
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

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setDialogOpen(true);
  };

  const openEdit = (row) => {
    setEditing(row);
    setForm({
      rule_id: row.rule_id ?? '',
      version: row.version ?? '',
      name: row.name ?? '',
      description: row.description ?? '',
      jurisdiction: row.jurisdiction ?? 'KW',
      category: row.category ?? 'other',
      effective_date: row.effective_date ?? '',
      formula_ref: row.formula_ref ?? '',
      source_citation: row.source_citation ?? '',
      inputs_schema: JSON.stringify(row.inputs_schema ?? {}, null, 2),
      is_authoritative: Boolean(row.is_authoritative),
    });
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditing(null);
  };

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (!form.rule_id.trim() || !form.version.trim() || !form.name.trim() || !form.effective_date || !form.category) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    let inputsSchema = {};
    try {
      inputsSchema = form.inputs_schema.trim() ? JSON.parse(form.inputs_schema) : {};
      if (typeof inputsSchema !== 'object' || Array.isArray(inputsSchema)) {
        throw new Error('not-object');
      }
    } catch {
      setSnackbar({ open: true, message: t('complianceInputsSchemaInvalid'), severity: 'error' });
      return;
    }

    const payload = {
      rule_id: form.rule_id.trim(),
      version: form.version.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      jurisdiction: form.jurisdiction.trim() || 'KW',
      category: form.category,
      effective_date: form.effective_date,
      formula_ref: form.formula_ref.trim(),
      source_citation: form.source_citation.trim(),
      inputs_schema: inputsSchema,
      is_authoritative: Boolean(form.is_authoritative),
    };

    setSaving(true);
    try {
      if (editing) {
        await updateComplianceRule(editing.id, payload, token);
      } else {
        await createComplianceRule(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('complianceRuleSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteComplianceRule(deleteTarget.id, token);
      setDeleteTarget(null);
      setSnackbar({ open: true, message: t('complianceRuleDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      setDeleteTarget(null);
      showError(err);
    }
  };

  const columns = useMemo(() => [
    { field: 'rule_id', headerName: t('colRuleId'), flex: 1.1, minWidth: 140, renderHeader: tipHeader(t('colRuleIdTip')) },
    { field: 'version', headerName: t('colVersion'), width: 90 },
    { field: 'name', headerName: t('colName'), flex: 1.3, minWidth: 160 },
    {
      field: 'jurisdiction',
      headerName: t('colJurisdiction'),
      width: 100,
      renderHeader: tipHeader(t('colJurisdictionTip')),
    },
    {
      field: 'category',
      headerName: t('colCategory'),
      width: 110,
      renderCell: (p) => (
        <Chip size="small" variant="outlined" label={t(`complianceCategory_${p.value}`, { defaultValue: p.value || '—' })} />
      ),
    },
    {
      field: 'effective_date',
      headerName: t('colEffectiveDate'),
      width: 120,
      valueGetter: (v) => formatDate(v),
    },
    {
      field: 'is_authoritative',
      headerName: t('colAuthoritative'),
      width: 120,
      renderCell: (p) => (
        <Chip
          size="small"
          variant="outlined"
          color={p.value ? 'success' : 'default'}
          label={p.value ? t('yes') : t('no')}
        />
      ),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 90,
      sortable: false,
      filterable: false,
      renderCell: (p) => (
        <Box sx={{ display: 'flex', gap: 0.25 }}>
          <Tooltip title={tCommon('edit')}>
            <IconButton size="small" aria-label={tCommon('edit')} onClick={() => openEdit(p.row)} sx={{ color: 'primary.main' }}>
              <EditIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title={tCommon('delete')}>
            <IconButton size="small" aria-label={tCommon('delete')} onClick={() => setDeleteTarget(p.row)} sx={{ color: 'error.main' }}>
              <DeleteIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], [t, tCommon]);

  return (
    <Stack spacing={1.5}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
        <Typography sx={{ ...FONT.heading }}>{t('configComplianceRules')}</Typography>
        <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          {t('actionAddComplianceRule')}
        </Button>
      </Stack>

      {loading ? (
        <LoadingSkeleton variant="table" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<SettingsIcon />}
          title={t('configEmpty')}
          description={t('configEmptyDesc')}
          actionLabel={t('actionAddComplianceRule')}
          onAction={openCreate}
        />
      ) : (
        <StandardDataGrid
          rows={rows}
          columns={columns}
          getRowId={(r) => r.id}
          density="compact"
          disableRowSelectionOnClick
          pageSize={25}
          sx={{ height: 480 }}
        />
      )}

      <SystemDialog
        open={dialogOpen}
        title={editing ? t('complianceRuleEditTitle') : t('complianceRuleCreateTitle')}
        onClose={closeDialog}
        onCancel={closeDialog}
        height={560}
        actions={(
          <Button size="small" variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? t('saving') : tCommon('save')}
          </Button>
        )}
      >
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField size="small" fullWidth required name="rule_id" label={t('colRuleId')} value={form.rule_id} onChange={handleChange} disabled={Boolean(editing)} />
            <TextField size="small" fullWidth required name="version" label={t('colVersion')} value={form.version} onChange={handleChange} disabled={Boolean(editing)} />
          </Stack>
          <TextField size="small" fullWidth required name="name" label={t('colName')} value={form.name} onChange={handleChange} />
          <TextField size="small" fullWidth multiline minRows={2} name="description" label={t('colDescription')} value={form.description} onChange={handleChange} />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField size="small" fullWidth name="jurisdiction" label={t('colJurisdiction')} value={form.jurisdiction} onChange={handleChange} />
            <TextField size="small" fullWidth required select name="category" label={t('colCategory')} value={form.category} onChange={handleChange}>
              {CATEGORIES.map((c) => (
                <MenuItem key={c} value={c}>{t(`complianceCategory_${c}`)}</MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              fullWidth
              required
              type="date"
              name="effective_date"
              label={t('colEffectiveDate')}
              value={form.effective_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
          <TextField size="small" fullWidth name="formula_ref" label={t('formFormulaRef')} value={form.formula_ref} onChange={handleChange} />
          <TextField size="small" fullWidth multiline minRows={2} name="source_citation" label={t('formSourceCitation')} value={form.source_citation} onChange={handleChange} />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={3}
            name="inputs_schema"
            label={t('formInputsSchema')}
            value={form.inputs_schema}
            onChange={handleChange}
            helperText={t('formInputsSchemaHint')}
          />
          <FormControlLabel
            control={<Switch size="small" name="is_authoritative" checked={form.is_authoritative} onChange={handleChange} />}
            label={t('colAuthoritative')}
          />
        </Stack>
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={t('complianceRuleDeleteTitle')}
        message={t('complianceRuleDeleteConfirm', { id: deleteTarget?.rule_id || '' })}
        confirmLabel={tCommon('delete')}
        destructive
        onConfirm={confirmDelete}
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
