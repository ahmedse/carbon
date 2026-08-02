import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  Alert,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import HistoryIcon from '@mui/icons-material/History';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { listDQRules, createDQRule, updateDQRule, deleteDQRule, executeDQRule, getDQRuleHistory } from '../../api/dq';
import { fetchAssetProfiles } from '../../api/catalog';
import DQRuleDialog from './tabs/DQRuleDialog';

const RULE_TYPE_LABELS = {
  not_null: 'Not Null',
  unique: 'Unique',
  allowed_values: 'Allowed Values',
  range: 'Range',
  regex: 'Regex',
  reference_integrity: 'Reference Integrity',
};

const SEVERITY_COLORS = {
  error: 'error',
  warn: 'warning',
  info: 'info',
  critical: 'error',
};

function mapRuleTarget(rule, tableMap) {
  if (rule.data_field_name || rule.data_field?.name) {
    return rule.data_field_name || rule.data_field.name;
  }
  if (rule.data_field) {
    return `Field #${rule.data_field}`;
  }
  if (rule.data_table) {
    return tableMap[rule.data_table] || `Table #${rule.data_table}`;
  }
  return '—';
}

function unwrapResults(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  return [];
}

function HistoryDialog({ open, onClose, rule, history, loading }) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Execution History for {rule?.name || 'Rule'}</DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
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
                  <TableCell>Duration</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {history.map((item) => (
                  <TableRow key={item.id || `${item.executed_at}-${item.rule}`}>
                    <TableCell>{item.executed_at ? new Date(item.executed_at).toLocaleString() : '—'}</TableCell>
                    <TableCell>{item.passed ? 'Passed' : item.status || 'Failed'}</TableCell>
                    <TableCell>{item.failed_rows ?? item.row_failure_count ?? '—'}</TableCell>
                    <TableCell>{item.duration_seconds != null ? `${item.duration_seconds}s` : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function DQRulesPage() {
  useDocumentTitle("DQ Rules");
  const { token } = useAuth();
  const { notify } = useNotification();
  const [rules, setRules] = useState([]);
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [executingIds, setExecutingIds] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRule, setHistoryRule] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const tableMap = useMemo(
    () => tables.reduce((acc, table) => ({ ...acc, [table.data_table]: table.title || table.name || `Table #${table.data_table}` }), {}),
    [tables],
  );

  const loadRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDQRules(token);
      setRules(unwrapResults(data));
    } catch (err) {
      const message = err.message || 'Unable to load data quality rules';
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  const loadTables = useCallback(async () => {
    try {
      const assets = await fetchAssetProfiles(token);
      const profiles = unwrapResults(assets).filter((asset) => asset.data_table != null && !asset.data_field);
      setTables(profiles);
    } catch (err) {
      console.error('Failed to load table list for DQ rule editor', err);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    loadRules();
    loadTables();
  }, [token, loadRules, loadTables]);

  const handleOpenDialog = (rule = null) => {
    setEditingRule(rule);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setEditingRule(null);
    setDialogOpen(false);
  };

  const handleSaveRule = async (payload) => {
    if (editingRule) {
      await updateDQRule(token, editingRule.id, payload);
      notify({ message: 'DQ rule updated successfully', type: 'success' });
    } else {
      await createDQRule(token, payload);
      notify({ message: 'DQ rule created successfully', type: 'success' });
    }
    handleCloseDialog();
    loadRules();
  };

  const handleDeleteRule = async (rule) => {
    if (!window.confirm(`Delete rule "${rule.name || 'DQ rule'}"?`)) return;
    try {
      await deleteDQRule(token, rule.id);
      notify({ message: 'Rule deleted successfully', type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Unable to delete rule', type: 'error' });
    }
  };

  const handleExecuteRule = async (rule) => {
    if (!rule?.id) return;
    setExecutingIds((prev) => [...prev, rule.id]);
    try {
      await executeDQRule(token, rule.id);
      notify({ message: 'Rule execution triggered', type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Unable to execute rule', type: 'error' });
    } finally {
      setExecutingIds((prev) => prev.filter((id) => id !== rule.id));
    }
  };

  const openHistory = async (rule) => {
    setHistoryRule(rule);
    setHistoryLoading(true);
    setHistoryOpen(true);
    try {
      const data = await getDQRuleHistory(token, rule.id);
      setHistoryItems(unwrapResults(data));
    } catch (err) {
      setHistoryItems([]);
      notify({ message: err.message || 'Unable to load history', type: 'error' });
    } finally {
      setHistoryLoading(false);
    }
  };

  const columns = [
    {
      field: 'name',
      headerName: 'Rule Name',
      flex: 1.5,
      minWidth: 220,
      sortable: true,
      renderCell: (params) => <Typography variant="body2" sx={{ fontWeight: 600 }}>{params.value || '—'}</Typography>,
    },
    {
      field: 'rule_type',
      headerName: 'Rule Type',
      width: 160,
      renderCell: (params) => <Chip label={RULE_TYPE_LABELS[params.value] || params.value} size="small" />,
    },
    {
      field: 'target',
      headerName: 'Target',
      flex: 1,
      minWidth: 170,
      valueGetter: (value, row) => mapRuleTarget(row, tableMap),
    },
    {
      field: 'severity',
      headerName: 'Severity',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value?.toUpperCase() || '—'}
          size="small"
          color={SEVERITY_COLORS[params.value] || 'default'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 110,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'last_run',
      headerName: 'Last Run',
      width: 160,
      valueGetter: (value, row) => row.last_run || row.updated_at || row.created_at,
      renderCell: (params) => (
        <Typography variant="body2">
          {params.value ? new Date(params.value).toLocaleString() : '—'}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 190,
      sortable: false,
      renderCell: (params) => {
        const rule = params.row;
        const executing = executingIds.includes(rule.id);
        return (
          <Stack direction="row" spacing={1}>
            <Tooltip title="Edit rule">
              <IconButton size="small" onClick={() => handleOpenDialog(rule)}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Run rule now">
              <IconButton size="small" disabled={executing} onClick={() => handleExecuteRule(rule)}>
                <PlayArrowIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="View history">
              <IconButton size="small" onClick={() => openHistory(rule)}>
                <HistoryIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete rule">
              <IconButton size="small" color="error" onClick={() => handleDeleteRule(rule)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        );
      },
    },
  ];

  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Box sx={{ mb: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-between', gap: 2 }}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Data Quality Rule Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create, update, execute, and inspect DQ rules across your catalog.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenDialog(null)}>
          New Rule
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Card>
        <CardContent>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          ) : (
            <div style={{ width: '100%' }}>
              <DataGrid
                autoHeight
                rows={rules}
                columns={columns}
                getRowId={(row) => row.id}
                pageSizeOptions={[10, 25, 50]}
                initialState={{ pagination: { paginationModel: { pageSize: 25, page: 0 } } }}
                density="compact"
                disableRowSelectionOnClick
                sx={{ border: 'none' }}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <DQRuleDialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        onSave={handleSaveRule}
        rule={editingRule}
        tables={tables}
        token={token}
      />

      <HistoryDialog
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        rule={historyRule}
        history={historyItems}
        loading={historyLoading}
      />
    </Box>
  );
}
