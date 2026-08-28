// src/pages/emissions/CalculationRulesPage.jsx
// Calculation Rules admin — CRUD + execute actions
// Canonical shell: FilteredDataGrid + SystemDialog + ConfirmDialog (see EmissionFactorsPage / GWPReferencePage)
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  TextField,
  MenuItem,
  Switch,
  FormControlLabel,
  CircularProgress,
  Typography,
  Stack,
  IconButton,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { FONT } from '../../theme/themeTokens';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import {
  fetchCalculationRules,
  createCalculationRule,
  updateCalculationRule,
  deleteCalculationRule,
  executeCalculationRule,
} from '../../api/emissions-extended';

// ── RuleTypeChip ────────────────────────────────────────────────────────

function RuleTypeChip({ value }) {
  const { t } = useTranslation('emissions');
  const cfg = {
    direct:       { label: t('ruleTypeDirect'),       palette: 'success' },
    unit_convert: { label: t('ruleTypeUnitConvert'), palette: 'info' },
    formula:      { label: t('ruleTypeFormula'),      palette: 'warning' },
  };
  const meta = cfg[value] || { label: value, palette: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.palette === 'default' ? undefined : meta.palette}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── RulesDialog ─────────────────────────────────────────────────────────

function RulesDialog({ open, rule, tables = [], factors = [], onSave, onClose }) {
  const { t } = useTranslation('emissions');
  const [form, setForm] = useState({
    name: '',
    description: '',
    data_table: '',
    activity_field: '',
    emission_factor: '',
    rule_type: 'direct',
    unit_conversion_factor: 1,
    is_active: true,
    auto_calculate: false,
  });

  useEffect(() => {
    if (rule) {
      setForm({
        name: rule.name || '',
        description: rule.description || '',
        data_table: rule.data_table || '',
        activity_field: rule.activity_field || '',
        emission_factor: rule.emission_factor || '',
        rule_type: rule.rule_type || 'direct',
        unit_conversion_factor: rule.unit_conversion_factor ?? 1,
        is_active: rule.is_active ?? true,
        auto_calculate: rule.auto_calculate ?? false,
      });
    } else {
      setForm({
        name: '',
        description: '',
        data_table: '',
        activity_field: '',
        emission_factor: '',
        rule_type: 'direct',
        unit_conversion_factor: 1,
        is_active: true,
        auto_calculate: false,
      });
    }
  }, [rule, open]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = () => {
    onSave(form);
  };

  return (
    <SystemDialog
      open={open}
      title={rule ? t('editRuleTitle') : t('createRuleTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancel')}
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          {rule ? t('update') : t('create')}
        </Button>
      }
      width={540}
      height={680}
      minWidth={420}
      minHeight={460}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <TextField
            label={t('name')}
            name="name"
            value={form.name}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          />
          <TextField
            label={t('description')}
            name="description"
            value={form.description}
            onChange={handleChange}
            fullWidth
            multiline
            rows={2}
            size="small"
          />
          <TextField
            label={t('dataTable')}
            select
            name="data_table"
            value={form.data_table}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="">{t('selectTable')}</MenuItem>
            {tables.map((tableItem) => (
              <MenuItem key={tableItem.id} value={tableItem.id}>{tableItem.name || tableItem.label || tableItem.id}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('activityField')}
            name="activity_field"
            value={form.activity_field}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder={t('fieldNameOrId')}
          />
          <TextField
            label={t('emissionFactor')}
            select
            name="emission_factor"
            value={form.emission_factor}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="">{t('selectFactor')}</MenuItem>
            {factors.map((f) => (
              <MenuItem key={f.id} value={f.id}>{f.name || f.id}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('ruleType')}
            select
            name="rule_type"
            value={form.rule_type}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="direct">{t('ruleTypeDirect')}</MenuItem>
            <MenuItem value="unit_convert">{t('ruleTypeUnitConvert')}</MenuItem>
            <MenuItem value="formula">{t('ruleTypeFormula')}</MenuItem>
          </TextField>
          {form.rule_type === 'unit_convert' && (
            <TextField
              label={t('unitConversionFactor')}
              name="unit_conversion_factor"
              type="number"
              value={form.unit_conversion_factor}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ step: 0.001 }}
            />
          )}
          <FormControlLabel
            control={<Switch checked={form.is_active} onChange={handleChange} name="is_active" size="small" />}
            label={t('active')}
          />
          <FormControlLabel
            control={<Switch checked={form.auto_calculate} onChange={handleChange} name="auto_calculate" size="small" />}
            label={t('autoCalculate')}
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── ExecuteDialog ──────────────────────────────────────────────────────

function ExecuteDialog({ open, rule, onClose, onConfirm, loading }) {
  const { t } = useTranslation('emissions');
  const [periodId, setPeriodId] = useState('');

  useEffect(() => {
    if (open) setPeriodId('');
  }, [open]);

  return (
    <SystemDialog
      open={open}
      title={t('executeRuleTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancel')}
      showCancel={false}
      actions={
        <>
          <Button onClick={onClose} color="inherit" disabled={loading}>
            {t('cancel')}
          </Button>
          <Button
            onClick={() => onConfirm(rule, periodId)}
            variant="contained"
            color="success"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
          >
            {loading ? t('running') : t('execute')}
          </Button>
        </>
      }
      width={480}
      height={320}
      minWidth={400}
      minHeight={260}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Typography sx={{ ...FONT.body, mb: 2 }}>
          {t('runRule')} <strong>{rule?.name || rule?.id}</strong>?
        </Typography>
        <TextField
          label={t('reportingPeriodId')}
          name="period_id"
          value={periodId}
          onChange={(e) => setPeriodId(e.target.value)}
          fullWidth
          size="small"
          placeholder={t('reportingPeriodHint')}
        />
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function CalculationRulesPage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('calculationRulesTitle'));
  const { user, token } = useAuth();
  const [rules, setRules] = useState([]);
  const [factors, _setFactors] = useState([]);
  const [tables, _setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [executeOpen, setExecuteOpen] = useState(false);
  const [executingRule, setExecutingRule] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [currentRule, setCurrentRule] = useState(null);

  const { notify, notifyFromError } = useNotification();
  const isAdmin = user?.is_superuser || user?.groups?.includes('admins_group');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const rulesData = await fetchCalculationRules(token);
      setRules(Array.isArray(rulesData) ? rulesData : rulesData?.results || []);
    } catch (err) {
      notifyFromError(err, t('failedToLoadRules'));
      setError(err.message || t('failedToLoadRules'));
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = () => {
    setCurrentRule(null);
    setDrawerOpen(true);
  };

  const handleEdit = (rule) => {
    setCurrentRule(rule);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    try {
      if (currentRule) {
        await updateCalculationRule(currentRule.id, formData, token);
      } else {
        await createCalculationRule(formData, token);
      }
      setDrawerOpen(false);
      setCurrentRule(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, t('failedToSaveRule'));
      setError(err.message || t('failedToSaveRule'));
    }
  };

  const handleDelete = async (ruleId) => {
    try {
      const result = await deleteCalculationRule(ruleId, token);
      if (result && result.archived) {
        notify({
          message: t('ruleArchived', { count: result.audit_count || 0 }),
          type: 'info',
        });
      } else {
        notify({ message: t('ruleDeleted'), type: 'success' });
      }
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, t('failedToDeleteRule'));
      setError(err.message || t('failedToDeleteRule'));
    }
  };

  const handleExecute = async (rule, periodId) => {
    setExecuting(true);
    try {
      const payload = periodId ? { reporting_period_id: periodId } : {};
      await executeCalculationRule(rule.id, payload, token);
      setExecuteOpen(false);
      setExecutingRule(null);
      notify({ message: t('ruleExecuted', { name: rule.name || rule.id }), type: 'success' });
      await loadData();
    } catch (err) {
      notifyFromError(err, t('executionFailed'));
    } finally {
      setExecuting(false);
    }
  };

  // ── Columns ───────────────────────────────────────────────────────────

  const columns = [
    { field: 'id', headerName: t('id'), width: 70 },
    { field: 'name', headerName: t('name'), flex: 1, minWidth: 160 },
    {
      field: 'data_table',
      headerName: t('dataTable'),
      width: 140,
      valueGetter: (value, row) => row?.data_table_name || row?.data_table || '—',
    },
    {
      field: 'activity_field',
      headerName: t('activityField'),
      width: 140,
      valueGetter: (value, row) => row?.activity_field_name || row?.activity_field || '—',
    },
    {
      field: 'emission_factor',
      headerName: t('emissionFactor'),
      width: 150,
      valueGetter: (value, row) => row?.emission_factor_name || row?.emission_factor || '—',
    },
    {
      field: 'emission_factor_code',
      headerName: t('factorCode'),
      width: 130,
      valueGetter: (value, row) => row?.emission_factor_code || '—',
    },
    {
      field: 'rule_type',
      headerName: t('ruleType'),
      width: 120,
      renderCell: (params) => <RuleTypeChip value={params.value} />,
    },
    {
      field: 'is_active',
      headerName: t('active'),
      width: 90,
      renderCell: (params) => (
        <Chip
          label={params.value ? t('yes') : t('no')}
          size="small"
          color={params.value ? 'success' : 'default'}
          variant="outlined"
          sx={{ height: 2.5, ...FONT.body }}
        />
      ),
    },
    {
      field: 'auto_calculate',
      headerName: t('autoCalculate'),
      width: 110,
      renderCell: (params) => (
        <Chip
          label={params.value ? t('yes') : t('no')}
          size="small"
          color={params.value ? 'info' : 'default'}
          variant="outlined"
          sx={{ height: 2.5, ...FONT.body }}
        />
      ),
    },
    {
      field: 'last_executed_at',
      headerName: t('lastModified'),
      width: 140,
      valueFormatter: (value) => (value ? new Date(value).toLocaleDateString() : '—'),
    },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: t('actions'),
            width: 130,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => handleEdit(params.row)} title={t('edit')}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  color="success"
                  onClick={() => { setExecutingRule(params.row); setExecuteOpen(true); }}
                  title={t('executeNow')}
                >
                  <PlayArrowIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm(params.row.id)}
                  sx={{ color: 'error.main' }}
                  title={t('delete')}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            ),
          },
        ]
      : []),
  ];

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <FilteredDataGrid
        title={t('calculationRulesTitle')}
        subtitle={t('rulesSubtitle', { count: rules.length })}
        description={t('rulesDescription')}
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" title={t('refresh')}>
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleCreate}>
                {t('newRule')}
              </Button>
            )}
          </Stack>
        }
        rows={rules}
        loading={loading}
        columns={columns}
        countLabel={t('rulesCountLabel', { count: rules.length })}
        emptyMessage={t('noRulesFound')}
        emptySubtext={isAdmin ? t('noRulesAdmin') : t('noRulesUser')}
      />

      {/* Create/Edit Dialog */}
      <RulesDialog
        open={drawerOpen}
        rule={currentRule}
        tables={tables}
        factors={factors}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Execute Dialog */}
      <ExecuteDialog
        open={executeOpen}
        rule={executingRule}
        onClose={() => { setExecuteOpen(false); setExecutingRule(null); }}
        onConfirm={handleExecute}
        loading={executing}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title={t('deleteRuleTitle')}
        message={t('deleteRuleMessage')}
        confirmLabel={t('delete')}
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </>
  );
}
