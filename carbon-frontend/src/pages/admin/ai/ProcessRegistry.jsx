// src/pages/admin/ai/ProcessRegistry.jsx
// Process Registry list — Domain Control. Row click opens ProcessObjectPage
// (/admin/ai/domain/processes/:id). Create draft stays here.
// RULE_8 tokens only; RULE_10 apiFetch only.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Paper,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import AddIcon from '@mui/icons-material/Add';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import {
  AI_OPERATOR,
  AI_PROCESS_OWNER,
  hasAnyCap,
} from '../../../capabilities';
import {
  createProcess,
  listProcesses,
  setKillSwitch,
} from '../../../api/aiRegistry';

const STATUS_TABS = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'review', label: 'Review' },
  { value: 'active', label: 'Active' },
  { value: 'deprecated', label: 'Deprecated' },
];

const SKELETON = `{
  "id": "process-example",
  "version": "0.1.0",
  "owner": "you",
  "status": "draft",
  "objective": "Describe the process objective",
  "scope": { "source": "authenticated_host_context" },
  "steps": [
    { "id": "step-1", "kind": "command", "capability": "carbon:query", "autonomy": "human_only" }
  ],
  "evidence": [],
  "policies": {},
  "exceptions": [],
  "kill_switch": false,
  "tests": []
}`;

function formatTimestamp(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

export function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || ''
    )
    .filter(Boolean);
}

export function objectiveText(def) {
  const o = def?.objective;
  if (!o) return '—';
  if (typeof o === 'string') return o;
  if (o && typeof o === 'object' && o.predicate) return o.predicate;
  return JSON.stringify(o);
}

export function flattenDiff(added, removed, changed, prefix = '') {
  const out = [];
  for (const key of Object.keys(added || {})) {
    out.push({
      kind: 'added',
      label: prefix ? `${prefix}.${key}` : key,
      value: added[key],
    });
  }
  for (const key of Object.keys(removed || {})) {
    out.push({
      kind: 'removed',
      label: prefix ? `${prefix}.${key}` : key,
      value: removed[key],
    });
  }
  for (const key of Object.keys(changed || {})) {
    const entry = changed[key];
    const label = prefix ? `${prefix}.${key}` : key;
    if (
      entry &&
      typeof entry === 'object' &&
      !Array.isArray(entry) &&
      'from' in entry &&
      'to' in entry
    ) {
      out.push({ kind: 'changed', label, from: entry.from, to: entry.to });
    } else if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
      out.push(...flattenDiff(entry.added, entry.removed, entry.changed, label));
    }
  }
  return out;
}

function statusColor(status, theme) {
  if (status === 'active') return theme.palette.success.main;
  if (status === 'review') return theme.palette.warning.main;
  if (status === 'deprecated') return theme.palette.text.disabled;
  return theme.palette.info.main;
}

function errorText(err) {
  const d = err?.data?.detail ?? err?.message;
  if (typeof d === 'string') return d;
  if (d && typeof d === 'object') return JSON.stringify(d, null, 2);
  return 'Request failed';
}

function GatedButton({ allowed, reason, children, ...props }) {
  const button = (
    <Button {...props} disabled={props.disabled || !allowed}>
      {children}
    </Button>
  );
  if (!allowed) {
    return (
      <Tooltip title={reason || ''}>
        <span>{button}</span>
      </Tooltip>
    );
  }
  return button;
}

export default function ProcessRegistry() {
  useDocumentTitle('Process Registry');
  const theme = useTheme();
  const navigate = useNavigate();
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const isOwner = useMemo(() => hasAnyCap(caps, [AI_PROCESS_OWNER]), [caps]);
  const canKill = useMemo(
    () => hasAnyCap(caps, [AI_OPERATOR, AI_PROCESS_OWNER]),
    [caps],
  );

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [status, setStatus] = useState('all');
  const [acting, setActing] = useState(false);

  const [draftOpen, setDraftOpen] = useState(false);
  const [draftText, setDraftText] = useState(SKELETON);
  const [draftError, setDraftError] = useState('');
  const [creating, setCreating] = useState(false);

  const load = useCallback(
    async (statusFilter = status) => {
      setLoading(true);
      try {
        const result = await listProcesses(token, {
          status: statusFilter === 'all' ? undefined : statusFilter,
        });
        setRows(Array.isArray(result) ? result : []);
        setOffline(false);
      } catch {
        setRows([]);
        setOffline(true);
      } finally {
        setLoading(false);
      }
    },
    [token, status],
  );

  useEffect(() => {
    load(status);
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  const openDetail = useCallback(
    (id) => {
      navigate(`/admin/ai/domain/processes/${encodeURIComponent(id)}`);
    },
    [navigate],
  );

  const openDraft = () => {
    setDraftText(SKELETON);
    setDraftError('');
    setDraftOpen(true);
  };

  const handleCreate = async () => {
    let doc;
    try {
      doc = JSON.parse(draftText);
    } catch {
      setDraftError('Invalid JSON — please fix the syntax.');
      return;
    }
    if (!doc || typeof doc !== 'object' || Array.isArray(doc)) {
      setDraftError('The definition must be a JSON object.');
      return;
    }
    if (!doc.id || !doc.version || !doc.status) {
      setDraftError('The definition requires id, version, and status fields.');
      return;
    }
    if (!Array.isArray(doc.steps) || doc.steps.length === 0) {
      setDraftError('The definition requires at least one step.');
      return;
    }
    setCreating(true);
    setDraftError('');
    try {
      const created = await createProcess(token, doc);
      notify({ message: `Created draft ${created.process_id}.`, type: 'success' });
      setDraftOpen(false);
      navigate(`/admin/ai/domain/processes/${encodeURIComponent(created.process_id)}`);
    } catch (err) {
      setDraftError(errorText(err));
    } finally {
      setCreating(false);
    }
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h5">Process Registry</Typography>
          <Stack direction="row" spacing={1}>
            <GatedButton
              allowed={isOwner}
              reason="Requires ai:process_owner"
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={openDraft}
            >
              New draft
            </GatedButton>
            <Button
              size="small"
              startIcon={<RefreshIcon />}
              onClick={() => load()}
              disabled={loading}
            >
              Refresh
            </Button>
          </Stack>
        </Stack>

        <Typography variant="body2" color="text.secondary">
          Open a process for structured scope, steps, autonomy, and lifecycle —
          not JSON-first.
        </Typography>

        <Tabs
          value={status}
          onChange={(_, v) => setStatus(v)}
          variant="scrollable"
          scrollButtons="auto"
        >
          {STATUS_TABS.map((t) => (
            <Tab key={t.value} value={t.value} label={t.label} />
          ))}
        </Tabs>

        {offline && (
          <Paper sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
            <CloudOffIcon color="disabled" />
            <Typography variant="body2">
              Registry is temporarily unavailable.
            </Typography>
          </Paper>
        )}

        {loading ? (
          <Stack alignItems="center" sx={{ py: 6 }}>
            <CircularProgress />
          </Stack>
        ) : rows.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No process definitions.
            </Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Process ID</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Owner</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Kill switch</TableCell>
                  <TableCell>Updated</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow
                    key={row.process_id}
                    hover
                    onClick={() => openDetail(row.process_id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{row.process_id || '—'}</TableCell>
                    <TableCell>{row.version || '—'}</TableCell>
                    <TableCell>{row.owner || '—'}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={row.status}
                        variant="outlined"
                        sx={{
                          color: statusColor(row.status, theme),
                          borderColor: statusColor(row.status, theme),
                        }}
                      />
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Switch
                        size="small"
                        checked={Boolean(row.kill_switch)}
                        disabled={!canKill || acting}
                        onChange={async (e) => {
                          setActing(true);
                          try {
                            await setKillSwitch(token, row.process_id, e.target.checked);
                            notify({ message: 'Kill switch updated.', type: 'success' });
                            await load();
                          } catch (err) {
                            notifyFromError(err, 'Kill switch failed');
                          } finally {
                            setActing(false);
                          }
                        }}
                      />
                    </TableCell>
                    <TableCell>{formatTimestamp(row.updated_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Stack>

      <Dialog open={draftOpen} onClose={() => setDraftOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>New draft</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 1 }}>
            Paste the full process definition JSON. After create, edit scope and
            steps on the process page.
          </DialogContentText>
          <TextField
            label="Definition JSON"
            multiline
            fullWidth
            minRows={12}
            maxRows={24}
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            error={Boolean(draftError)}
            helperText={draftError || ' '}
            sx={{
              '& .MuiInputBase-input': {
                fontFamily: 'monospace',
                fontSize: '0.8125rem',
              },
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDraftOpen(false)} disabled={creating}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={creating || !isOwner}
            onClick={handleCreate}
          >
            {creating ? 'Saving…' : 'Create draft'}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
