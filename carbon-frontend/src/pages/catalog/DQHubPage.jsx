// src/pages/catalog/DQHubPage.jsx
// Unified DQ Management Hub: Dashboard, Rules CRUD, Profiles, Freshness & Schema
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box, Tabs, Tab, Card, CardContent, Typography, Button, Chip, CircularProgress,
  Alert, Stack, IconButton, Tooltip, Grid, Dialog, DialogActions, DialogContent,
  DialogTitle, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, TextField,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import HistoryIcon from '@mui/icons-material/History';
import AssessmentIcon from '@mui/icons-material/Assessment';
import RuleIcon from '@mui/icons-material/Rule';
import StorageIcon from '@mui/icons-material/Storage';
import TimelineIcon from '@mui/icons-material/Timeline';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  getOrgDQMetrics, getDQResults, listDQRules, createDQRule, updateDQRule,
  deleteDQRule, executeDQRule, getDQRuleHistory, getTableProfiles,
  getFreshnessChecks, getSchemaSnapshots, getSchemaChanges,
} from '../../api/dq';
import { fetchAssetProfiles } from '../../api/catalog';
import DQRuleDialog from './tabs/DQRuleDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

// ─── Constants ───────────────────────────────────────────────────────────────

const RULE_TYPE_LABELS = {
  not_null: 'Not Null', unique: 'Unique', allowed_values: 'Allowed Values',
  range: 'Range', regex: 'Regex', reference_integrity: 'Reference Integrity',
  threshold: 'Threshold', nl_check: 'NL Check',
};

const SEVERITY_COLORS = { error: 'error', warn: 'warning', info: 'info', critical: 'error' };

const TABS = [
  { label: 'Dashboard', icon: <AssessmentIcon /> },
  { label: 'Rules', icon: <RuleIcon /> },
  { label: 'Profiles', icon: <StorageIcon /> },
  { label: 'Freshness & Schema', icon: <TimelineIcon /> },
];

function unwrapResults(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  return [];
}

function getQualityStatus(score) {
  if (score >= 95) return { label: 'Excellent', color: '#16a34a', icon: <CheckCircleIcon /> };
  if (score >= 80) return { label: 'Good', color: '#0288d1', icon: <CheckCircleIcon /> };
  if (score >= 60) return { label: 'Fair', color: '#f59e0b', icon: <WarningIcon /> };
  return { label: 'Needs Improvement', color: '#d32f2f', icon: <ErrorIcon /> };
}

// ─── MetricCard ──────────────────────────────────────────────────────────────

function MetricCard({ label, value, suffix, status, color }) {
  return (
    <Card sx={{ height: '100%', borderRadius: 2, boxShadow: 'none', border: '1px solid', borderColor: 'divider' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>{label}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1 }}>
          <Typography variant="h4" fontWeight={700} color="text.primary">{value}</Typography>
          {suffix && <Typography variant="subtitle2" color="text.secondary">{suffix}</Typography>}
        </Box>
        {status && (
          <Chip label={status} size="small" sx={{ mt: 2, bgcolor: `${color}20`, color, fontWeight: 600 }} />
        )}
      </CardContent>
    </Card>
  );
}

// ─── History Dialog ──────────────────────────────────────────────────────────

function HistoryDialog({ open, onClose, rule, history, loading }) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Execution History for {rule?.name || 'Rule'}</DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
        ) : !history || history.length === 0 ? (
          <Alert severity="info">No execution history available for this rule.</Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined" sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Executed At</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Failed Rows</TableCell>
                  <TableCell>Score</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {history.map((item) => (
                  <TableRow key={item.id || `${item.executed_at}-${item.rule}`}>
                    <TableCell>{item.executed_at ? new Date(item.executed_at).toLocaleString() : '—'}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        icon={item.passed ? <CheckCircleIcon /> : <ErrorIcon />}
                        label={item.passed ? 'Passed' : 'Failed'}
                        color={item.passed ? 'success' : 'error'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{item.failed_count ?? item.failed_rows ?? '—'}</TableCell>
                    <TableCell>{item.score != null ? `${item.score}%` : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Close</Button></DialogActions>
    </Dialog>
  );
}

// ─── Column Schema Dialog ────────────────────────────────────────────────────

function SchemaDialog({ open, onClose, snapshot }) {
  if (!snapshot) return null;
  const cols = snapshot.column_schema || {};
  const entries = Object.entries(cols);
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Schema Snapshot — {snapshot.table_name || snapshot.data_table}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Snapshot at: {snapshot.snapshot_at ? new Date(snapshot.snapshot_at).toLocaleString() : '—'}
          &nbsp;| Rows: {snapshot.row_count ?? '—'} &nbsp;| Columns: {entries.length}
        </Typography>
        {entries.length === 0 ? (
          <Alert severity="info">No column schema data.</Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined" sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Column</TableCell>
                  <TableCell>Type</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {entries.map(([col, def]) => (
                  <TableRow key={col}>
                    <TableCell sx={{ fontWeight: 600 }}>{col}</TableCell>
                    <TableCell>{typeof def === 'object' ? def.type || JSON.stringify(def) : String(def)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Close</Button></DialogActions>
    </Dialog>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function DQHubPage() {
  useDocumentTitle('DQ Hub');
  const { token } = useAuth();
  const { notify } = useNotification();

  // Tab state
  const [tab, setTab] = useState(0);

  // Dashboard state
  const [metrics, setMetrics] = useState(null);
  const [results, setResults] = useState([]);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState(null);

  // Rules state
  const [rules, setRules] = useState([]);
  const [tables, setTables] = useState([]);
  const [rulesLoading, setRulesLoading] = useState(true);
  const [rulesError, setRulesError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [executingIds, setExecutingIds] = useState([]);
  const [bulkExecuting, setBulkExecuting] = useState(false);
  const [selectedRuleIds, setSelectedRuleIds] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRule, setHistoryRule] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Profiles state
  const [profiles, setProfiles] = useState([]);
  const [profilesLoading, setProfilesLoading] = useState(false);

  // Freshness/Schema state
  const [freshness, setFreshness] = useState([]);
  const [schemaSnapshots, setSchemaSnapshots] = useState([]);
  const [schemaChanges, setSchemaChanges] = useState([]);
  const [freshnessLoading, setFreshnessLoading] = useState(false);
  const [schemaDialog, setSchemaDialog] = useState(null);

  const tableMap = useMemo(
    () => tables.reduce((acc, t) => ({ ...acc, [t.data_table]: t.title || t.name || `Table #${t.data_table}` }), {}),
    [tables],
  );

  // ─── Data Loaders ────────────────────────────────────────────────────────

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      const [m, r] = await Promise.all([
        getOrgDQMetrics(token),
        getDQResults({ limit: 100, ordering: '-executed_at' }, token),
      ]);
      setMetrics(m || null);
      setResults(unwrapResults(r));
    } catch (err) {
      setDashboardError(err.message || 'Failed to load dashboard');
    } finally {
      setDashboardLoading(false);
    }
  }, [token]);

  const loadRules = useCallback(async () => {
    setRulesLoading(true);
    setRulesError(null);
    try {
      const data = await listDQRules(token);
      setRules(unwrapResults(data));
    } catch (err) {
      setRulesError(err.message || 'Unable to load rules');
    } finally {
      setRulesLoading(false);
    }
  }, [token]);

  const loadTables = useCallback(async () => {
    try {
      const assets = await fetchAssetProfiles(token);
      const profiles = unwrapResults(assets).filter((a) => a.data_table != null && !a.data_field);
      setTables(profiles);
    } catch { /* non-critical */ }
  }, [token]);

  const loadProfiles = useCallback(async () => {
    setProfilesLoading(true);
    try {
      const data = await getTableProfiles({}, token);
      setProfiles(unwrapResults(data));
    } catch (err) {
      notify({ message: err.message || 'Failed to load profiles', type: 'error' });
    } finally {
      setProfilesLoading(false);
    }
  }, [token, notify]);

  const loadFreshnessSchema = useCallback(async () => {
    setFreshnessLoading(true);
    try {
      const [f, ss, sc] = await Promise.all([
        getFreshnessChecks({}, token),
        getSchemaSnapshots({}, token),
        getSchemaChanges({}, token),
      ]);
      setFreshness(unwrapResults(f));
      setSchemaSnapshots(unwrapResults(ss));
      setSchemaChanges(unwrapResults(sc));
    } catch (err) {
      notify({ message: err.message || 'Failed to load freshness/schema data', type: 'error' });
    } finally {
      setFreshnessLoading(false);
    }
  }, [token, notify]);

  // ─── Effects ─────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!token) return;
    loadDashboard();
    loadRules();
    loadTables();
  }, [token, loadDashboard, loadRules, loadTables]);

  useEffect(() => {
    if (!token || tab !== 2) return;
    if (profiles.length === 0) loadProfiles();
  }, [tab, token, profiles.length, loadProfiles]);

  useEffect(() => {
    if (!token || tab !== 3) return;
    if (freshness.length === 0) loadFreshnessSchema();
  }, [tab, token, freshness.length, loadFreshnessSchema]);

  // ─── Rule CRUD Handlers ──────────────────────────────────────────────────

  const handleOpenDialog = (rule = null) => {
    setEditingRule(rule);
    setDialogOpen(true);
  };

  const handleSaveRule = async (payload) => {
    if (editingRule) {
      await updateDQRule(token, editingRule.id, payload);
      notify({ message: 'DQ rule updated', type: 'success' });
    } else {
      await createDQRule(token, payload);
      notify({ message: 'DQ rule created', type: 'success' });
    }
    setDialogOpen(false);
    setEditingRule(null);
    loadRules();
  };

  const handleDeleteRule = async (rule) => {
    if (!window.confirm(`Delete rule "${rule.name || 'DQ rule'}"?`)) return;
    try {
      await deleteDQRule(token, rule.id);
      notify({ message: 'Rule deleted', type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Delete failed', type: 'error' });
    }
  };

  const handleExecuteRule = async (rule) => {
    if (!rule?.id) return;
    setExecutingIds((prev) => [...prev, rule.id]);
    try {
      await executeDQRule(token, rule.id);
      notify({ message: 'Rule executed', type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Execution failed', type: 'error' });
    } finally {
      setExecutingIds((prev) => prev.filter((id) => id !== rule.id));
    }
  };

  const handleBulkExecute = async () => {
    setBulkExecuting(true);
    try {
      // Use apiFetch directly for bulk-execute (POST /dq/rules/bulk-execute/)
      const { apiFetch } = await import('../../api/api');
      const res = await apiFetch('dq/rules/bulk-execute/', { method: 'POST', token, body: { rule_ids: selectedRuleIds } });
      notify({ message: `Bulk executed: ${res.passed}/${res.total} passed`, type: 'success' });
      setSelectedRuleIds([]);
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Bulk execution failed', type: 'error' });
    } finally {
      setBulkExecuting(false);
    }
  };

  const openHistory = async (rule) => {
    setHistoryRule(rule);
    setHistoryLoading(true);
    setHistoryOpen(true);
    try {
      const data = await getDQRuleHistory(token, rule.id);
      setHistoryItems(unwrapResults(data));
    } catch {
      setHistoryItems([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  // ─── DataGrid Columns ────────────────────────────────────────────────────

  const resultColumns = useMemo(() => [
    { field: 'rule_name', headerName: 'Rule', flex: 1.5, minWidth: 180,
      renderCell: (p) => <Typography variant="body2" fontWeight={600}>{p.value || '—'}</Typography> },
    { field: 'passed', headerName: 'Status', width: 120,
      renderCell: (p) => (
        <Chip size="small" icon={p.value ? <CheckCircleIcon /> : <ErrorIcon />}
          label={p.value ? 'Passed' : 'Failed'}
          color={p.value ? 'success' : 'error'} variant="outlined" />
      ) },
    { field: 'checked_count', headerName: 'Checked', width: 90, type: 'number' },
    { field: 'failed_count', headerName: 'Failed', width: 90, type: 'number' },
    { field: 'score', headerName: 'Score', width: 90, type: 'number',
      renderCell: (p) => <Typography>{p.value != null ? `${p.value}%` : '—'}</Typography> },
    { field: 'executed_at', headerName: 'Executed At', width: 180,
      renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '—' },
  ], []);

  const ruleColumns = useMemo(() => [
    { field: 'name', headerName: 'Rule Name', flex: 1.5, minWidth: 200,
      renderCell: (p) => <Typography variant="body2" fontWeight={600}>{p.value || '—'}</Typography> },
    { field: 'rule_type', headerName: 'Type', width: 130,
      renderCell: (p) => <Chip label={RULE_TYPE_LABELS[p.value] || p.value} size="small" /> },
    { field: 'severity', headerName: 'Severity', width: 100,
      renderCell: (p) => <Chip label={p.value} size="small" color={SEVERITY_COLORS[p.value] || 'default'} /> },
    { field: 'rule_level', headerName: 'Level', width: 130,
      renderCell: (p) => {
        const labels = { field_validation: 'Field', business_rule: 'Business', relation_integrity: 'Relation' };
        return <Chip label={labels[p.value] || p.value} size="small" variant="outlined" />;
      } },
    { field: 'data_table_name', headerName: 'Table', width: 180,
      renderCell: (p) => {
        // data_table_name comes from the first field_assignment
        const assn = p.row?.field_assignments?.[0];
        return <Typography variant="body2">{p.value || assn?.table_name || tableMap[assn?.data_table] || '—'}</Typography>;
      } },
    { field: 'is_active', headerName: 'Active', width: 80, type: 'boolean' },
    {
      field: 'actions', headerName: 'Actions', width: 200, sortable: false, filterable: false,
      renderCell: (p) => (
        <Stack direction="row" spacing={0.5}>
          <Tooltip title="Execute"><IconButton size="small" onClick={() => handleExecuteRule(p.row)} disabled={executingIds.includes(p.row.id)}><PlayArrowIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="History"><IconButton size="small" onClick={() => openHistory(p.row)}><HistoryIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Edit"><IconButton size="small" onClick={() => handleOpenDialog(p.row)}><EditIcon fontSize="small" /></IconButton></Tooltip>
          <Tooltip title="Delete"><IconButton size="small" color="error" onClick={() => handleDeleteRule(p.row)}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
        </Stack>
      ),
    },
  ], [executingIds, tableMap]);

  const profileColumns = useMemo(() => [
    { field: 'table_name', headerName: 'Table', flex: 1.5, minWidth: 200,
      renderCell: (p) => <Typography variant="body2" fontWeight={600}>{p.value || '—'}</Typography> },
    { field: 'row_count', headerName: 'Row Count', width: 110, type: 'number' },
    { field: 'column_count', headerName: 'Columns', width: 90, type: 'number' },
    { field: 'null_pct', headerName: 'Null %', width: 90, type: 'number',
      renderCell: (p) => <Typography>{p.value != null ? `${Number(p.value).toFixed(1)}%` : '—'}</Typography> },
    { field: 'distinctness', headerName: 'Distinctness', width: 110, type: 'number',
      renderCell: (p) => <Typography>{p.value != null ? `${Number(p.value).toFixed(2)}` : '—'}</Typography> },
    { field: 'profiled_at', headerName: 'Profiled At', width: 180,
      renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '—' },
  ], []);

  const freshnessColumns = useMemo(() => [
    { field: 'table_name', headerName: 'Table', flex: 1.5, minWidth: 200,
      renderCell: (p) => <Typography variant="body2" fontWeight={600}>{p.value || '—'}</Typography> },
    { field: 'expected_max_age_hours', headerName: 'Max Age (hrs)', width: 120, type: 'number' },
    { field: 'is_fresh', headerName: 'Fresh?', width: 90,
      renderCell: (p) => <Chip size="small" icon={p.value ? <CheckCircleIcon /> : <ErrorIcon />}
        label={p.value ? 'Yes' : 'No'} color={p.value ? 'success' : 'error'} variant="outlined" /> },
    { field: 'last_data_timestamp', headerName: 'Last Data', width: 180,
      renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '—' },
    { field: 'checked_at', headerName: 'Checked At', width: 180,
      renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '—' },
  ], []);

  const schemaChangeColumns = useMemo(() => [
    { field: 'table_name', headerName: 'Table', flex: 1.2, minWidth: 160,
      renderCell: (p) => <Typography variant="body2" fontWeight={600}>{p.value || '—'}</Typography> },
    { field: 'change_type', headerName: 'Change', width: 100,
      renderCell: (p) => <Chip size="small" label={p.value}
        color={p.value === 'added' ? 'success' : p.value === 'removed' ? 'error' : p.value === 'modified' ? 'warning' : 'default'} /> },
    { field: 'field_name', headerName: 'Field', width: 140 },
    { field: 'detected_at', headerName: 'Detected At', width: 180,
      renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '—' },
  ], []);

  const snapshotColumns = useMemo(() => [
    { field: 'table_name', headerName: 'Table', flex: 1.2, minWidth: 160,
      renderCell: (p) => <Typography variant="body2" fontWeight={600}>{p.value || '—'}</Typography> },
    { field: 'row_count', headerName: 'Row Count', width: 100, type: 'number' },
    { field: 'column_count', headerName: 'Columns', width: 90, type: 'number' },
    { field: 'snapshot_at', headerName: 'Snapshot At', width: 180,
      renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '—' },
    {
      field: 'actions', headerName: '', width: 80, sortable: false, filterable: false,
      renderCell: (p) => (
        <Button size="small" variant="outlined" onClick={() => setSchemaDialog(p.row)}>View</Button>
      ),
    },
  ], []);

  // ─── Render Helpers ──────────────────────────────────────────────────────

  const renderDashboard = () => {
    if (dashboardLoading) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>;
    if (dashboardError) return <Alert severity="error" sx={{ m: 2 }}>{dashboardError}</Alert>;

    const status = metrics?.quality_status ? getQualityStatus(metrics.quality_status) : null;

    return (
      <Box>
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={3}>
            <MetricCard label="Overall Quality Score" value={metrics?.quality_status ?? '—'}
              suffix="%" status={status?.label} color={status?.color} />
          </Grid>
          <Grid item xs={6} md={3}>
            <MetricCard label="Total Rules" value={metrics?.total_rules ?? '—'} />
          </Grid>
          <Grid item xs={6} md={3}>
            <MetricCard label="Active Rules" value={metrics?.active_rules ?? '—'} />
          </Grid>
          <Grid item xs={6} md={3}>
            <MetricCard label="Last Scan" value={metrics?.last_scan ? new Date(metrics.last_scan).toLocaleDateString() : '—'} />
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Recent DQ Results</Typography>
          <Button startIcon={<RefreshIcon />} onClick={loadDashboard} size="small">Refresh</Button>
        </Box>

        <Paper variant="outlined" sx={{ borderRadius: 2 }}>
          <DataGrid
            rows={results}
            columns={resultColumns}
            getRowId={(row) => row.id || row.result_id || `${row.rule}-${row.executed_at}`}
            autoHeight
            density="compact"
            disableRowSelectionOnClick
            initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            pageSizeOptions={[10, 25, 50]}
            sx={{ border: 'none' }}
          />
        </Paper>
      </Box>
    );
  };

  const renderRules = () => {
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">DQ Rules</Typography>
          <Stack direction="row" spacing={1}>
            {selectedRuleIds.length > 0 && (
              <Button
                variant="contained" size="small" color="primary"
                startIcon={bulkExecuting ? <CircularProgress size={16} /> : <PlayArrowIcon />}
                onClick={handleBulkExecute} disabled={bulkExecuting}
              >
                Execute Selected ({selectedRuleIds.length})
              </Button>
            )}
            <Button variant="contained" size="small" startIcon={<AddIcon />}
              onClick={() => handleOpenDialog(null)}>Add Rule</Button>
            <Button startIcon={<RefreshIcon />} size="small" onClick={loadRules}>Refresh</Button>
          </Stack>
        </Box>

        {rulesError && <Alert severity="error" sx={{ mb: 2 }}>{rulesError}</Alert>}

        <Paper variant="outlined" sx={{ borderRadius: 2 }}>
          <DataGrid
            rows={rules}
            columns={ruleColumns}
            getRowId={(row) => row.id}
            autoHeight
            density="compact"
            loading={rulesLoading}
            checkboxSelection
            onRowSelectionModelChange={(ids) => setSelectedRuleIds(ids)}
            disableRowSelectionOnClick
            initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            pageSizeOptions={[10, 25, 50]}
            sx={{ border: 'none' }}
          />
        </Paper>
      </Box>
    );
  };

  const renderProfiles = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Table Profiles</Typography>
        <Button startIcon={<RefreshIcon />} size="small" onClick={loadProfiles}>Refresh</Button>
      </Box>
      <Paper variant="outlined" sx={{ borderRadius: 2 }}>
        <DataGrid
          rows={profiles}
          columns={profileColumns}
          getRowId={(row) => row.id}
          autoHeight
          density="compact"
          loading={profilesLoading}
          disableRowSelectionOnClick
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[10, 25, 50]}
          sx={{ border: 'none' }}
        />
      </Paper>
    </Box>
  );

  const renderFreshnessSchema = () => (
    <Box>
      {freshnessLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
      ) : (
        <>
          <Typography variant="h6" sx={{ mb: 2 }}>Freshness Checks</Typography>
          <Paper variant="outlined" sx={{ borderRadius: 2, mb: 4 }}>
            <DataGrid
              rows={freshness}
              columns={freshnessColumns}
              getRowId={(row) => row.id}
              autoHeight
              density="compact"
              disableRowSelectionOnClick
              initialState={{ pagination: { paginationModel: { pageSize: 15 } } }}
              pageSizeOptions={[10, 15, 25]}
              sx={{ border: 'none' }}
            />
          </Paper>

          <Typography variant="h6" sx={{ mb: 2 }}>Schema Changes</Typography>
          <Paper variant="outlined" sx={{ borderRadius: 2, mb: 4 }}>
            <DataGrid
              rows={schemaChanges}
              columns={schemaChangeColumns}
              getRowId={(row) => row.id}
              autoHeight
              density="compact"
              disableRowSelectionOnClick
              initialState={{ pagination: { paginationModel: { pageSize: 15 } } }}
              pageSizeOptions={[10, 15, 25]}
              sx={{ border: 'none' }}
            />
          </Paper>

          <Typography variant="h6" sx={{ mb: 2 }}>Schema Snapshots</Typography>
          <Paper variant="outlined" sx={{ borderRadius: 2 }}>
            <DataGrid
              rows={schemaSnapshots}
              columns={snapshotColumns}
              getRowId={(row) => row.id}
              autoHeight
              density="compact"
              disableRowSelectionOnClick
              initialState={{ pagination: { paginationModel: { pageSize: 15 } } }}
              pageSizeOptions={[10, 15, 25]}
              sx={{ border: 'none' }}
            />
          </Paper>
        </>
      )}
    </Box>
  );

  // ─── Main Render ─────────────────────────────────────────────────────────

  return (
    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1400, mx: 'auto' }}>
      <Typography variant="h4" fontWeight={700} sx={{ mb: 3 }}>
        Data Quality Hub
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
        {TABS.map((t, i) => (
          <Tab key={i} icon={t.icon} label={t.label} iconPosition="start" />
        ))}
      </Tabs>

      {tab === 0 && renderDashboard()}
      {tab === 1 && renderRules()}
      {tab === 2 && renderProfiles()}
      {tab === 3 && renderFreshnessSchema()}

      {/* Rule Dialog */}
      <DQRuleDialog
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); setEditingRule(null); }}
        onSave={handleSaveRule}
        rule={editingRule}
        tables={tables}
        token={token}
      />

      {/* History Dialog */}
      <HistoryDialog
        open={historyOpen}
        onClose={() => { setHistoryOpen(false); setHistoryRule(null); }}
        rule={historyRule}
        history={historyItems}
        loading={historyLoading}
      />

      {/* Schema Dialog */}
      <SchemaDialog
        open={!!schemaDialog}
        onClose={() => setSchemaDialog(null)}
        snapshot={schemaDialog}
      />
    </Box>
  );
}
