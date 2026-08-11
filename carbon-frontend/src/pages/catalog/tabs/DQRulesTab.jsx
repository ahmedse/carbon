// src/pages/catalog/tabs/DQRulesTab.jsx
// Data Quality rules for a schema table. Uses apiFetch-backed wrappers.
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Button, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Chip, CircularProgress, Alert, Typography, Tooltip, Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import LaunchIcon from '@mui/icons-material/Launch';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  listDQRules, deleteDQRule, runTableValidation,
} from '../../../api/dq';

const SEVERITY_COLOR = { error: 'error', warn: 'warning', info: 'info' };

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function DQRulesTab({ tableId, fields = [] }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();

  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  const fieldLabel = useCallback(
    (id) => fields.find((f) => f.id === id)?.name || (id ? `#${id}` : '—'),
    [fields],
  );

  const loadRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDQRules(token, { data_table: tableId });
      setRules(unwrap(data));
    } catch (err) {
      setError(err.message || 'Failed to load DQ rules');
      notify({ message: err.message || 'Failed to load DQ rules', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, tableId, notify]);

  useEffect(() => { loadRules(); }, [loadRules]);

  // Manage actions deep-link into the DQ Workspace (/dq) — JSON-first authoring lives there.
  const handleCreate = () => navigate(`/dq/rules?table=${tableId}`);
  const handleEdit = (rule) => navigate(`/dq/rules/${rule.id}`);
  const handleOpenWorkspace = () => navigate('/dq#rules');

  const handleDelete = async (rule) => {
    if (!window.confirm(`Delete rule "${rule.name || rule.rule_type}"?`)) return;
    try {
      await deleteDQRule(token, rule.id);
      notify({ message: 'Rule deleted', type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Delete failed', type: 'error' });
    }
  };

  const handleRunChecks = async () => {
    setRunning(true);
    try {
      const res = await runTableValidation(token, tableId);
      const ran = res?.result?.rules_run ?? 0;
      notify({ message: `DQ validation complete — ${ran} rule(s) run`, type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err.message || 'Run failed (are you in scope for this table?)', type: 'error' });
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Data Quality Rules</Typography>
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<LaunchIcon />}
            onClick={handleOpenWorkspace}
          >
            Open DQ Workspace
          </Button>
          <Button
            variant="outlined"
            startIcon={running ? <CircularProgress size={16} /> : <PlayArrowIcon />}
            onClick={handleRunChecks}
            disabled={running || rules.length === 0}
          >
            Run Checks
          </Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
            Add Rule
          </Button>
        </Stack>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {rules.length === 0 ? (
        <Alert severity="info">No data quality rules defined for this table.</Alert>
      ) : (
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'grey.100' }}>
                <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Scope</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Field</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Severity</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Active</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Runs</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.map((rule) => (
                <TableRow key={rule.id} sx={{ '&:hover': { bgcolor: 'grey.50' } }}>
                  <TableCell sx={{ fontWeight: 500 }}>{rule.name || '—'}</TableCell>
                  <TableCell>
                    <Chip label={rule.rule_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>{rule.scope}</TableCell>
                  <TableCell>{rule.scope === 'field' ? fieldLabel(rule.data_field) : '—'}</TableCell>
                  <TableCell>
                    <Chip
                      label={rule.severity}
                      size="small"
                      color={SEVERITY_COLOR[rule.severity] || 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={rule.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={rule.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                  <TableCell align="right">{rule.results_count ?? 0}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Manage in DQ Workspace">
                      <IconButton size="small" onClick={() => handleEdit(rule)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" onClick={() => handleDelete(rule)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </DetailTabContent>
  );
}
