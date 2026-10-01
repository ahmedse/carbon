// Compliance rules on People Config. Drafts are editable. Published versions are not.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PublishIcon from '@mui/icons-material/Publish';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTranslation } from 'react-i18next';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { FormField, SearchSelect } from '../../components/Form';
import { useAuth } from '../../auth/AuthContext';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import {
  fetchComplianceRules,
  createComplianceRule,
  updateComplianceRule,
  deleteComplianceRule,
  copyForwardComplianceRule,
  submitComplianceRule,
} from '../../api/people';
import { formatDate, refCode, refLabel } from './utils';

const EMPTY_FORM = {
  rule_id: '',
  version: '',
  name: '',
  description: '',
  jurisdiction: '',
  category: '',
  effective_date: '',
  formula_ref: '',
  source_citation: '',
  inputs_schema: '{\n  "formula": { "type": "scaled_rate", "params": {} }\n}',
  test_cases: '[]',
};

const LIFECYCLE_TONE = {
  draft: 'info',
  in_review: 'warning',
  authoritative: 'success',
  superseded: 'default',
};

function parseObject(text, fallback) {
  const parsed = text.trim() ? JSON.parse(text) : fallback;
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('not-object');
  }
  return parsed;
}

function readParams(text) {
  try {
    const parsed = JSON.parse(text || '{}');
    return parsed?.formula?.params || {};
  } catch {
    return null;
  }
}

function writeParam(text, key, value) {
  const parsed = JSON.parse(text || '{}');
  if (!parsed.formula || typeof parsed.formula !== 'object') {
    parsed.formula = { type: 'scaled_rate', params: {} };
  }
  parsed.formula.params = parsed.formula.params || {};
  if (value === '' || value == null) delete parsed.formula.params[key];
  else parsed.formula.params[key] = value;
  return JSON.stringify(parsed, null, 2);
}

export default function ComplianceRulesPanel() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { token } = useAuth();
  const categoryRef = useReferenceOptions('compliance_category');
  const jurisdictionRef = useReferenceOptions('jurisdiction');

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [highlightId, setHighlightId] = useState(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [fieldError, setFieldError] = useState('');
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
    const message = fb?.detail || err?.detail || err?.message || t('actionError');
    setSnackbar({ open: true, message, severity: 'error' });
    return message;
  };

  const visibleRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter && row.lifecycle !== statusFilter) return false;
      if (!q) return true;
      return [row.rule_id, row.version, row.name].some((value) => String(value || '').toLowerCase().includes(q));
    });
  }, [rows, search, statusFilter]);

  const params = readParams(form.inputs_schema);
  const schemaInvalid = params === null;

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setFieldError('');
    setDialogOpen(true);
  };

  const openEdit = (row) => {
    setEditing(row);
    setFieldError('');
    setForm({
      rule_id: row.rule_id ?? '',
      version: row.version ?? '',
      name: row.name ?? '',
      description: row.description ?? '',
      jurisdiction: refCode(row.jurisdiction) || '',
      category: refCode(row.category) || '',
      effective_date: row.effective_date ?? '',
      formula_ref: row.formula_ref ?? '',
      source_citation: row.source_citation ?? '',
      inputs_schema: JSON.stringify(row.inputs_schema ?? {}, null, 2),
      test_cases: JSON.stringify(row.test_cases ?? [], null, 2),
    });
    setDialogOpen(true);
  };

  const setField = (name, value) => {
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const setParam = (key, value) => {
    setForm((prev) => {
      try {
        return { ...prev, inputs_schema: writeParam(prev.inputs_schema, key, value) };
      } catch {
        return prev;
      }
    });
  };

  const handleSave = async () => {
    if (!form.rule_id.trim() || !form.version.trim() || !form.name.trim() || !form.effective_date || !form.category || !form.jurisdiction) {
      setFieldError(tCommon('allFieldsRequired'));
      return;
    }
    let inputsSchema;
    let testCases;
    try {
      inputsSchema = parseObject(form.inputs_schema, {});
      const parsedCases = form.test_cases.trim() ? JSON.parse(form.test_cases) : [];
      if (!Array.isArray(parsedCases)) throw new Error('cases');
      testCases = parsedCases;
    } catch {
      setFieldError(t('complianceInputsSchemaInvalid'));
      return;
    }
    const payload = {
      rule_id: form.rule_id.trim(),
      version: form.version.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      jurisdiction: form.jurisdiction.trim(),
      category: form.category,
      effective_date: form.effective_date,
      formula_ref: form.formula_ref.trim(),
      source_citation: form.source_citation.trim(),
      inputs_schema: inputsSchema,
      test_cases: testCases,
    };
    setSaving(true);
    setFieldError('');
    try {
      if (editing) await updateComplianceRule(editing.id, payload, token);
      else await createComplianceRule(payload, token);
      setDialogOpen(false);
      setEditing(null);
      setSnackbar({ open: true, message: t('complianceRuleSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      setFieldError(showError(err));
    } finally {
      setSaving(false);
    }
  };

  const runAction = async (fn, successKey) => {
    try {
      await fn();
      setSnackbar({ open: true, message: t(successKey), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
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
    { field: 'rule_id', headerName: t('colRuleId'), flex: 1.1, minWidth: 140 },
    { field: 'version', headerName: t('colVersion'), width: 90 },
    { field: 'name', headerName: t('colName'), flex: 1.2, minWidth: 160 },
    {
      field: 'category',
      headerName: t('colCategory'),
      width: 120,
      valueGetter: (_v, row) => refLabel(row.category) || refCode(row.category) || '—',
    },
    {
      field: 'effective_date',
      headerName: t('colEffectiveDate'),
      width: 120,
      valueGetter: (value) => formatDate(value),
    },
    {
      field: 'lifecycle',
      headerName: t('complianceStatusFilter'),
      width: 140,
      renderCell: (p) => (
        <Chip
          size="small"
          variant="outlined"
          color={LIFECYCLE_TONE[p.value] || 'default'}
          label={t(`complianceLifecycle_${p.value}`, { defaultValue: p.value || '—' })}
        />
      ),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 150,
      sortable: false,
      renderCell: (p) => {
        const row = p.row;
        const lifecycle = row.lifecycle;
        return (
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            {lifecycle === 'draft' && (
              <Tooltip title={tCommon('edit')}>
                <IconButton size="small" aria-label={tCommon('edit')} onClick={() => openEdit(row)}>
                  <EditIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            {lifecycle === 'draft' && (
              <Tooltip title={t('complianceSubmit')}>
                <IconButton size="small" aria-label={t('complianceSubmit')} onClick={() => runAction(() => submitComplianceRule(row.id, token), 'complianceSubmitted')}>
                  <PublishIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            {lifecycle === 'in_review' && (
              <Tooltip title={t('compliancePublishOnDeskHint')}>
                <IconButton
                  size="small"
                  component={RouterLink}
                  to={`/catalog/policy-versions?focus=${row.id}`}
                  aria-label={t('compliancePublishOnDesk')}
                >
                  <OpenInNewIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            {(lifecycle === 'authoritative' || lifecycle === 'superseded') && (
              <Tooltip title={t('complianceNewVersion')}>
                <IconButton size="small" aria-label={t('complianceNewVersion')} onClick={() => runAction(() => copyForwardComplianceRule(row.id, token), 'complianceCopied')}>
                  <AddIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            {lifecycle === 'draft' && (
              <Tooltip title={tCommon('delete')}>
                <IconButton size="small" aria-label={tCommon('delete')} onClick={() => setDeleteTarget(row)}>
                  <DeleteIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        );
      },
    },
  ], [t, tCommon, token]);

  const statusOptions = ['draft', 'in_review', 'authoritative', 'superseded'].map((value) => ({
    value,
    label: t(`complianceLifecycle_${value}`),
  }));

  return (
    <Stack spacing={1.5}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
        <Box>
          <Typography variant="subtitle1">{t('configComplianceRules')}</Typography>
          <Typography variant="caption" color="text.secondary">{t('compliancePublishOnDeskHint')}</Typography>
        </Box>
        <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          {t('complianceNewVersion')}
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
          actionLabel={t('complianceNewVersion')}
          onAction={openCreate}
        />
      ) : (
        <FilteredDataGrid
          embedded
          rows={visibleRows}
          columns={columns}
          getRowId={(row) => row.id}
          loading={false}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('complianceSearch')}
          filterDefs={[{
            key: 'lifecycle',
            label: t('complianceStatusFilter'),
            options: statusOptions,
          }]}
          filterValues={{ lifecycle: statusFilter }}
          onFilterChange={(_key, value) => setStatusFilter(value || '')}
          onClearFilters={() => setStatusFilter('')}
          pageSize={25}
          height={480}
          onRowClick={(params) => setHighlightId(params.id)}
          highlightRow={(row) => row.id === highlightId}
          dataGridProps={{ density: 'compact', disableRowSelectionOnClick: true }}
        />
      )}

      <SystemDialog
        open={dialogOpen}
        title={editing ? t('complianceRuleEditTitle') : t('complianceRuleCreateTitle')}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        height={640}
        actions={(
          <Button size="small" variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? t('saving') : tCommon('save')}
          </Button>
        )}
      >
        <Stack spacing={0.5} sx={{ pt: 0.5 }}>
          {fieldError ? <Alert severity="error">{fieldError}</Alert> : null}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <FormField label={t('colRuleId')} required>
              <TextField size="small" fullWidth name="rule_id" value={form.rule_id} onChange={(e) => setField('rule_id', e.target.value)} disabled={Boolean(editing)} inputProps={{ 'aria-label': t('colRuleId') }} />
            </FormField>
            <FormField label={t('colVersion')} required>
              <TextField size="small" fullWidth name="version" value={form.version} onChange={(e) => setField('version', e.target.value)} disabled={Boolean(editing)} inputProps={{ 'aria-label': t('colVersion') }} />
            </FormField>
          </Stack>
          <FormField label={t('colName')} required>
            <TextField size="small" fullWidth value={form.name} onChange={(e) => setField('name', e.target.value)} inputProps={{ 'aria-label': t('colName') }} />
          </FormField>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <Box sx={{ flex: 1 }}>
              <SearchSelect
                label={t('colJurisdiction')}
                options={jurisdictionRef.options}
                value={form.jurisdiction}
                onChange={(v) => setField('jurisdiction', v?.value ?? '')}
                loading={jurisdictionRef.loading}
                error={jurisdictionRef.error}
                onRetry={jurisdictionRef.refetch}
                required
                clearable={false}
              />
            </Box>
            <Box sx={{ flex: 1 }}>
              <SearchSelect
                label={t('colCategory')}
                options={categoryRef.options}
                value={form.category}
                onChange={(v) => setField('category', v?.value ?? '')}
                loading={categoryRef.loading}
                error={categoryRef.error}
                onRetry={categoryRef.refetch}
                required
                clearable={false}
              />
            </Box>
          </Stack>
          <FormField label={t('colEffectiveDate')} required>
            <TextField size="small" fullWidth type="date" value={form.effective_date} onChange={(e) => setField('effective_date', e.target.value)} inputProps={{ 'aria-label': t('colEffectiveDate') }} />
          </FormField>
          <FormField label={t('formSourceCitation')}>
            <TextField size="small" fullWidth value={form.source_citation} onChange={(e) => setField('source_citation', e.target.value)} />
          </FormField>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <FormField label={t('formDivisor')}>
              <TextField
                size="small"
                fullWidth
                value={schemaInvalid ? '' : (params.divisor ?? '')}
                disabled={schemaInvalid}
                onChange={(e) => setParam('divisor', e.target.value)}
              />
            </FormField>
            <FormField label={t('formCapMonths')}>
              <TextField
                size="small"
                fullWidth
                value={schemaInvalid ? '' : (params.cap_months ?? '')}
                disabled={schemaInvalid}
                onChange={(e) => setParam('cap_months', e.target.value)}
              />
            </FormField>
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <FormField label={t('formFractionNumerator')}>
              <TextField
                size="small"
                fullWidth
                value={schemaInvalid ? '' : (params.fraction?.numerator ?? '')}
                disabled={schemaInvalid}
                onChange={(e) => setParam('fraction', { ...(params?.fraction || {}), numerator: e.target.value })}
              />
            </FormField>
            <FormField label={t('formFractionDenominator')}>
              <TextField
                size="small"
                fullWidth
                value={schemaInvalid ? '' : (params.fraction?.denominator ?? '')}
                disabled={schemaInvalid}
                onChange={(e) => setParam('fraction', { ...(params?.fraction || {}), denominator: e.target.value })}
              />
            </FormField>
          </Stack>
          <Accordion disableGutters elevation={0}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2">{t('complianceAdvancedJson')}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                size="small"
                fullWidth
                multiline
                minRows={4}
                value={form.inputs_schema}
                onChange={(e) => setField('inputs_schema', e.target.value)}
                error={schemaInvalid}
                helperText={schemaInvalid ? t('complianceInputsSchemaInvalid') : t('formInputsSchemaHint')}
              />
              <TextField
                sx={{ mt: 1 }}
                size="small"
                fullWidth
                multiline
                minRows={3}
                label={t('complianceExamples')}
                value={form.test_cases}
                onChange={(e) => setField('test_cases', e.target.value)}
              />
            </AccordionDetails>
          </Accordion>
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={Boolean(deleteTarget)}
        title={t('complianceRuleDeleteTitle')}
        onClose={() => setDeleteTarget(null)}
        onCancel={() => setDeleteTarget(null)}
        actions={(
          <Button size="small" color="error" variant="contained" onClick={confirmDelete}>
            {tCommon('delete')}
          </Button>
        )}
      >
        <Typography variant="body2">
          {t('complianceRuleDeleteConfirm', { id: deleteTarget?.rule_id || '' })}
        </Typography>
      </SystemDialog>

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} variant="filled" onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Stack>
  );
}
