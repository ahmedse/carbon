// src/pages/emissions/CalculationRulesPage.jsx
// Calculation Rules admin — CRUD + execute actions
// Pattern: EmissionFactorsPage style — MUI Table with icons, dialogs for create/edit
// All colours via theme.palette, zero hardcoded hex

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  Alert,
  TextField,
  MenuItem,
  Switch,
  FormControlLabel,
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
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import { FONT } from '../../theme/themeTokens';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import InboxIcon from '@mui/icons-material/Inbox';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchCalculationRules,
  createCalculationRule,
  updateCalculationRule,
  deleteCalculationRule,
  executeCalculationRule,
} from '../../api/emissions-extended';

// ── RuleTypeChip ────────────────────────────────────────────────────────

function RuleTypeChip({ value }) {
  const cfg = {
    direct:       { label: 'Direct',       palette: 'success' },
    unit_convert: { label: 'Unit Convert', palette: 'info' },
    formula:      { label: 'Formula',      palette: 'warning' },
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

// ── RulesDrawer ─────────────────────────────────────────────────────────

function RulesDrawer({ open, rule, tables = [], factors = [], onSave, onClose }) {
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
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 420, p: 3 }}>
        <Typography variant="h5" sx={{ mb: 3 }}>
          {rule ? 'Edit Rule' : 'Create Rule'}
        </Typography>
        <Stack spacing={2}>
          <TextField
            label="Name"
            name="name"
            value={form.name}
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
            rows={2}
            size="small"
          />
          <TextField
            label="Data Table"
            select
            name="data_table"
            value={form.data_table}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="">Select table…</MenuItem>
            {tables.map((t) => (
              <MenuItem key={t.id} value={t.id}>{t.name || t.label || t.id}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Activity Field"
            name="activity_field"
            value={form.activity_field}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="Field name or ID"
          />
          <TextField
            label="Emission Factor"
            select
            name="emission_factor"
            value={form.emission_factor}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="">Select factor…</MenuItem>
            {factors.map((f) => (
              <MenuItem key={f.id} value={f.id}>{f.name || f.id}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Rule Type"
            select
            name="rule_type"
            value={form.rule_type}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="direct">Direct</MenuItem>
            <MenuItem value="unit_convert">Unit Convert</MenuItem>
            <MenuItem value="formula">Formula</MenuItem>
          </TextField>
          {form.rule_type === 'unit_convert' && (
            <TextField
              label="Unit Conversion Factor"
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
            label="Active"
          />
          <FormControlLabel
            control={<Switch checked={form.auto_calculate} onChange={handleChange} name="auto_calculate" size="small" />}
            label="Auto-Calculate"
          />
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSubmit} sx={{ flex: 1 }}>
              {rule ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── ExecuteDialog ──────────────────────────────────────────────────────

function ExecuteDialog({ open, rule, onClose, onConfirm, loading }) {
  const [periodId, setPeriodId] = useState('');

  useEffect(() => {
    if (open) setPeriodId('');
  }, [open]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Execute Rule</DialogTitle>
      <DialogContent>
        <Typography sx={{ ...FONT.body, mb: 2 }}>
          Run rule: <strong>{rule?.name || rule?.id}</strong>?
        </Typography>
        <TextField
          label="Reporting Period ID (optional)"
          name="period_id"
          value={periodId}
          onChange={(e) => setPeriodId(e.target.value)}
          fullWidth
          size="small"
          placeholder="Leave blank to use active period"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>Cancel</Button>
        <Button
          onClick={() => onConfirm(rule, periodId)}
          variant="contained"
          color="success"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
        >
          {loading ? 'Running…' : 'Execute'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function CalculationRulesPage() {
  useDocumentTitle("Calculation Rules");
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
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const { notify, notifyFromError } = useNotification();
  const isAdmin = user?.is_superuser || user?.groups?.includes('admins_group');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const rulesData = await fetchCalculationRules(token);
      setRules(Array.isArray(rulesData) ? rulesData : rulesData?.results || []);
    } catch (err) {
      notifyFromError(err, 'Failed to load calculation rules');
      setError(err.message || 'Failed to load calculation rules');
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

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
      notifyFromError(err, 'Failed to save rule');
      setError(err.message || 'Failed to save rule');
    }
  };

  const handleDelete = async (ruleId) => {
    try {
      const result = await deleteCalculationRule(ruleId, token);
      if (result && result.archived) {
        notify({
          message: `Rule archived. ${result.audit_count || 0} audit records preserved.`,
          type: 'info',
        });
      } else {
        notify({ message: 'Rule deleted', type: 'success' });
      }
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete rule');
      setError(err.message || 'Failed to delete rule');
    }
  };

  const handleExecute = async (rule, periodId) => {
    setExecuting(true);
    try {
      const payload = periodId ? { reporting_period_id: periodId } : {};
      await executeCalculationRule(rule.id, payload, token);
      setExecuteOpen(false);
      setExecutingRule(null);
      setSnackbar({ open: true, message: `Rule "${rule.name || rule.id}" executed successfully`, severity: 'success' });
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Execution failed');
      setSnackbar({ open: true, message: err.message || 'Execution failed', severity: 'error' });
    } finally {
      setExecuting(false);
    }
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
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h2">
          Calculation Rules
        </Typography>
        <Stack direction="row" spacing={1}>
          <IconButton onClick={loadData} size="small">
            <RefreshIcon />
          </IconButton>
          {isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
              New Rule
            </Button>
          )}
        </Stack>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {(!rules || rules.length === 0) && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <InboxIcon sx={{ fontSize: '4rem', color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">No calculation rules found</Typography>
          <Typography variant="body2" color="text.disabled">
            {isAdmin ? 'Click "New Rule" to create one.' : 'Contact an administrator to add items.'}
          </Typography>
        </Box>
      )}

      {rules && rules.length > 0 && (
      /* Table */
      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: 'action.hover' }}>
            <TableRow>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>ID</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Name</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Data Table</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Activity Field</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Emission Factor</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Factor Code</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Rule Type</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Active</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Auto-Calc</TableCell>
              <TableCell sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Last Executed</TableCell>
              {isAdmin && <TableCell align="center" sx={{ ...FONT.bodySmall, fontWeight: 600 }}>Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {rules.map((rule) => (
                <TableRow key={rule.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  <TableCell sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{rule.id}</TableCell>
                  <TableCell sx={{ ...FONT.body, fontWeight: 500 }}>{rule.name}</TableCell>
                  <TableCell sx={{ ...FONT.body }}>{rule.data_table_name || rule.data_table || '—'}</TableCell>
                  <TableCell sx={{ ...FONT.body }}>{rule.activity_field_name || rule.activity_field || '—'}</TableCell>
                  <TableCell sx={{ ...FONT.body }}>{rule.emission_factor_name || rule.emission_factor || '—'}</TableCell>
                  <TableCell sx={{ ...FONT.body, fontFamily: 'monospace' }}>{rule.emission_factor_code || '—'}</TableCell>
                  <TableCell><RuleTypeChip value={rule.rule_type} /></TableCell>
                  <TableCell>
                    <Chip
                      label={rule.is_active ? 'Yes' : 'No'}
                      size="small"
                      color={rule.is_active ? 'success' : 'default'}
                      variant="outlined"
                      sx={{ height: 2.5, ...FONT.body }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={rule.auto_calculate ? 'Yes' : 'No'}
                      size="small"
                      color={rule.auto_calculate ? 'info' : 'default'}
                      variant="outlined"
                      sx={{ height: 2.5, ...FONT.body }}
                    />
                  </TableCell>
                  <TableCell sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>
                    {rule.last_executed_at ? new Date(rule.last_executed_at).toLocaleDateString() : '—'}
                  </TableCell>
                  {isAdmin && (
                    <TableCell align="center">
                      <IconButton size="small" onClick={() => handleEdit(rule)} title="Edit">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="success"
                        onClick={() => { setExecutingRule(rule); setExecuteOpen(true); }}
                        title="Execute Now"
                      >
                        <PlayArrowIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => setDeleteConfirm(rule.id)}
                        sx={{ color: 'error.main' }}
                        title="Delete"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>
      )}

      {/* Create/Edit Drawer */}
      <RulesDrawer
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
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Rule?</DialogTitle>
        <DialogContent>
          <Typography sx={{ ...FONT.body }}>This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button onClick={() => handleDelete(deleteConfirm)} variant="contained" color="error">
            Delete
          </Button>
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
