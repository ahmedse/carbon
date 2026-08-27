// src/pages/admin/ai/AgentsPanel.jsx
// Route /admin/ai/agents — W3-G UPGRADE: real read/write agent catalog.
// Table (CarbonDataGrid) + detail drawer (role, edges, skills, status) +
// Graph ⇄ Table toggle embedding the declared topology (AgentTopologyGraph).
// Admin-gated create/edit/remove — RULE_21: destructive/replay actions need an
// explicit confirm Dialog; the API is not called until confirmed.
//
// Staff proxy: canSchemaAdmin() (admins_group/admin) OR isGlobalAdminFlag.
// Non-staff admins with AI_VIEW_CONSOLE get a read-only catalog. RULE_8 tokens
// only; RULE_10 apiFetch only (via src/api/aiCatalog.js); RULE_16 grounded
// states. This is the ADMIN surface — no user plan controls here.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Drawer,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import SchemaOutlinedIcon from '@mui/icons-material/SchemaOutlined';
import TableRowsOutlinedIcon from '@mui/icons-material/TableRowsOutlined';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import AgentTopologyGraph, {
  AGENT_ROLES,
  agentRoleColor,
} from '../../../components/graph/AgentTopologyGraph';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { listAgents, createAgent, updateAgent, deleteAgent, getTopology } from '../../../api/aiCatalog';

/** "a, b, c" → ["a","b","c"] (trims, drops empties). */
function parseList(value) {
  return (value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

const EMPTY_FORM = {
  name: '',
  role: AGENT_ROLES[0],
  tool_set: '',
  playbook_blocks: '',
  model_override: '',
  max_turns: 3,
};

export default function AgentsPanel() {
  useDocumentTitle('Agents');
  const theme = useTheme();
  const { token, canSchemaAdmin, isGlobalAdminFlag } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const staff = Boolean(canSchemaAdmin?.() || isGlobalAdminFlag);

  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  // Table ⇄ Topology toggle (topology fetched lazily on first switch).
  const [view, setView] = useState('table');
  const [topology, setTopology] = useState(null);
  const [topoLoading, setTopoLoading] = useState(false);

  // Detail drawer.
  const [selected, setSelected] = useState(null);

  // CRUD dialogs.
  const [dialog, setDialog] = useState(null); // 'create' | 'edit' | 'delete'
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listAgents(token);
      setAgents(Array.isArray(rows) ? rows : []);
      setOffline(false);
    } catch {
      setAgents([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const loadTopology = useCallback(async () => {
    if (topology || topoLoading) return;
    setTopoLoading(true);
    try {
      setTopology(await getTopology(token));
    } catch {
      setTopology(null);
    } finally {
      setTopoLoading(false);
    }
  }, [token, topology, topoLoading]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setDialog('create');
  };

  const openEdit = (row) => {
    setForm({
      name: row.name,
      role: AGENT_ROLES.includes(row.role) ? row.role : AGENT_ROLES[0],
      tool_set: Array.isArray(row.tool_set) ? row.tool_set.join(', ') : '',
      playbook_blocks: Array.isArray(row.playbook_blocks) ? row.playbook_blocks.join(', ') : '',
      model_override: row.model_override || '',
      max_turns: row.max_turns ?? 3,
    });
    setDialog('edit');
  };

  const openDelete = (row) => {
    setSelected(row);
    setDialog('delete');
  };

  const onSave = async () => {
    if (!dialog || !staff) return;
    setSaving(true);
    try {
      const payload = {
        role: form.role,
        tool_set: parseList(form.tool_set),
        playbook_blocks: parseList(form.playbook_blocks),
        max_turns: Number(form.max_turns) || 3,
      };
      if (form.model_override) payload.model_override = form.model_override;
      if (dialog === 'create') {
        payload.name = form.name.trim();
        await createAgent(token, payload);
        notify({ message: `Agent ${payload.name} registered.`, type: 'success' });
      } else {
        // Update serializer has NO name field — rename is delete + create.
        await updateAgent(token, selected.id, payload);
        notify({ message: `Agent ${selected.name} updated.`, type: 'success' });
      }
      setDialog(null);
      await load();
      setTopology(null); // topology is stale after a write — refetch on next view
    } catch (err) {
      notifyFromError(err, 'Could not save agent.');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!selected || !staff) return;
    setSaving(true);
    try {
      await deleteAgent(token, selected.id);
      notify({ message: `Agent ${selected.name} removed (soft delete).`, type: 'success' });
      setDialog(null);
      setSelected(null);
      await load();
      setTopology(null);
    } catch (err) {
      notifyFromError(err, 'Could not remove agent.');
    } finally {
      setSaving(false);
    }
  };

  // ── DataGrid columns (v8 positional valueFormatter — never destructure) ──
  const columns = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Agent',
        flex: 1,
        minWidth: 160,
      },
      {
        field: 'role',
        headerName: 'Role',
        width: 170,
        renderCell: ({ value }) => (
          <Chip
            size="small"
            label={value}
            variant="outlined"
            sx={{
              fontSize: '0.625rem',
              height: 18,
              color: agentRoleColor(value),
              borderColor: agentRoleColor(value),
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 110,
        renderCell: ({ value }) => (
          <Chip
            size="small"
            label={value ? 'active' : 'inactive'}
            variant="outlined"
            sx={{
              fontSize: '0.625rem',
              height: 18,
              color: value ? theme.palette.success.main : theme.palette.text.disabled,
              borderColor: value ? theme.palette.success.main : theme.palette.divider,
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        ),
      },
      {
        field: 'handoff_count',
        headerName: 'Handoffs',
        width: 110,
        valueGetter: (_value, row) =>
          (Array.isArray(row?.outgoing_handoffs) ? row.outgoing_handoffs.length : 0) +
          (Array.isArray(row?.incoming_handoffs) ? row.incoming_handoffs.length : 0),
      },
      {
        field: 'skill_count',
        headerName: 'Skills',
        width: 90,
        valueGetter: (_value, row) => (Array.isArray(row?.skills) ? row.skills.length : 0),
      },
      ...(staff
        ? [
            {
              field: 'actions',
              headerName: 'Actions',
              width: 96,
              sortable: false,
              disableColumnMenu: true,
              renderCell: ({ row }) => (
                <Stack direction="row" spacing={0.5}>
                  <Tooltip title="Edit agent">
                    <IconButton size="small" aria-label={`Edit ${row.name}`} onClick={() => openEdit(row)}>
                      <EditOutlinedIcon sx={{ fontSize: '0.9375rem' }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Remove agent">
                    <IconButton size="small" aria-label={`Remove ${row.name}`} onClick={() => openDelete(row)}>
                      <DeleteOutlineIcon sx={{ fontSize: '0.9375rem' }} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              ),
            },
          ]
        : []),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme, staff],
  );

  const toggleView = (_e, next) => {
    if (!next) return;
    setView(next);
    if (next === 'topology') loadTopology();
  };

  const outgoingHandoffs = Array.isArray(selected?.outgoing_handoffs) ? selected.outgoing_handoffs : [];
  const incomingHandoffs = Array.isArray(selected?.incoming_handoffs) ? selected.incoming_handoffs : [];
  const skills = Array.isArray(selected?.skills) ? selected.skills : [];
  const toolSet = Array.isArray(selected?.tool_set) ? selected.tool_set : [];
  const playbookBlocks = Array.isArray(selected?.playbook_blocks) ? selected.playbook_blocks : [];

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ width: '100%', maxWidth: 1200 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
            Agents
          </Typography>
          {staff && (
            <Button
              size="small"
              variant="contained"
              startIcon={<AddIcon sx={{ fontSize: '0.9375rem' }} />}
              onClick={openCreate}
              sx={{ fontSize: '0.75rem' }}
            >
              Register agent
            </Button>
          )}
          <Button
            size="small"
            startIcon={<RefreshIcon sx={{ fontSize: '0.9375rem' }} />}
            onClick={load}
            disabled={loading}
            sx={{ fontSize: '0.75rem' }}
          >
            Refresh
          </Button>
          <ToggleButtonGroup size="small" exclusive value={view} onChange={toggleView} aria-label="Agents view">
            <ToggleButton value="table" sx={{ fontSize: '0.6875rem', px: 1 }}>
              <TableRowsOutlinedIcon sx={{ fontSize: '0.9375rem', mr: 0.5 }} />
              Table
            </ToggleButton>
            <ToggleButton value="topology" sx={{ fontSize: '0.6875rem', px: 1 }}>
              <SchemaOutlinedIcon sx={{ fontSize: '0.9375rem', mr: 0.5 }} />
              Topology
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          Registered agent roles and their declared handoff wiring. Admin manage surface —
          {staff ? ' create, edit and remove agents (confirm-gated).' : ' read-only (staff required to edit).'}
        </Typography>

        {loading && (
          <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <CircularProgress size={28} />
          </Paper>
        )}

        {!loading && offline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Catalog unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                Could not reach the agent catalog. Check the API and try again.
              </Typography>
              <Button size="small" startIcon={<RefreshIcon sx={{ fontSize: '0.9375rem' }} />} onClick={load}>
                Retry
              </Button>
            </Stack>
          </Paper>
        )}

        {!loading && !offline && view === 'table' && (
          <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
            <CarbonDataGrid
              columns={columns}
              rows={agents}
              loading={false}
              getRowId={(row) => row.id}
              pageSize={10}
              pageSizeOptions={[10, 25, 50]}
              density="compact"
              emptyMessage="No agents registered yet."
              onRowClick={(params) => setSelected(params.row)}
            />
          </Paper>
        )}

        {!loading && !offline && view === 'topology' && (
          <Box>
            {topoLoading && (
              <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress size={28} />
              </Paper>
            )}
            {!topoLoading && !topology && (
              <Paper variant="outlined" sx={{ p: 3 }}>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  Topology could not be loaded.
                </Typography>
              </Paper>
            )}
            {!topoLoading && topology && <AgentTopologyGraph topology={topology} />}
          </Box>
        )}

        {/* ── Detail drawer: role, edges, skills, status ─────────────────── */}
        <Drawer
          anchor="right"
          open={Boolean(selected) && dialog !== 'delete'}
          onClose={() => setSelected(null)}
          PaperProps={{ sx: { width: { xs: '100%', sm: 520 }, p: 2.5 } }}
        >
          {selected && (
            <Stack spacing={1}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
                  {selected.name}
                </Typography>
                <IconButton size="small" onClick={() => setSelected(null)} aria-label="Close detail">
                  <CloseIcon />
                </IconButton>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  size="small"
                  label={selected.role}
                  variant="outlined"
                  sx={{
                    fontSize: '0.625rem',
                    height: 18,
                    color: agentRoleColor(selected.role),
                    borderColor: agentRoleColor(selected.role),
                    '& .MuiChip-label': { px: 0.75 },
                  }}
                />
                <Chip
                  size="small"
                  label={selected.is_active ? 'active' : 'inactive'}
                  variant="outlined"
                  sx={{
                    fontSize: '0.625rem',
                    height: 18,
                    color: selected.is_active ? theme.palette.success.main : theme.palette.text.disabled,
                    borderColor: selected.is_active ? theme.palette.success.main : theme.palette.divider,
                    '& .MuiChip-label': { px: 0.75 },
                  }}
                />
              </Stack>

              <Divider />
              <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Max turns: <strong>{selected.max_turns ?? '—'}</strong>
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Model: <strong>{selected.model_override || 'default'}</strong>
                </Typography>
              </Stack>

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Tool set
              </Typography>
              {toolSet.length ? (
                <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                  {toolSet.map((t) => (
                    <Chip key={t} size="small" label={t} sx={{ fontSize: '0.625rem', height: 2.25 }} />
                  ))}
                </Stack>
              ) : (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  No tools configured.
                </Typography>
              )}

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Outgoing handoffs ({outgoingHandoffs.length})
              </Typography>
              {outgoingHandoffs.length ? (
                <Stack spacing={0.5}>
                  {outgoingHandoffs.map((h, i) => (
                    <Typography key={`${h.to_agent_id}-${i}`} variant="caption" sx={{ fontSize: '0.6875rem' }}>
                      → <strong>{h.to_agent_id}</strong>
                      {h.description ? ` — ${h.description}` : ''}
                      {h.max_parallel ? ` (max ${h.max_parallel})` : ''}
                    </Typography>
                  ))}
                </Stack>
              ) : (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  No outgoing handoffs declared.
                </Typography>
              )}

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Incoming handoffs ({incomingHandoffs.length})
              </Typography>
              {incomingHandoffs.length ? (
                <Stack spacing={0.5}>
                  {incomingHandoffs.map((h, i) => (
                    <Typography key={`${h.from_agent_id}-${i}`} variant="caption" sx={{ fontSize: '0.6875rem' }}>
                      ← <strong>{h.from_agent_id}</strong>
                      {h.description ? ` — ${h.description}` : ''}
                    </Typography>
                  ))}
                </Stack>
              ) : (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  No incoming handoffs declared.
                </Typography>
              )}

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Skills ({skills.length})
              </Typography>
              {skills.length ? (
                <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                  {skills.map((s) => (
                    <Chip
                      key={s.id ?? s.name}
                      size="small"
                      label={s.name}
                      sx={{ fontSize: '0.625rem', height: 2.25 }}
                    />
                  ))}
                </Stack>
              ) : (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  No admitted skills.
                </Typography>
              )}

              {playbookBlocks.length > 0 && (
                <>
                  <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                    Playbook blocks
                  </Typography>
                  <Stack spacing={0.5}>
                    {playbookBlocks.map((b, i) => (
                      <Typography key={i} variant="caption" sx={{ fontSize: '0.6875rem' }}>
                        • {b}
                      </Typography>
                    ))}
                  </Stack>
                </>
              )}
            </Stack>
          )}
        </Drawer>

        {/* ── Create / Edit dialog ───────────────────────────────────────── */}
        <Dialog
          open={dialog === 'create' || dialog === 'edit'}
          onClose={() => !saving && setDialog(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ fontSize: '1rem', fontWeight: 700 }}>
            {dialog === 'create' ? 'Register agent' : `Edit ${form.name}`}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              {dialog === 'create' && (
                <TextField
                  size="small"
                  label="Name (unique — engine upsert key)"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  fullWidth
                />
              )}
              <FormControl size="small" fullWidth>
                <InputLabel id="agent-role-label">Role</InputLabel>
                <Select
                  labelId="agent-role-label"
                  label="Role"
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                >
                  {AGENT_ROLES.map((r) => (
                    <MenuItem key={r} value={r}>
                      {r}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                size="small"
                label="Tool set (comma-separated)"
                value={form.tool_set}
                onChange={(e) => setForm({ ...form, tool_set: e.target.value })}
                fullWidth
                placeholder="web_search, kg_lookup"
              />
              <TextField
                size="small"
                label="Playbook blocks (comma-separated, optional)"
                value={form.playbook_blocks}
                onChange={(e) => setForm({ ...form, playbook_blocks: e.target.value })}
                fullWidth
                placeholder="verify_grounding, cite_sources"
              />
              <TextField
                size="small"
                label="Model override (optional)"
                value={form.model_override}
                onChange={(e) => setForm({ ...form, model_override: e.target.value })}
                fullWidth
              />
              <TextField
                size="small"
                label="Max turns"
                type="number"
                inputProps={{ min: 1, max: 100 }}
                value={form.max_turns}
                onChange={(e) => setForm({ ...form, max_turns: e.target.value })}
                fullWidth
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button size="small" onClick={() => setDialog(null)} disabled={saving} sx={{ fontSize: '0.75rem' }}>
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              onClick={onSave}
              disabled={saving || (dialog === 'create' && !form.name.trim())}
              sx={{ fontSize: '0.75rem' }}
            >
              {saving ? 'Saving…' : dialog === 'create' ? 'Register' : 'Save changes'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* ── Delete confirm dialog (RULE_21) ────────────────────────────── */}
        <Dialog open={dialog === 'delete'} onClose={() => !saving && setDialog(null)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ fontSize: '1rem', fontWeight: 700 }}>Remove agent?</DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ fontSize: '0.8125rem' }}>
              Remove <strong>{selected?.name}</strong> (role: {selected?.role})? This is a soft
              delete — the agent is deactivated and no longer receives work, but its catalog
              record and handoff history are retained.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button size="small" onClick={() => setDialog(null)} disabled={saving} sx={{ fontSize: '0.75rem' }}>
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              color="error"
              onClick={onDelete}
              disabled={saving}
              sx={{ fontSize: '0.75rem' }}
            >
              {saving ? 'Removing…' : 'Remove agent'}
            </Button>
          </DialogActions>
        </Dialog>
      </Stack>
    </PageContainer>
  );
}
