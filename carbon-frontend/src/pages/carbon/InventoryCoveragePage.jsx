// src/pages/carbon/InventoryCoveragePage.jsx
// Inventory Coverage admin — declared-universe completeness for GHG accounting (ADR-0020)
// Canonical shell: StandardDataGrid + SystemDialog + ConfirmDialog (see EmissionFactorsPage / GWPReferencePage)
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  TextField,
  MenuItem,
  Typography,
  Stack,
  IconButton,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  LinearProgress,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import { FONT } from '../../theme/themeTokens';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import StandardDataGrid from '../../components/StandardDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import PageHeader from '../../components/Page/PageHeader';
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
} from '../../api/emissions-extended';

// ── ScopeChip ──────────────────────────────────────────────────────────

function ScopeChip({ value }) {
  const key = String(value ?? '');
  const cfg = {
    '1':      { label: 'Scope 1',     color: 'error' },
    '2':      { label: 'Scope 2',     color: 'warning' },
    '3':      { label: 'Scope 3',     color: 'success' },
    '1+2':    { label: 'Scope 1+2',   color: 'info' },
    '1+2+3':  { label: 'Scope 1+2+3', color: 'primary' },
  };
  const meta = cfg[key] || { label: value ?? '—', color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── TierChip ───────────────────────────────────────────────────────────

function TierChip({ value }) {
  if (value == null) {
    return (
      <Typography component="span" sx={{ ...FONT.body, color: 'text.secondary' }}>—</Typography>
    );
  }
  const cfg = {
    1: { label: 'T1 Audited',   color: 'success' },
    2: { label: 'T2 Verified',  color: 'info' },
    3: { label: 'T3 Calculated', color: 'primary' },
    4: { label: 'T4 Estimated', color: 'warning' },
    5: { label: 'T5 Proxy',     color: 'error' },
  };
  const meta = cfg[value] || { label: String(value), color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── StatusChip (source status / goal status / action status) ───────────

function StatusChip({ value }) {
  const cfg = {
    declared:    { label: 'Declared',    color: 'info' },
    covered:     { label: 'Covered',     color: 'success' },
    excluded:    { label: 'Excluded',    color: 'warning' },
    draft:       { label: 'Draft',       color: 'warning' },
    active:      { label: 'Active',      color: 'success' },
    archived:    { label: 'Archived',    color: 'default' },
    open:        { label: 'Open',        color: 'info' },
    in_progress: { label: 'In Progress', color: 'primary' },
    done:        { label: 'Done',        color: 'success' },
    blocked:     { label: 'Blocked',     color: 'error' },
  };
  const meta = cfg[value] || { label: value, color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="filled"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── ExclusionChip ──────────────────────────────────────────────────────

function ExclusionChip({ value }) {
  if (!value) {
    return (
      <Typography component="span" sx={{ ...FONT.body, color: 'text.secondary' }}>—</Typography>
    );
  }
  const cfg = {
    not_material:      { label: 'Not Material',      color: 'default' },
    insufficient_data: { label: 'Insufficient Data', color: 'warning' },
    out_of_boundary:   { label: 'Outside Boundary',  color: 'info' },
    other:             { label: 'Other',             color: 'secondary' },
  };
  const meta = cfg[value] || { label: value, color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── CompletenessChip ───────────────────────────────────────────────────

function CompletenessChip({ value }) {
  const cfg = {
    absolute:            { label: 'Absolute',            color: 'primary' },
    materiality_bounded: { label: 'Materiality-Bounded', color: 'secondary' },
  };
  const meta = cfg[value] || { label: value ?? '—', color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── ActionTypeChip ─────────────────────────────────────────────────────

function ActionTypeChip({ value }) {
  const cfg = {
    collect_data:        { label: 'Collect Data',        color: 'info' },
    improve_quality:     { label: 'Improve Quality',     color: 'primary' },
    obtain_verification: { label: 'Obtain Verification', color: 'success' },
    formalize_exclusion: { label: 'Formalize Exclusion', color: 'warning' },
  };
  const meta = cfg[value] || { label: value, color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── ActiveChip ─────────────────────────────────────────────────────────

function ActiveChip({ value }) {
  return (
    <Chip
      label={value ? 'Active' : 'Inactive'}
      size="small"
      color={value ? 'success' : 'default'}
      variant="filled"
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── StatCard ───────────────────────────────────────────────────────────

function StatCard({ label, value, sub }) {
  return (
    <Card sx={{ flex: 1, minWidth: 150 }}>
      <CardContent>
        <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>{label}</Typography>
        <Typography sx={{ ...FONT.statValue, color: 'text.primary' }}>{value}</Typography>
        {sub && <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{sub}</Typography>}
      </CardContent>
    </Card>
  );
}

// ── CoverageBar ────────────────────────────────────────────────────────

function CoverageBar({ value }) {
  const pct = Number(value) || 0;
  let color = 'error';
  if (pct >= 100) color = 'success';
  else if (pct >= 60) color = 'info';
  else if (pct >= 30) color = 'warning';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 140 }}>
      <LinearProgress
        variant="determinate"
        value={Math.min(pct, 100)}
        color={color}
        sx={{ flex: 1, height: 0.75, borderRadius: 1 }}
      />
      <Typography variant="caption" sx={{ ...FONT.body, fontWeight: 600, minWidth: 40, textAlign: 'right' }}>
        {pct.toFixed(1)}%
      </Typography>
    </Box>
  );
}

// ── SourceDialog ───────────────────────────────────────────────────────

function SourceDialog({ open, source, onSave, onClose }) {
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
      title={source ? 'Edit Source' : 'New Source'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={() => onSave(form)}>
          {source ? 'Update' : 'Create'}
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
            label="Org Unit"
            name="org_unit"
            value={form.org_unit}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="Org unit ID"
          />
          <TextField
            label="Scope"
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
              label="Scope 3 Category"
              name="scope3_category"
              type="number"
              value={form.scope3_category}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ min: 1, max: 15 }}
              helperText="Category 1–15"
            />
          )}
          <TextField
            label="Source Name"
            name="source_name"
            value={form.source_name}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          />
          <TextField
            label="Description"
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
            label="Active"
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── GoalDialog ─────────────────────────────────────────────────────────

function GoalDialog({ open, goal, onSave, onClose }) {
  const [form, setForm] = useState({
    org_unit: '',
    name: '',
    scope: '1+2+3',
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
        org_unit: '', name: '', scope: '1+2+3', target_coverage_pct: '', min_quality_tier: '',
        completeness_definition: 'materiality_bounded', target_year: '', sbti_target: '', status: 'active',
      });
    }
  }, [goal, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <SystemDialog
      open={open}
      title={goal ? 'Edit Goal' : 'New Goal'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={() => onSave(form)}>
          {goal ? 'Update' : 'Create'}
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
          <TextField label="Org Unit" name="org_unit" value={form.org_unit} onChange={handleChange} fullWidth size="small" placeholder="Org unit ID" />
          <TextField label="Name" name="name" value={form.name} onChange={handleChange} fullWidth required size="small" />
          <TextField label="Scope" select name="scope" value={form.scope} onChange={handleChange} fullWidth size="small">
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
            <MenuItem value="1+2">Scope 1+2</MenuItem>
            <MenuItem value="1+2+3">Scope 1+2+3</MenuItem>
          </TextField>
          <TextField
            label="Target Coverage (%)"
            name="target_coverage_pct"
            type="number"
            value={form.target_coverage_pct}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ min: 0, max: 100, step: 0.01 }}
          />
          <TextField
            label="Min Quality Tier"
            select
            name="min_quality_tier"
            value={form.min_quality_tier}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value=""><em>None</em></MenuItem>
            <MenuItem value="1">Tier 1 — Audited</MenuItem>
            <MenuItem value="2">Tier 2 — Verified</MenuItem>
            <MenuItem value="3">Tier 3 — Calculated</MenuItem>
            <MenuItem value="4">Tier 4 — Estimated</MenuItem>
            <MenuItem value="5">Tier 5 — Proxy</MenuItem>
          </TextField>
          <TextField label="Completeness Definition" select name="completeness_definition" value={form.completeness_definition} onChange={handleChange} fullWidth size="small">
            <MenuItem value="absolute">Absolute</MenuItem>
            <MenuItem value="materiality_bounded">Materiality-Bounded</MenuItem>
          </TextField>
          <TextField
            label="Target Year"
            name="target_year"
            type="number"
            value={form.target_year}
            onChange={handleChange}
            fullWidth
            required
            size="small"
            inputProps={{ min: 2020, max: 2100 }}
          />
          <TextField label="SBTi Target" name="sbti_target" value={form.sbti_target} onChange={handleChange} fullWidth size="small" placeholder="SBTi target ID" />
          <TextField label="Status" select name="status" value={form.status} onChange={handleChange} fullWidth size="small">
            <MenuItem value="draft">Draft</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="archived">Archived</MenuItem>
          </TextField>
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── ActionDialog ───────────────────────────────────────────────────────

function ActionDialog({ open, action, sources, onSave, onClose }) {
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
        source: action.source ?? '',
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

  return (
    <SystemDialog
      open={open}
      title={action ? 'Edit Action' : 'New Action'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={() => onSave(form)}>
          {action ? 'Update' : 'Create'}
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
          <TextField label="Source" select name="source" value={form.source} onChange={handleChange} fullWidth required size="small">
            {(sources || []).map((s) => (
              <MenuItem key={s.id} value={s.id}>{s.source_name || `Source ${s.id}`}</MenuItem>
            ))}
          </TextField>
          <TextField label="Action Type" select name="action_type" value={form.action_type} onChange={handleChange} fullWidth size="small">
            <MenuItem value="collect_data">Collect Data</MenuItem>
            <MenuItem value="improve_quality">Improve Data Quality</MenuItem>
            <MenuItem value="obtain_verification">Obtain Verification</MenuItem>
            <MenuItem value="formalize_exclusion">Formalize Exclusion</MenuItem>
          </TextField>
          <TextField label="Status" select name="status" value={form.status} onChange={handleChange} fullWidth size="small">
            <MenuItem value="open">Open</MenuItem>
            <MenuItem value="in_progress">In Progress</MenuItem>
            <MenuItem value="done">Done</MenuItem>
            <MenuItem value="blocked">Blocked</MenuItem>
          </TextField>
          <TextField
            label="Due Date"
            name="due_date"
            type="date"
            value={form.due_date}
            onChange={handleChange}
            fullWidth
            size="small"
            InputLabelProps={{ shrink: true }}
          />
          <TextField label="Owner" name="owner" value={form.owner} onChange={handleChange} fullWidth size="small" placeholder="User ID" />
          <TextField label="Notes" name="notes" value={form.notes} onChange={handleChange} fullWidth multiline rows={3} size="small" />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function InventoryCoveragePage() {
  useDocumentTitle('Inventory Coverage');
  const { user, token, availablePerspectives } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [coverage, setCoverage] = useState(null);
  const [sources, setSources] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [goals, setGoals] = useState([]);
  const [actions, setActions] = useState([]);

  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);

  const [sourceOpen, setSourceOpen] = useState(false);
  const [goalOpen, setGoalOpen] = useState(false);
  const [actionOpen, setActionOpen] = useState(false);
  const [currentSource, setCurrentSource] = useState(null);
  const [currentGoal, setCurrentGoal] = useState(null);
  const [currentAction, setCurrentAction] = useState(null);

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
    } catch (err) {
      notifyFromError(err, 'Failed to load inventory coverage data');
      setPeriods([]);
      setSources([]);
      setGoals([]);
      setActions([]);
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Auto-select the first period once periods are available.
  useEffect(() => {
    if (periods.length > 0 && !selectedPeriod) {
      setSelectedPeriod(periods[0].id);
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
      notifyFromError(err, 'Failed to load coverage');
    }
  }, [token, notifyFromError]);

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
        notify({ message: 'Inventory source updated', type: 'success' });
      } else {
        await createInventorySource(payload, token);
        notify({ message: 'Inventory source created', type: 'success' });
      }
      setSourceOpen(false);
      setCurrentSource(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, 'Failed to save source');
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
        notify({ message: 'Coverage goal updated', type: 'success' });
      } else {
        await createCoverageGoal(payload, token);
        notify({ message: 'Coverage goal created', type: 'success' });
      }
      setGoalOpen(false);
      setCurrentGoal(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, 'Failed to save goal');
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
        notify({ message: 'Coverage action updated', type: 'success' });
      } else {
        await createCoverageAction(payload, token);
        notify({ message: 'Coverage action created', type: 'success' });
      }
      setActionOpen(false);
      setCurrentAction(null);
      await loadAll();
    } catch (err) {
      notifyFromError(err, 'Failed to save action');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    const { kind, id } = deleteConfirm;
    try {
      if (kind === 'source') await deleteInventorySource(id, token);
      else if (kind === 'goal') await deleteCoverageGoal(id, token);
      else if (kind === 'action') await deleteCoverageAction(id, token);
      notify({ message: 'Record deleted', type: 'success' });
      setDeleteConfirm(null);
      await loadAll();
      if (kind === 'source') await loadPeriodScoped(selectedPeriod);
    } catch (err) {
      notifyFromError(err, 'Failed to delete record');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  // ── Columns ──────────────────────────────────────────────────────────

  const sourceColumns = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'org_unit',
      headerName: 'Org Unit',
      flex: 1,
      minWidth: 120,
      valueGetter: (value, row) => row.org_unit_name || row.org_unit || '—',
    },
    { field: 'scope', headerName: 'Scope', width: 110, renderCell: (params) => <ScopeChip value={params.value} /> },
    {
      field: 'scope3_category',
      headerName: 'Scope 3 Cat',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => value ?? '—',
    },
    { field: 'source_name', headerName: 'Source Name', flex: 1, minWidth: 160 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1,
      minWidth: 200,
      valueFormatter: (value) => value || '—',
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 100,
      renderCell: (params) => <ActiveChip value={params.value} />,
    },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 100,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => { setCurrentSource(params.row); setSourceOpen(true); }}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm({ kind: 'source', id: params.row.id })}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            ),
          },
        ]
      : []),
  ];

  const statusColumns = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'source_name',
      headerName: 'Source',
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.source_name || row.source || '—',
    },
    {
      field: 'reporting_period_name',
      headerName: 'Period',
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.reporting_period_name || row.reporting_period || '—',
    },
    { field: 'status', headerName: 'Status', width: 120, renderCell: (params) => <StatusChip value={params.value} /> },
    { field: 'data_quality_tier', headerName: 'Tier', width: 120, renderCell: (params) => <TierChip value={params.value} /> },
    { field: 'exclusion_reason', headerName: 'Exclusion', width: 150, renderCell: (params) => <ExclusionChip value={params.value} /> },
    {
      field: 'linked_tables',
      headerName: 'Linked Tables',
      width: 120,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => (Array.isArray(value) ? value.length : '—'),
    },
    { field: 'notes', headerName: 'Notes', flex: 1, minWidth: 180, valueFormatter: (value) => value || '—' },
  ];

  const goalColumns = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'org_unit',
      headerName: 'Org Unit',
      flex: 1,
      minWidth: 120,
      valueGetter: (value, row) => row.org_unit_name || row.org_unit || '—',
    },
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 150 },
    { field: 'scope', headerName: 'Scope', width: 110, renderCell: (params) => <ScopeChip value={params.value} /> },
    {
      field: 'target_coverage_pct',
      headerName: 'Target %',
      width: 100,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (value, row) => (row.target_coverage_pct != null ? `${row.target_coverage_pct}%` : '—'),
    },
    { field: 'min_quality_tier', headerName: 'Min Tier', width: 110, renderCell: (params) => <TierChip value={params.value} /> },
    { field: 'completeness_definition', headerName: 'Completeness', width: 180, renderCell: (params) => <CompletenessChip value={params.value} /> },
    {
      field: 'target_year',
      headerName: 'Target Year',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => value ?? '—',
    },
    { field: 'sbti_target', headerName: 'SBTi', width: 90, valueFormatter: (value) => value ?? '—' },
    { field: 'status', headerName: 'Status', width: 120, renderCell: (params) => <StatusChip value={params.value} /> },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 100,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => { setCurrentGoal(params.row); setGoalOpen(true); }}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm({ kind: 'goal', id: params.row.id })}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            ),
          },
        ]
      : []),
  ];

  const actionColumns = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'source',
      headerName: 'Source',
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.source_name || row.source || '—',
    },
    { field: 'action_type', headerName: 'Action Type', width: 170, renderCell: (params) => <ActionTypeChip value={params.value} /> },
    { field: 'status', headerName: 'Status', width: 120, renderCell: (params) => <StatusChip value={params.value} /> },
    { field: 'due_date', headerName: 'Due Date', width: 120, valueFormatter: (value) => fmtDate(value) },
    {
      field: 'owner',
      headerName: 'Owner',
      width: 120,
      valueGetter: (value, row) => row.owner_username || row.owner || '—',
    },
    { field: 'notes', headerName: 'Notes', flex: 1, minWidth: 180, valueFormatter: (value) => value || '—' },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 100,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => { setCurrentAction(params.row); setActionOpen(true); }}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm({ kind: 'action', id: params.row.id })}
                  sx={{ color: 'error.main' }}
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
    <PageContainer>
      <PageHeader
        title="Inventory Coverage"
        description="Declared-universe completeness for GHG accounting. Declare the emission sources you are accountable for, track per-period coverage status and PCAF data-quality tiers, maintain an exclusions register, and set coverage goals (ADR-0020)."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadAll} size="small" aria-label="Refresh coverage">
              <RefreshIcon />
            </IconButton>
          </Stack>
        }
      />

      {/* Reporting period selector */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <TextField
          label="Reporting Period"
          select
          value={selectedPeriod ?? ''}
          onChange={(e) => setSelectedPeriod(e.target.value)}
          size="small"
          sx={{ minWidth: 260 }}
        >
          {periods.length === 0 ? (
            <MenuItem value="">No periods available</MenuItem>
          ) : (
            periods.map((p) => (
              <MenuItem key={p.id} value={p.id}>{p.name || `Period ${p.id}`}</MenuItem>
            ))
          )}
        </TextField>
      </Box>

      {/* Coverage summary header */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Card sx={{ flex: 1, minWidth: 180 }}>
          <CardContent>
            <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>Coverage</Typography>
            <CoverageBar value={coverage?.pct} />
          </CardContent>
        </Card>
        <StatCard label="Covered / Total" value={`${coverage?.covered ?? '—'} / ${coverage?.total ?? '—'}`} />
        <StatCard label="Gaps" value={coverage?.gaps_count ?? '—'} />
        <StatCard label="Avg Quality Tier" value={coverage?.avg_quality_tier ?? '—'} />
        <StatCard label="Completeness" value={coverage?.completeness_definition ?? '—'} />
        <StatCard label="Material Exclusions" value={coverage?.material_exclusions_count ?? '—'} />
      </Box>

      {/* Section tabs */}
      <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Tab label="Sources" sx={{ ...FONT.tab }} />
        <Tab label="Statuses" sx={{ ...FONT.tab }} />
        <Tab label="Goals" sx={{ ...FONT.tab }} />
        <Tab label="Actions" sx={{ ...FONT.tab }} />
      </Tabs>

      {/* ── Sources ── */}
      {tab === 0 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => { setCurrentSource(null); setSourceOpen(true); }}>
                New Source
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
                New Goal
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
                New Action
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
        onSave={handleSaveAction}
        onClose={() => setActionOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Record?"
        message="This action cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />
    </PageContainer>
  );
}
