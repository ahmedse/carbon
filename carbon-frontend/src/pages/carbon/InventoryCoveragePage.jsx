// src/pages/carbon/InventoryCoveragePage.jsx
// Inventory coverage admin — the SOLE surface that reports Missing / Entered /
// Excluded for the declared universe (ADR-0020). This is the streams reporter;
// it is NOT a completeness claim and NOT a second state store.
//
// Toolkit only, ADR-0018 EN+AR parity, RULE 13 SearchSelect for governed /
// data-driven enums, RULE 14 grid search, shared Layer-2 primitives
// (StatusChip / ProgressBar / NumericText / StatCard) instead of page-local
// forks. No page-local fontSize / hex.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import WorkflowCard from '../../components/Cards/WorkflowCard';
import StatCard from '../../components/Cards/StatCard';
import StatusChip from '../../components/StatusChip';
import ProgressBar from '../../components/ProgressBar';
import LtrText from '../../components/LtrText';
import NumericText from '../../components/NumericText';
import StandardDataGrid from '../../components/StandardDataGrid';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import { SearchSelect } from '../../components/Form';
import { Scope2MethodChip } from './Scope2Labels';
import { TierChip } from './coverageTargetsShared';
import { formatDisplayDate } from '../../utils/dateUtils';
import { formatPercent } from '../../utils/formatNumber';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchReportingPeriods,
  fetchInventorySources,
  createInventorySource,
  updateInventorySource,
  deleteInventorySource,
  fetchInventorySourceStatuses,
  fetchCoverageGoals,
  createCoverageGoal,
  updateCoverageGoal,
  deleteCoverageGoal,
  fetchCoverageActions,
  createCoverageAction,
  updateCoverageAction,
  deleteCoverageAction,
  fetchCoverage,
  fetchCampusIntake,
  fetchCoverageReconciliation,
  setCoverageRowExclusion,
} from '../../api/emissions-extended';

// Scope labels are Latin domain terms that stay English inside an RTL sentence
// (ADR-0018) — isolated with the shared bdi primitive, not a page-local fork.
const SCOPE_MAP = {
  '1': { label: <LtrText>Scope 1</LtrText>, color: 'success' },
  '2': { label: <LtrText>Scope 2</LtrText>, color: 'warning' },
  '3': { label: <LtrText>Scope 3</LtrText>, color: 'primary' },
  '1+2': { label: <LtrText>Scope 1+2</LtrText>, color: 'info' },
  '1+2+3': { label: <LtrText>Scope 1+2+3</LtrText>, color: 'primary' },
};

// Coverage pct tone — the threshold policy stays with the caller; the shared
// ProgressBar only renders.
function coverageTone(value) {
  const pct = Number(value) || 0;
  if (pct >= 100) return 'success';
  if (pct >= 60) return 'info';
  if (pct >= 30) return 'warning';
  return 'error';
}

const REASON_KEY = {
  not_material: 'coverage.exclusionNotMaterial',
  insufficient_data: 'coverage.exclusionInsufficient',
  out_of_boundary: 'coverage.exclusionOutOfBoundary',
  other: 'coverage.exclusionOther',
  exclusion_notes: 'coverage.exclusionNotes',
  awaiting_factor: 'intake.statusAwaiting',
  diesel_stream_both: 'intake.exclusion.diesel_stream_both',
  diesel_stream_unlabelled: 'intake.exclusion.diesel_stream_unlabelled',
  open_period_count: 'intake.exclusion.open_period_count',
};

function reasonLabel(t, reason) {
  if (!reason) return '—';
  const key = REASON_KEY[reason];
  return key ? t(key) : String(reason);
}

function sourceOptions(t, sources) {
  return (sources || []).map((s) => ({
    value: String(s.id),
    label: s.source_name || t('inventoryCoverage.sourceFallback', { id: s.id }),
  }));
}

// ── SourceDialog ───────────────────────────────────────────────────────

function SourceDialog({ open, source, onSave, onClose }) {
  const { t } = useTranslation('emissions');
  const [form, setForm] = useState({
    org_unit: '',
    scope: '1',
    scope3_category: '',
    source_name: '',
    description: '',
    is_active: true,
  });

  useEffect(() => {
    if (source) {
      setForm({
        org_unit: source.org_unit ?? '',
        scope: source.scope != null ? String(source.scope) : '1',
        scope3_category: source.scope3_category ?? '',
        source_name: source.source_name || '',
        description: source.description || '',
        is_active: source.is_active ?? true,
      });
    } else {
      setForm({ org_unit: '', scope: '1', scope3_category: '', source_name: '', description: '', is_active: true });
    }
  }, [source, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <SystemDialog
      open={open}
      title={source ? t('inventoryCoverage.sourceEditTitle') : t('inventoryCoverage.sourceNewTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('common:cancel')}
      actions={
        <Button variant="contained" size="small" onClick={() => onSave(form)}>
          {source ? t('update') : t('create')}
        </Button>
      }
      width={540}
      height={560}
      minWidth={420}
      minHeight={420}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <TextField
            label={t('inventoryCoverage.orgUnit')}
            name="org_unit"
            value={form.org_unit}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder={t('inventoryCoverage.orgUnitPlaceholder')}
          />
          <TextField
            label={t('intake.scope')}
            select
            name="scope"
            value={form.scope}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          >
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
          </TextField>
          {form.scope === '3' && (
            <TextField
              label={t('inventoryCoverage.scope3Category')}
              name="scope3_category"
              type="number"
              value={form.scope3_category}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ min: 1, max: 15 }}
              helperText={t('inventoryCoverage.scope3CategoryHint')}
            />
          )}
          <TextField
            label={t('inventoryCoverage.sourceName')}
            name="source_name"
            value={form.source_name}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          />
          <TextField
            label={t('inventoryCoverage.description')}
            name="description"
            value={form.description}
            onChange={handleChange}
            fullWidth
            multiline
            rows={3}
            size="small"
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              />
            }
            label={t('inventoryCoverage.active')}
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── GoalDialog ─────────────────────────────────────────────────────────

function GoalDialog({ open, goal, onSave, onClose }) {
  const { t } = useTranslation('emissions');
  const [form, setForm] = useState({
    org_unit: '',
    name: '',
    scope: '1+2',
    target_coverage_pct: '',
    min_quality_tier: '',
    completeness_definition: 'materiality_bounded',
    target_year: '',
    sbti_target: '',
    status: 'active',
  });

  useEffect(() => {
    if (goal) {
      setForm({
        org_unit: goal.org_unit ?? '',
        name: goal.name || '',
        scope: goal.scope || '1+2+3',
        target_coverage_pct: goal.target_coverage_pct ?? '',
        min_quality_tier: goal.min_quality_tier ?? '',
        completeness_definition: goal.completeness_definition || 'materiality_bounded',
        target_year: goal.target_year ?? '',
        sbti_target: goal.sbti_target ?? '',
        status: goal.status || 'active',
      });
    } else {
      setForm({
        org_unit: '', name: '', scope: '1+2', target_coverage_pct: '', min_quality_tier: '',
        completeness_definition: 'materiality_bounded', target_year: '', sbti_target: '', status: 'active',
      });
    }
  }, [goal, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };
  const handleSelect = (name) => (option) => {
    setForm((prev) => ({ ...prev, [name]: option?.value ?? '' }));
  };

  const tierOptions = [
    { value: '', label: t('inventoryCoverage.qualityTierNone') },
    ...[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: t(`inventoryCoverage.tier${n}`) })),
  ];

  return (
    <SystemDialog
      open={open}
      title={goal ? t('inventoryCoverage.goalEditTitle') : t('inventoryCoverage.goalNewTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('common:cancel')}
      actions={
        <Button variant="contained" size="small" onClick={() => onSave(form)}>
          {goal ? t('update') : t('create')}
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
          <TextField label={t('inventoryCoverage.orgUnit')} name="org_unit" value={form.org_unit} onChange={handleChange} fullWidth size="small" placeholder={t('inventoryCoverage.orgUnitPlaceholder')} />
          <TextField label={t('inventoryCoverage.goalName')} name="name" value={form.name} onChange={handleChange} fullWidth required size="small" />
          <TextField label={t('intake.scope')} select name="scope" value={form.scope} onChange={handleChange} fullWidth size="small">
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
            <MenuItem value="1+2">Scope 1+2</MenuItem>
            <MenuItem value="1+2+3">Scope 1+2+3</MenuItem>
          </TextField>
          <TextField
            label={t('inventoryCoverage.targetCoveragePct')}
            name="target_coverage_pct"
            type="number"
            value={form.target_coverage_pct}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ min: 0, max: 100, step: 0.01 }}
          />
          <SearchSelect
            label={t('inventoryCoverage.minQualityTier')}
            options={tierOptions}
            value={form.min_quality_tier === null || form.min_quality_tier === undefined ? '' : String(form.min_quality_tier)}
            onChange={handleSelect('min_quality_tier')}
            clearable={false}
          />
          <SearchSelect
            label={t('inventoryCoverage.completenessDefinition')}
            options={[
              { value: 'absolute', label: t('inventoryCoverage.completenessAbsolute') },
              { value: 'materiality_bounded', label: t('inventoryCoverage.completenessMateriality') },
            ]}
            value={form.completeness_definition}
            onChange={handleSelect('completeness_definition')}
            clearable={false}
          />
          <TextField
            label={t('inventoryCoverage.targetYear')}
            name="target_year"
            type="number"
            value={form.target_year}
            onChange={handleChange}
            fullWidth
            required
            size="small"
            inputProps={{ min: 2020, max: 2100 }}
          />
          <TextField label={t('inventoryCoverage.sbtiTarget')} name="sbti_target" value={form.sbti_target} onChange={handleChange} fullWidth size="small" placeholder={t('inventoryCoverage.sbtiTargetPlaceholder')} />
          <SearchSelect
            label={t('coverageTargets.colStatus')}
            options={[
              { value: 'draft', label: t('coverageTargets.statusDraft') },
              { value: 'active', label: t('coverageTargets.statusActive') },
              { value: 'archived', label: t('coverageTargets.statusArchived') },
            ]}
            value={form.status}
            onChange={handleSelect('status')}
            clearable={false}
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── ActionDialog ───────────────────────────────────────────────────────

function ActionDialog({ open, action, sources, sourcesLoading, sourcesError, onSave, onClose }) {
  const { t } = useTranslation('emissions');
  const [form, setForm] = useState({
    source: '',
    action_type: 'collect_data',
    status: 'open',
    due_date: '',
    owner: '',
    notes: '',
  });

  useEffect(() => {
    if (action) {
      setForm({
        source: action.source != null ? String(action.source) : '',
        action_type: action.action_type || 'collect_data',
        status: action.status || 'open',
        due_date: action.due_date ?? '',
        owner: action.owner ?? '',
        notes: action.notes || '',
      });
    } else {
      setForm({ source: '', action_type: 'collect_data', status: 'open', due_date: '', owner: '', notes: '' });
    }
  }, [action, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };
  const handleSelect = (name) => (option) => {
    setForm((prev) => ({ ...prev, [name]: option?.value ?? '' }));
  };

  return (
    <SystemDialog
      open={open}
      title={action ? t('inventoryCoverage.actionEditTitle') : t('inventoryCoverage.actionNewTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('common:cancel')}
      actions={
        <Button variant="contained" size="small" onClick={() => onSave(form)}>
          {action ? t('update') : t('create')}
        </Button>
      }
      width={540}
      height={520}
      minWidth={420}
      minHeight={400}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <SearchSelect
            label={t('inventoryCoverage.source')}
            options={sourceOptions(t, sources)}
            value={form.source}
            onChange={handleSelect('source')}
            loading={sourcesLoading}
            error={sourcesError || undefined}
            noOptionsText={t('inventoryCoverage.noSources')}
            clearable={false}
            required
          />
          <SearchSelect
            label={t('inventoryCoverage.actionType')}
            options={[
              { value: 'collect_data', label: t('inventoryCoverage.actionTypeCollect') },
              { value: 'improve_quality', label: t('inventoryCoverage.actionTypeImprove') },
              { value: 'obtain_verification', label: t('inventoryCoverage.actionTypeVerification') },
              { value: 'formalize_exclusion', label: t('inventoryCoverage.actionTypeExclusion') },
            ]}
            value={form.action_type}
            onChange={handleSelect('action_type')}
            clearable={false}
          />
          <SearchSelect
            label={t('coverageTargets.colStatus')}
            options={[
              { value: 'open', label: t('coverageTargets.taskOpen') },
              { value: 'in_progress', label: t('coverageTargets.taskInProgress') },
              { value: 'done', label: t('coverageTargets.taskDone') },
              { value: 'blocked', label: t('coverageTargets.taskBlocked') },
            ]}
            value={form.status}
            onChange={handleSelect('status')}
            clearable={false}
          />
          <TextField
            label={t('inventoryCoverage.dueDate')}
            name="due_date"
            type="date"
            value={form.due_date}
            onChange={handleChange}
            fullWidth
            size="small"
            InputLabelProps={{ shrink: true }}
          />
          <TextField label={t('inventoryCoverage.owner')} name="owner" value={form.owner} onChange={handleChange} fullWidth size="small" placeholder={t('inventoryCoverage.ownerPlaceholder')} />
          <TextField label={t('inventoryCoverage.notes')} name="notes" value={form.notes} onChange={handleChange} fullWidth multiline rows={3} size="small" />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── ExclusionDialog ────────────────────────────────────────────────────
// Coverage is the only surface that reports Excluded, so it is also the only
// surface that declares one. The reason comes from a fixed vocabulary; "other"
// requires notes. Cancel clears the column, so the dialog never edits a value.

function ExclusionDialog({ open, row, onSave, onClose }) {
  const { t } = useTranslation('emissions');
  const excluding = row?.status !== 'excluded';
  const [reason, setReason] = useState('insufficient_data');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    if (open) {
      setReason('insufficient_data');
      setNotes('');
    }
  }, [open, row]);

  const handleSave = () => {
    if (excluding) {
      onSave({ excluded: true, reason, notes: notes.trim() });
    } else {
      onSave({ excluded: false, reason: '', notes: '' });
    }
  };

  const reasonOptions = [
    { value: 'not_material', label: t('coverage.exclusionNotMaterial') },
    { value: 'insufficient_data', label: t('coverage.exclusionInsufficient') },
    { value: 'out_of_boundary', label: t('coverage.exclusionOutOfBoundary') },
    { value: 'other', label: t('coverage.exclusionOther') },
  ];

  return (
    <SystemDialog
      open={open}
      title={excluding ? t('coverage.exclusionTitle') : t('coverage.reincludeTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('common:cancel')}
      actions={
        <Button variant="contained" size="small" onClick={handleSave}>
          {excluding ? t('coverage.excludeRow') : t('coverage.reincludeRow')}
        </Button>
      }
      width={520}
      height={excluding ? 420 : 300}
      minWidth={380}
      minHeight={excluding ? 340 : 240}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <Typography variant="body2" color="text.secondary">
            {t('coverage.exclusionRowLabel', {
              source: row?.source_name || '',
              campus: row?.campus || '',
            })}
          </Typography>
          {excluding ? (
            <>
              <SearchSelect
                label={t('coverage.exclusionReason')}
                options={reasonOptions}
                value={reason}
                onChange={(option) => setReason(option?.value ?? 'insufficient_data')}
                clearable={false}
                required
              />
              <TextField
                label={t('coverage.exclusionNotesField')}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                fullWidth
                multiline
                rows={3}
                size="small"
                required={reason === 'other'}
                helperText={reason === 'other' ? t('coverage.exclusionNotesRequired') : t('coverage.exclusionNotesHint')}
              />
            </>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t('coverage.reincludeHint')}
            </Typography>
          )}
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function InventoryCoveragePage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('inventoryCoverage.pageTitle'));
  const navigate = useNavigate();
  const { user, token, availablePerspectives } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [coverage, setCoverage] = useState(null);
  const [sources, setSources] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [goals, setGoals] = useState([]);
  const [actions, setActions] = useState([]);
  const [streams, setStreams] = useState([]);
  const [streamPeriods, setStreamPeriods] = useState([]);
  const [streamPeriodId, setStreamPeriodId] = useState('');
  const [streamError, setStreamError] = useState('');
  const [reconciliation, setReconciliation] = useState(null);

  const [loading, setLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState('');
  const [tab, setTab] = useState(0);

  // RULE 14: every growable record list is searchable.
  const [streamSearch, setStreamSearch] = useState({});
  const [goalSearch, setGoalSearch] = useState('');

  const [sourceOpen, setSourceOpen] = useState(false);
  const [goalOpen, setGoalOpen] = useState(false);
  const [actionOpen, setActionOpen] = useState(false);
  const [currentSource, setCurrentSource] = useState(null);
  const [currentGoal, setCurrentGoal] = useState(null);
  const [currentAction, setCurrentAction] = useState(null);
  const [exclusionRow, setExclusionRow] = useState(null);

  const [deleteConfirm, setDeleteConfirm] = useState(null); // { kind, id }

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [pData, sData, gData, aData] = await Promise.all([
        fetchReportingPeriods(token),
        fetchInventorySources(token),
        fetchCoverageGoals(token),
        fetchCoverageActions(token),
      ]);
      setPeriods(Array.isArray(pData) ? pData : pData?.results || []);
      setSources(Array.isArray(sData) ? sData : sData?.results || []);
      setGoals(Array.isArray(gData) ? gData : gData?.results || []);
      setActions(Array.isArray(aData) ? aData : aData?.results || []);
      setSourcesError('');
      try {
        const [intake, recon] = await Promise.all([
          fetchCampusIntake(token),
          fetchCoverageReconciliation(token).catch(() => null),
        ]);
        const boards = Array.isArray(intake?.periods) ? intake.periods : [];
        setStreamPeriods(boards);
        setStreams(Array.isArray(intake?.streams) ? intake.streams : []);
        const openBoard = boards.find((row) => row.role === 'open') || boards[0];
        setStreamPeriodId((current) => current || (openBoard ? String(openBoard.id) : ''));
        setStreamError('');
        setReconciliation(recon && typeof recon === 'object' ? recon : null);
      } catch (err) {
        setStreams([]);
        setStreamPeriods([]);
        setReconciliation(null);
        setStreamError(err?.message || t('intake.loadFailed'));
      }
    } catch (err) {
      notifyFromError(err, t('inventoryCoverage.loadFailedToast'));
      setPeriods([]);
      setSources([]);
      setGoals([]);
      setActions([]);
      setSourcesError(err?.message || t('inventoryCoverage.loadFailedToast'));
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Auto-select the first period once periods are available.
  useEffect(() => {
    if (periods.length > 0 && !selectedPeriod) {
      const open = periods.find((row) => row.status === 'open');
      setSelectedPeriod(String((open || periods[0]).id));
    }
  }, [periods, selectedPeriod]);

  const loadPeriodScoped = useCallback(async (periodId) => {
    if (!periodId) return;
    try {
      const [statusData, covData] = await Promise.all([
        fetchInventorySourceStatuses({ reporting_period: periodId }, token),
        fetchCoverage({ reporting_period: periodId }, token),
      ]);
      setStatuses(Array.isArray(statusData) ? statusData : statusData?.results || []);
      setCoverage(covData);
    } catch (err) {
      notifyFromError(err, t('inventoryCoverage.loadCoverageFailedToast'));
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    loadPeriodScoped(selectedPeriod);
  }, [selectedPeriod, loadPeriodScoped]);

  // ── CRUD handlers ──────────────────────────────────────────────────

  const handleSaveSource = async (formData) => {
    const payload = {
      ...formData,
      org_unit: formData.org_unit ? Number(formData.org_unit) : null,
      scope: formData.scope ? Number(formData.scope) : null,
      scope3_category: formData.scope3_category ? Number(formData.scope3_category) : null,
    };
    try {
      if (currentSource) {
        await updateInventorySource(currentSource.id, payload, token);
        notify({ message: t('inventoryCoverage.sourceUpdated'), type: 'success' });
      } else {
        await createInventorySource(payload, token);
        notify({ message: t('inventoryCoverage.sourceCreated'), type: 'success' });
      }
      setSourceOpen(false);
      setCurrentSource(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, t('inventoryCoverage.saveSourceFailed'));
    }
  };

  const handleSaveGoal = async (formData) => {
    const payload = {
      ...formData,
      org_unit: formData.org_unit ? Number(formData.org_unit) : null,
      target_coverage_pct: formData.target_coverage_pct ? Number(formData.target_coverage_pct) : null,
      min_quality_tier: formData.min_quality_tier ? Number(formData.min_quality_tier) : null,
      target_year: formData.target_year ? Number(formData.target_year) : null,
      sbti_target: formData.sbti_target ? Number(formData.sbti_target) : null,
    };
    try {
      if (currentGoal) {
        await updateCoverageGoal(currentGoal.id, payload, token);
        notify({ message: t('inventoryCoverage.goalUpdated'), type: 'success' });
      } else {
        await createCoverageGoal(payload, token);
        notify({ message: t('inventoryCoverage.goalCreated'), type: 'success' });
      }
      setGoalOpen(false);
      setCurrentGoal(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, t('inventoryCoverage.saveGoalFailed'));
    }
  };

  const handleSaveAction = async (formData) => {
    const payload = {
      ...formData,
      source: formData.source ? Number(formData.source) : null,
      owner: formData.owner ? Number(formData.owner) : null,
      due_date: formData.due_date || null,
    };
    try {
      if (currentAction) {
        await updateCoverageAction(currentAction.id, payload, token);
        notify({ message: t('inventoryCoverage.actionUpdated'), type: 'success' });
      } else {
        await createCoverageAction(payload, token);
        notify({ message: t('inventoryCoverage.actionCreated'), type: 'success' });
      }
      setActionOpen(false);
      setCurrentAction(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, t('inventoryCoverage.saveActionFailed'));
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    const { kind, id } = deleteConfirm;
    try {
      if (kind === 'source') await deleteInventorySource(id, token);
      else if (kind === 'goal') await deleteCoverageGoal(id, token);
      else if (kind === 'action') await deleteCoverageAction(id, token);
      notify({ message: t('inventoryCoverage.recordDeleted'), type: 'success' });
      setDeleteConfirm(null);
      await loadAll();
      if (kind === 'source') await loadPeriodScoped(selectedPeriod);
    } catch (err) {
      notifyFromError(err, t('inventoryCoverage.deleteFailed'));
    }
  };

  const handleSaveExclusion = async ({ excluded, reason, notes }) => {
    const sourceId = exclusionRow?.inventory_source_id;
    if (!sourceId) return;
    try {
      await setCoverageRowExclusion(sourceId, { excluded, reason, notes }, token);
      notify({
        message: excluded ? t('coverage.exclusionSaved') : t('coverage.exclusionCleared'),
        type: 'success',
      });
      setExclusionRow(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, t('coverage.exclusionFailed'));
    }
  };

  // ── Enum label maps (labels resolved here; the shared chip stays generic) ──

  const statusMap = useMemo(() => ({
    declared: { label: t('inventoryCoverage.statusDeclared'), color: 'info' },
    covered: { label: t('inventoryCoverage.statusCovered'), color: 'success' },
    excluded: { label: t('inventoryCoverage.statusExcluded'), color: 'warning' },
    draft: { label: t('coverageTargets.statusDraft'), color: 'warning' },
    active: { label: t('coverageTargets.statusActive'), color: 'success' },
    archived: { label: t('coverageTargets.statusArchived') },
    open: { label: t('coverageTargets.taskOpen'), color: 'info' },
    in_progress: { label: t('coverageTargets.taskInProgress'), color: 'primary' },
    done: { label: t('coverageTargets.taskDone'), color: 'success' },
    blocked: { label: t('coverageTargets.taskBlocked'), color: 'error' },
  }), [t]);

  const exclusionMap = useMemo(() => ({
    not_material: { label: t('coverage.exclusionNotMaterial') },
    insufficient_data: { label: t('coverage.exclusionInsufficient'), color: 'warning' },
    out_of_boundary: { label: t('coverage.exclusionOutOfBoundary'), color: 'info' },
    other: { label: t('coverage.exclusionOther'), color: 'secondary' },
  }), [t]);

  const completenessMap = useMemo(() => ({
    absolute: { label: t('inventoryCoverage.completenessAbsolute'), color: 'primary' },
    materiality_bounded: { label: t('inventoryCoverage.completenessMateriality'), color: 'secondary' },
  }), [t]);

  const actionTypeMap = useMemo(() => ({
    collect_data: { label: t('inventoryCoverage.actionTypeCollect'), color: 'info' },
    improve_quality: { label: t('inventoryCoverage.actionTypeImprove'), color: 'primary' },
    obtain_verification: { label: t('inventoryCoverage.actionTypeVerification'), color: 'success' },
    formalize_exclusion: { label: t('inventoryCoverage.actionTypeExclusion'), color: 'warning' },
  }), [t]);

  const activeMap = useMemo(() => ({
    true: { label: t('inventoryCoverage.activeYes'), color: 'success' },
    false: { label: t('inventoryCoverage.activeNo') },
  }), [t]);

  // ── Columns ──────────────────────────────────────────────────────────

  const idColumn = (headerName) => ({
    field: 'id',
    headerName,
    width: 70,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText>,
  });

  const actionButtons = (onEdit, onDelete, editLabel, deleteLabel) => ({
    field: 'actions',
    headerName: t('inventoryCoverage.colActions'),
    width: 100,
    sortable: false,
    renderCell: (params) => (
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <IconButton size="small" aria-label={editLabel} onClick={onEdit(params.row)}>
          <EditIcon fontSize="small" />
        </IconButton>
        <IconButton
          size="small"
          aria-label={deleteLabel}
          onClick={onDelete(params.row)}
          sx={{ color: 'error.main' }}
        >
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Box>
    ),
  });

  const sourceColumns = [
    idColumn(t('inventoryCoverage.colId')),
    {
      field: 'org_unit',
      headerName: t('inventoryCoverage.colOrgUnit'),
      flex: 1,
      minWidth: 120,
      valueGetter: (value, row) => row.org_unit_name || row.org_unit || '—',
    },
    { field: 'scope', headerName: t('inventoryCoverage.colScope'), width: 110, renderCell: (params) => <StatusChip value={String(params.value)} map={SCOPE_MAP} /> },
    {
      field: 'scope2_method',
      headerName: t('scope2MethodCol'),
      width: 150,
      renderCell: (params) => (
        Number(params.row.scope) === 2
          ? <Scope2MethodChip method={params.value} scope={2} />
          : '—'
      ),
    },
    {
      field: 'scope3_category',
      headerName: t('inventoryCoverage.colScope3Cat'),
      width: 110,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText>,
    },
    { field: 'source_name', headerName: t('inventoryCoverage.colSourceName'), flex: 1, minWidth: 160 },
    {
      field: 'description',
      headerName: t('inventoryCoverage.colDescription'),
      flex: 1,
      minWidth: 200,
      valueFormatter: (value) => value || '—',
    },
    {
      field: 'is_active',
      headerName: t('inventoryCoverage.colActive'),
      width: 100,
      renderCell: (params) => <StatusChip value={String(params.value)} map={activeMap} />,
    },
    ...(isAdmin
      ? [actionButtons(
          (row) => () => { setCurrentSource(row); setSourceOpen(true); },
          (row) => () => setDeleteConfirm({ kind: 'source', id: row.id }),
          t('inventoryCoverage.editSourceAria'),
          t('inventoryCoverage.deleteSourceAria'),
        )]
      : []),
  ];

  const statusColumns = [
    idColumn(t('inventoryCoverage.colId')),
    {
      field: 'source_name',
      headerName: t('inventoryCoverage.colSource'),
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.source_name || row.source || '—',
    },
    {
      field: 'reporting_period_name',
      headerName: t('inventoryCoverage.colPeriod'),
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.reporting_period_name || row.reporting_period || '—',
    },
    { field: 'status', headerName: t('inventoryCoverage.colStatus'), width: 120, renderCell: (params) => <StatusChip value={params.value} map={statusMap} /> },
    { field: 'data_quality_tier', headerName: t('inventoryCoverage.colTier'), width: 120, renderCell: (params) => <TierChip value={params.value} /> },
    { field: 'exclusion_reason', headerName: t('inventoryCoverage.colExclusion'), width: 150, renderCell: (params) => <StatusChip value={params.value} map={exclusionMap} fallbackLabel="—" /> },
    {
      field: 'linked_tables',
      headerName: t('inventoryCoverage.colLinkedTables'),
      width: 120,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <NumericText align="right">{Array.isArray(params.value) ? params.value.length : '—'}</NumericText>
      ),
    },
    { field: 'notes', headerName: t('inventoryCoverage.colNotes'), flex: 1, minWidth: 180, valueFormatter: (value) => value || '—' },
  ];

  const goalColumns = [
    idColumn(t('inventoryCoverage.colId')),
    {
      field: 'org_unit',
      headerName: t('inventoryCoverage.colOrgUnit'),
      flex: 1,
      minWidth: 120,
      valueGetter: (value, row) => row.org_unit_name || row.org_unit || '—',
    },
    { field: 'name', headerName: t('inventoryCoverage.colGoalName'), flex: 1, minWidth: 150 },
    { field: 'scope', headerName: t('inventoryCoverage.colScope'), width: 110, renderCell: (params) => <StatusChip value={String(params.value)} map={SCOPE_MAP} /> },
    {
      field: 'target_coverage_pct',
      headerName: t('inventoryCoverage.colTargetPct'),
      width: 110,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <NumericText align="right">
          {params.value == null ? '—' : formatPercent(params.value, { maximumFractionDigits: 1 })}
        </NumericText>
      ),
    },
    { field: 'min_quality_tier', headerName: t('inventoryCoverage.colMinTier'), width: 110, renderCell: (params) => <TierChip value={params.value} /> },
    { field: 'completeness_definition', headerName: t('inventoryCoverage.colCompleteness'), width: 180, renderCell: (params) => <StatusChip value={params.value} map={completenessMap} /> },
    {
      field: 'target_year',
      headerName: t('inventoryCoverage.colTargetYear'),
      width: 110,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText>,
    },
    { field: 'sbti_target', headerName: t('inventoryCoverage.colSbti'), width: 90, valueFormatter: (value) => value ?? '—' },
    { field: 'status', headerName: t('inventoryCoverage.colStatus'), width: 120, renderCell: (params) => <StatusChip value={params.value} map={statusMap} /> },
    ...(isAdmin
      ? [actionButtons(
          (row) => () => { setCurrentGoal(row); setGoalOpen(true); },
          (row) => () => setDeleteConfirm({ kind: 'goal', id: row.id }),
          t('inventoryCoverage.editGoalAria'),
          t('inventoryCoverage.deleteGoalAria'),
        )]
      : []),
  ];

  const actionColumns = [
    idColumn(t('inventoryCoverage.colId')),
    {
      field: 'source',
      headerName: t('inventoryCoverage.colSource'),
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.source_name || row.source || '—',
    },
    { field: 'action_type', headerName: t('inventoryCoverage.colActionType'), width: 170, renderCell: (params) => <StatusChip value={params.value} map={actionTypeMap} /> },
    { field: 'status', headerName: t('inventoryCoverage.colStatus'), width: 120, renderCell: (params) => <StatusChip value={params.value} map={statusMap} /> },
    { field: 'due_date', headerName: t('inventoryCoverage.colDueDate'), width: 120, valueFormatter: (value) => (value ? (formatDisplayDate(value) || '—') : '—') },
    {
      field: 'owner',
      headerName: t('inventoryCoverage.colOwner'),
      width: 120,
      valueGetter: (value, row) => row.owner_username || row.owner || '—',
    },
    { field: 'notes', headerName: t('inventoryCoverage.colNotes'), flex: 1, minWidth: 180, valueFormatter: (value) => value || '—' },
    ...(isAdmin
      ? [actionButtons(
          (row) => () => { setCurrentAction(row); setActionOpen(true); },
          (row) => () => setDeleteConfirm({ kind: 'action', id: row.id }),
          t('inventoryCoverage.editActionAria'),
          t('inventoryCoverage.deleteActionAria'),
        )]
      : []),
  ];

  // ── Derived rows (search filters, never a second reporter) ───────────

  const filterStreamRows = (board) => {
    const q = (streamSearch[board.id] || '').trim().toLowerCase();
    const rows = board.streams || [];
    if (!q) return rows;
    return rows.filter((row) => [row.campus, row.source_name, row.scope, reasonLabel(t, row.reason)]
      .filter((value) => value != null && value !== '')
      .some((value) => String(value).toLowerCase().includes(q)));
  };

  const filteredGoals = useMemo(() => {
    const rows = reconciliation?.goals || [];
    const q = goalSearch.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) => [row.name, row.org_unit_name, row.scope]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(q)));
  }, [reconciliation, goalSearch]);

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <PageContainer>
      <PageHeader
        title={t('inventoryCoverage.pageTitle')}
        description={t('inventoryCoverage.pageDescription')}
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadAll} size="small" aria-label={t('inventoryCoverage.refreshAria')}>
              <RefreshIcon />
            </IconButton>
          </Stack>
        }
      />

      {coverage != null && typeof coverage === 'object' && (
        <Alert
          severity="warning"
          sx={{ mb: 2 }}
          action={(
            <Button color="inherit" size="small" onClick={() => navigate('/carbon/onboarding')}>
              {t('chairman.openOnboarding')}
            </Button>
          )}
        >
          {t('chairman.notO1Footprint')}
        </Alert>
      )}

      <Typography variant="h6">{t('intake.streamsTitle')}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('intake.notComplete')}
      </Typography>
      {loading && streamPeriods.length === 0 && streams.length === 0 && (
        <LoadingSkeleton variant="table" />
      )}
      {streamError && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={(
            <Button color="inherit" size="small" onClick={loadAll}>
              {t('common:retry')}
            </Button>
          )}
        >
          {streamError}
        </Alert>
      )}
      <WorkflowCard
        icon={<FactCheckIcon />}
        title={t('intake.recordDiscovered')}
        description={t('intake.recordDiscoveredHint')}
        onClick={() => navigate('/carbon/onboarding/intake')}
      />
      {streamPeriods.length > 0 && (
        <Box sx={{ maxWidth: 420, my: 2 }}>
          <SearchSelect
            label={t('intake.periodList')}
            options={streamPeriods.map((board) => ({
              value: String(board.id),
              label: t('intake.streamsFor', {
                name: board.name,
                status: board.role === 'locked'
                  ? t('intake.periodLocked')
                  : board.role === 'closed'
                    ? t('intake.periodClosed')
                    : t('intake.periodOpen'),
              }),
            }))}
            value={streamPeriodId}
            onChange={(option) => setStreamPeriodId(option?.value ? String(option.value) : '')}
          />
        </Box>
      )}
      {(streamPeriods.length > 0 ? streamPeriods : [{ id: 'open', name: t('intake.periodOpen'), role: 'open', streams }]).map((board) => (
        <Box key={board.id} sx={{ mb: 2 }}>
          <Typography variant="subtitle1">
            {t('intake.streamsFor', {
              name: board.name,
              status: board.role === 'locked'
                ? t('intake.periodLocked')
                : board.role === 'closed'
                  ? t('intake.periodClosed')
                  : t('intake.periodOpen'),
            })}
          </Typography>
          {(board.streams || []).length === 0 && (
            <EmptyState title={t('intake.emptyTitle')} description={t('intake.notComplete')} />
          )}
          {(board.streams || []).length > 0 && (
            <FilteredDataGrid
              embedded
              title={board.name || t('intake.streamsTitle')}
              rows={filterStreamRows(board)}
              searchValue={streamSearch[board.id] || ''}
              onSearchChange={(value) => setStreamSearch((prev) => ({ ...prev, [board.id]: value }))}
              searchPlaceholder={t('inventoryCoverage.streamsSearch')}
              columns={[
                { field: 'campus', headerName: t('intake.campus'), flex: 1 },
                { field: 'source_name', headerName: t('intake.source'), flex: 1.2 },
                { field: 'scope', headerName: t('intake.scope'), width: 90 },
                {
                  field: 'status',
                  headerName: t('intake.status'),
                  width: 200,
                  valueGetter: (_value, row) => {
                    const key = {
                      entered: 'intake.statusEntered',
                      excluded: 'intake.statusExcluded',
                      missing: 'intake.statusMissing',
                      awaiting_factor: 'intake.statusAwaiting',
                    }[row?.status] || 'intake.statusMissing';
                    return t(key);
                  },
                },
                {
                  field: 'reason',
                  headerName: t('intake.reason'),
                  width: 170,
                  valueGetter: (_value, row) => reasonLabel(t, row?.reason),
                },
                {
                  field: 'inventory_kg',
                  headerName: t('intake.inventoryKg'),
                  width: 140,
                  align: 'right',
                  headerAlign: 'right',
                  renderCell: (params) => (
                    <NumericText align="right">
                      {params.value == null || params.value === '' ? t('intake.kgAbsent') : params.value}
                    </NumericText>
                  ),
                },
                {
                  field: 'submit',
                  headerName: t('coverage.entryAction'),
                  width: 150,
                  sortable: false,
                  renderCell: (params) => (
                    params.row?.inventory_source_id
                    && (params.row?.status === 'missing' || params.row?.status === 'awaiting_factor')
                  ) ? (
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => navigate(`/carbon/onboarding/intake?source=${params.row.inventory_source_id}`)}
                    >
                      {t('coverage.enterRow')}
                    </Button>
                  ) : null,
                },
                ...(isAdmin
                  ? [
                      {
                        field: 'exclusion',
                        headerName: t('coverage.exclusionAction'),
                        width: 160,
                        sortable: false,
                        renderCell: (params) => (
                          params.row?.inventory_source_id ? (
                            <Button
                              size="small"
                              variant={params.row?.status === 'excluded' ? 'outlined' : 'text'}
                              color={params.row?.status === 'excluded' ? 'inherit' : 'warning'}
                              onClick={() => setExclusionRow(params.row)}
                            >
                              {params.row?.status === 'excluded'
                                ? t('coverage.reincludeRow')
                                : t('coverage.excludeRow')}
                            </Button>
                          ) : null
                        ),
                      },
                    ]
                  : []),
              ]}
              loading={loading}
            />
          )}
        </Box>
      ))}

      {/* Reporting period selector */}
      <Box sx={{ maxWidth: 420, mb: 2 }}>
        <SearchSelect
          label={t('inventoryCoverage.reportingPeriod')}
          options={periods.map((p) => ({
            value: String(p.id),
            label: p.name || t('inventoryCoverage.periodFallback', { id: p.id }),
          }))}
          value={selectedPeriod}
          onChange={(option) => setSelectedPeriod(option?.value ? String(option.value) : '')}
          loading={loading && periods.length === 0}
          noOptionsText={t('inventoryCoverage.noPeriods')}
          clearable={false}
        />
      </Box>

      {/* Coverage summary header */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Card sx={{ flex: 1, minWidth: 180 }}>
          <CardContent>
            <Typography variant="overline" color="text.secondary">{t('intake.percentLabel')}</Typography>
            <ProgressBar
              value={coverage?.pct}
              tone={coverageTone(coverage?.pct)}
              label={formatPercent(coverage?.pct, { maximumFractionDigits: 1 })}
            />
          </CardContent>
        </Card>
        <StatCard title={t('inventoryCoverage.statCoveredTotal')} value={`${coverage?.covered ?? '—'} / ${coverage?.total ?? '—'}`} />
        <StatCard title={t('inventoryCoverage.statGaps')} value={coverage?.gaps_count ?? '—'} />
        <StatCard title={t('inventoryCoverage.statAvgTier')} value={coverage?.avg_quality_tier ?? '—'} />
        <StatCard title={t('inventoryCoverage.statCompleteness')} value={coverage?.completeness_definition ?? '—'} />
        <StatCard title={t('inventoryCoverage.statMaterialExclusions')} value={coverage?.material_exclusions_count ?? '—'} />
      </Box>

      {/* ── Reconciliation (read-only counts). Coverage is the only reporter. ── */}
      <Typography variant="h6">{t('coverage.reconciliationTitle')}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('coverage.reconciliationHint')}
      </Typography>
      {reconciliation ? (
        <>
          <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
            <StatCard title={t('coverage.required')} value={reconciliation.counts?.required ?? '—'} />
            <StatCard title={t('coverage.entered')} value={reconciliation.counts?.entered ?? '—'} />
            <StatCard title={t('coverage.excluded')} value={reconciliation.counts?.excluded ?? '—'} />
            <StatCard title={t('coverage.missing')} value={reconciliation.counts?.missing ?? '—'} />
          </Box>
          {(reconciliation.goals || []).length === 0 ? (
            <EmptyState title={t('coverage.noGoals')} description={t('coverage.noGoalsHint')} />
          ) : (
            <FilteredDataGrid
              embedded
              title={t('coverage.goalsTitle')}
              rows={filteredGoals}
              getRowId={(row) => row.goal_id}
              searchValue={goalSearch}
              onSearchChange={setGoalSearch}
              searchPlaceholder={t('inventoryCoverage.goalsSearch')}
              columns={[
                { field: 'name', headerName: t('coverage.goalName'), flex: 1 },
                { field: 'scope', headerName: t('intake.scope'), width: 90 },
                { field: 'org_unit_name', headerName: t('coverage.orgUnit'), flex: 1 },
                { field: 'required', headerName: t('coverage.required'), width: 100, align: 'right', headerAlign: 'right', renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText> },
                { field: 'entered', headerName: t('coverage.entered'), width: 100, align: 'right', headerAlign: 'right', renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText> },
                { field: 'excluded', headerName: t('coverage.excluded'), width: 100, align: 'right', headerAlign: 'right', renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText> },
                { field: 'missing', headerName: t('coverage.missing'), width: 100, align: 'right', headerAlign: 'right', renderCell: (params) => <NumericText align="right">{params.value ?? '—'}</NumericText> },
                {
                  field: 'target_coverage_pct',
                  headerName: t('coverage.declaredTarget'),
                  width: 140,
                  align: 'right',
                  headerAlign: 'right',
                  renderCell: (params) => (
                    <NumericText align="right">
                      {params.value == null ? '—' : formatPercent(params.value, { maximumFractionDigits: 1 })}
                    </NumericText>
                  ),
                },
              ]}
            />
          )}
        </>
      ) : loading ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <EmptyState title={t('coverage.noGoals')} description={t('coverage.noGoalsHint')} />
      )}

      {/* Section tabs */}
      <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Tab label={t('inventoryCoverage.tabSources')} />
        <Tab label={t('inventoryCoverage.tabStatuses')} />
        <Tab label={t('inventoryCoverage.tabGoals')} />
        <Tab label={t('inventoryCoverage.tabActions')} />
      </Tabs>

      {/* ── Sources ── */}
      {tab === 0 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => { setCurrentSource(null); setSourceOpen(true); }}>
                {t('inventoryCoverage.newSource')}
              </Button>
            )}
          </Box>
          <StandardDataGrid rows={sources} columns={sourceColumns} loading={loading} toolbar pageSize={25} />
        </Box>
      )}

      {/* ── Statuses (read-only) ── */}
      {tab === 1 && (
        <StandardDataGrid rows={statuses} columns={statusColumns} loading={loading} toolbar pageSize={25} />
      )}

      {/* ── Goals ── */}
      {tab === 2 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => { setCurrentGoal(null); setGoalOpen(true); }}>
                {t('inventoryCoverage.newGoal')}
              </Button>
            )}
          </Box>
          <StandardDataGrid rows={goals} columns={goalColumns} loading={loading} toolbar pageSize={25} />
        </Box>
      )}

      {/* ── Actions ── */}
      {tab === 3 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => { setCurrentAction(null); setActionOpen(true); }}>
                {t('inventoryCoverage.newAction')}
              </Button>
            )}
          </Box>
          <StandardDataGrid rows={actions} columns={actionColumns} loading={loading} toolbar pageSize={25} />
        </Box>
      )}

      {/* Create/Edit Dialogs (modal — design system primitive) */}
      <SourceDialog
        open={sourceOpen}
        source={currentSource}
        onSave={handleSaveSource}
        onClose={() => setSourceOpen(false)}
      />
      <GoalDialog
        open={goalOpen}
        goal={currentGoal}
        onSave={handleSaveGoal}
        onClose={() => setGoalOpen(false)}
      />
      <ActionDialog
        open={actionOpen}
        action={currentAction}
        sources={sources}
        sourcesLoading={loading}
        sourcesError={sourcesError}
        onSave={handleSaveAction}
        onClose={() => setActionOpen(false)}
      />
      <ExclusionDialog
        open={!!exclusionRow}
        row={exclusionRow}
        onSave={handleSaveExclusion}
        onClose={() => setExclusionRow(null)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title={t('inventoryCoverage.deleteTitle')}
        message={t('inventoryCoverage.deleteMessage')}
        confirmLabel={t('delete')}
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />
    </PageContainer>
  );
}
