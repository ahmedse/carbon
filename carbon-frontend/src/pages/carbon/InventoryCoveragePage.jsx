// src/pages/carbon/InventoryCoveragePage.jsx
// Inventory Coverage admin — declared-universe completeness for GHG accounting (ADR-0020)
// Pattern: SBTiTargetsPage / BaseYearsPage — MUI Table + Drawer CRUD, zero hardcoded hex

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  Alert,
  TextField,
  MenuItem,
  CircularProgress,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stack,
  IconButton,
  Snackbar,
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

// ── SourceDrawer ───────────────────────────────────────────────────────

function SourceDrawer({ open, source, onSave, onClose }) {
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
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 440, p: 3 }}>
        <Typography variant="h5" sx={{ mb: 3 }}>
          {source ? 'Edit Source' : 'New Source'}
        </Typography>
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
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>Cancel</Button>
            <Button variant="contained" onClick={() => onSave(form)} sx={{ flex: 1 }}>
              {source ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── GoalDrawer ─────────────────────────────────────────────────────────

function GoalDrawer({ open, goal, onSave, onClose }) {
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
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 440, p: 3 }}>
        <Typography variant="h5" sx={{ mb: 3 }}>
          {goal ? 'Edit Goal' : 'New Goal'}
        </Typography>
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
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>Cancel</Button>
            <Button variant="contained" onClick={() => onSave(form)} sx={{ flex: 1 }}>
              {goal ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── ActionDrawer ───────────────────────────────────────────────────────

function ActionDrawer({ open, action, sources, onSave, onClose }) {
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
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 440, p: 3 }}>
        <Typography variant="h5" sx={{ mb: 3 }}>
          {action ? 'Edit Action' : 'New Action'}
        </Typography>
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
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>Cancel</Button>
            <Button variant="contained" onClick={() => onSave(form)} sx={{ flex: 1 }}>
              {action ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function InventoryCoveragePage() {
  useDocumentTitle('Inventory Coverage');
  const { user, token, availablePerspectives } = useAuth();

  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [coverage, setCoverage] = useState(null);
  const [sources, setSources] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [goals, setGoals] = useState([]);
  const [actions, setActions] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState(0);

  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);
  const [goalDrawerOpen, setGoalDrawerOpen] = useState(false);
  const [actionDrawerOpen, setActionDrawerOpen] = useState(false);
  const [currentSource, setCurrentSource] = useState(null);
  const [currentGoal, setCurrentGoal] = useState(null);
  const [currentAction, setCurrentAction] = useState(null);

  const [deleteConfirm, setDeleteConfirm] = useState(null); // { kind, id }
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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
      setError(err.message || 'Failed to load inventory coverage data');
    } finally {
      setLoading(false);
    }
  }, [token]);

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
      setError(err.message || 'Failed to load coverage');
    }
  }, [token]);

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
      if (currentSource) await updateInventorySource(currentSource.id, payload, token);
      else await createInventorySource(payload, token);
      setSourceDrawerOpen(false);
      setCurrentSource(null);
      setSnackbar({ open: true, message: 'Inventory source saved', severity: 'success' });
      await loadAll();
    } catch (err) {
      setError(err.message || 'Failed to save source');
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
      if (currentGoal) await updateCoverageGoal(currentGoal.id, payload, token);
      else await createCoverageGoal(payload, token);
      setGoalDrawerOpen(false);
      setCurrentGoal(null);
      setSnackbar({ open: true, message: 'Coverage goal saved', severity: 'success' });
      await loadAll();
    } catch (err) {
      setError(err.message || 'Failed to save goal');
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
      if (currentAction) await updateCoverageAction(currentAction.id, payload, token);
      else await createCoverageAction(payload, token);
      setActionDrawerOpen(false);
      setCurrentAction(null);
      setSnackbar({ open: true, message: 'Coverage action saved', severity: 'success' });
      await loadAll();
    } catch (err) {
      setError(err.message || 'Failed to save action');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    const { kind, id } = deleteConfirm;
    try {
      if (kind === 'source') await deleteInventorySource(id, token);
      else if (kind === 'goal') await deleteCoverageGoal(id, token);
      else if (kind === 'action') await deleteCoverageAction(id, token);
      setDeleteConfirm(null);
      setSnackbar({ open: true, message: 'Record deleted', severity: 'success' });
      await loadAll();
      if (kind === 'source') await loadPeriodScoped(selectedPeriod);
    } catch (err) {
      setError(err.message || 'Failed to delete record');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  // ── Loading state ────────────────────────────────────────────────────

  if (loading) {
    return (
      <PageContainer sx={{ alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </PageContainer>
    );
  }

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <PageContainer>
      <PageHeader
        title="Inventory Coverage"
        description="Declared-universe completeness for GHG accounting. Declare the emission sources you are accountable for, track per-period coverage status and PCAF data-quality tiers, maintain an exclusions register, and set coverage goals (ADR-0020)."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadAll} size="small" sx={{ mr: 0.5 }}>
              <RefreshIcon />
            </IconButton>
          </Stack>
        }
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

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
        <>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setCurrentSource(null); setSourceDrawerOpen(true); }}>
                New Source
              </Button>
            )}
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead sx={{ bgcolor: 'action.hover' }}>
                <TableRow>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>ID</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Org Unit</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Scope</TableCell>
                  <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Scope 3 Cat</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Source Name</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Description</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Active</TableCell>
                  {isAdmin && <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {sources.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 8 : 7} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                      No inventory sources found. Click "New Source" to declare one.
                    </TableCell>
                  </TableRow>
                ) : (
                  sources.map((s) => (
                    <TableRow key={s.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                      <TableCell sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{s.id}</TableCell>
                      <TableCell sx={{ ...FONT.body }}>{s.org_unit_name || s.org_unit || '—'}</TableCell>
                      <TableCell><ScopeChip value={s.scope} /></TableCell>
                      <TableCell align="center" sx={{ ...FONT.body }}>{s.scope3_category ?? '—'}</TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 500 }}>{s.source_name}</TableCell>
                      <TableCell sx={{ ...FONT.body, color: 'text.secondary' }}>{s.description || '—'}</TableCell>
                      <TableCell><ActiveChip value={s.is_active} /></TableCell>
                      {isAdmin && (
                        <TableCell align="center">
                          <IconButton size="small" onClick={() => { setCurrentSource(s); setSourceDrawerOpen(true); }} title="Edit">
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <IconButton size="small" onClick={() => setDeleteConfirm({ kind: 'source', id: s.id })} sx={{ color: 'error.main' }} title="Delete">
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {/* ── Statuses (read-only) ── */}
      {tab === 1 && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ bgcolor: 'action.hover' }}>
              <TableRow>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>ID</TableCell>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Source</TableCell>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Period</TableCell>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Status</TableCell>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Tier</TableCell>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Exclusion</TableCell>
                <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Linked Tables</TableCell>
                <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Notes</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {statuses.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                    No per-period statuses for the selected reporting period.
                  </TableCell>
                </TableRow>
              ) : (
                statuses.map((s) => (
                  <TableRow key={s.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                    <TableCell sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{s.id}</TableCell>
                    <TableCell sx={{ ...FONT.body, fontWeight: 500 }}>{s.source_name || s.source || '—'}</TableCell>
                    <TableCell sx={{ ...FONT.body }}>{s.reporting_period_name || s.reporting_period || '—'}</TableCell>
                    <TableCell><StatusChip value={s.status} /></TableCell>
                    <TableCell><TierChip value={s.data_quality_tier} /></TableCell>
                    <TableCell><ExclusionChip value={s.exclusion_reason} /></TableCell>
                    <TableCell align="center" sx={{ ...FONT.body }}>
                      {Array.isArray(s.linked_tables) ? s.linked_tables.length : '—'}
                    </TableCell>
                    <TableCell sx={{ ...FONT.body, color: 'text.secondary' }}>{s.notes || '—'}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ── Goals ── */}
      {tab === 2 && (
        <>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setCurrentGoal(null); setGoalDrawerOpen(true); }}>
                New Goal
              </Button>
            )}
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead sx={{ bgcolor: 'action.hover' }}>
                <TableRow>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>ID</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Org Unit</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Name</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Scope</TableCell>
                  <TableCell align="right" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Target %</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Min Tier</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Completeness</TableCell>
                  <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Target Year</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>SBTi</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Status</TableCell>
                  {isAdmin && <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {goals.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 11 : 10} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                      No coverage goals found. Click "New Goal" to define one.
                    </TableCell>
                  </TableRow>
                ) : (
                  goals.map((g) => (
                    <TableRow key={g.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                      <TableCell sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{g.id}</TableCell>
                      <TableCell sx={{ ...FONT.body }}>{g.org_unit_name || g.org_unit || '—'}</TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 500 }}>{g.name}</TableCell>
                      <TableCell><ScopeChip value={g.scope} /></TableCell>
                      <TableCell align="right" sx={{ ...FONT.body }}>{g.target_coverage_pct ?? '—'}%</TableCell>
                      <TableCell><TierChip value={g.min_quality_tier} /></TableCell>
                      <TableCell><CompletenessChip value={g.completeness_definition} /></TableCell>
                      <TableCell align="center" sx={{ ...FONT.body }}>{g.target_year ?? '—'}</TableCell>
                      <TableCell sx={{ ...FONT.body }}>{g.sbti_target ?? '—'}</TableCell>
                      <TableCell><StatusChip value={g.status} /></TableCell>
                      {isAdmin && (
                        <TableCell align="center">
                          <IconButton size="small" onClick={() => { setCurrentGoal(g); setGoalDrawerOpen(true); }} title="Edit">
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <IconButton size="small" onClick={() => setDeleteConfirm({ kind: 'goal', id: g.id })} sx={{ color: 'error.main' }} title="Delete">
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {/* ── Actions ── */}
      {tab === 3 && (
        <>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
            {isAdmin && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setCurrentAction(null); setActionDrawerOpen(true); }}>
                New Action
              </Button>
            )}
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead sx={{ bgcolor: 'action.hover' }}>
                <TableRow>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>ID</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Source</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Action Type</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Status</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Due Date</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Owner</TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Notes</TableCell>
                  {isAdmin && <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {actions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 8 : 7} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                      No coverage actions found. Click "New Action" to create a remediation item.
                    </TableCell>
                  </TableRow>
                ) : (
                  actions.map((a) => (
                    <TableRow key={a.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                      <TableCell sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{a.id}</TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 500 }}>{a.source_name || a.source || '—'}</TableCell>
                      <TableCell><ActionTypeChip value={a.action_type} /></TableCell>
                      <TableCell><StatusChip value={a.status} /></TableCell>
                      <TableCell sx={{ ...FONT.body }}>{fmtDate(a.due_date)}</TableCell>
                      <TableCell sx={{ ...FONT.body }}>{a.owner_username || a.owner || '—'}</TableCell>
                      <TableCell sx={{ ...FONT.body, color: 'text.secondary' }}>{a.notes || '—'}</TableCell>
                      {isAdmin && (
                        <TableCell align="center">
                          <IconButton size="small" onClick={() => { setCurrentAction(a); setActionDrawerOpen(true); }} title="Edit">
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <IconButton size="small" onClick={() => setDeleteConfirm({ kind: 'action', id: a.id })} sx={{ color: 'error.main' }} title="Delete">
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {/* Create/Edit Drawers */}
      <SourceDrawer
        open={sourceDrawerOpen}
        source={currentSource}
        onSave={handleSaveSource}
        onClose={() => setSourceDrawerOpen(false)}
      />
      <GoalDrawer
        open={goalDrawerOpen}
        goal={currentGoal}
        onSave={handleSaveGoal}
        onClose={() => setGoalDrawerOpen(false)}
      />
      <ActionDrawer
        open={actionDrawerOpen}
        action={currentAction}
        sources={sources}
        onSave={handleSaveAction}
        onClose={() => setActionDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Record?</DialogTitle>
        <DialogContent>
          <Typography sx={{ ...FONT.body }}>This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button onClick={handleDelete} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </PageContainer>
  );
}
