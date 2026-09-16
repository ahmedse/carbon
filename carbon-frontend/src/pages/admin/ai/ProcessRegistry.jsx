// src/pages/admin/ai/ProcessRegistry.jsx
// Route /admin/ai/registry — P3-05c Process Registry. Dense table of governed
// process definitions (latest per process_id) + a detail drawer with the full
// definition, a structured diff vs active, and the autonomy dial editor.
//
// CBAC: reads are server-gated; every write action maps to a capability
// (process_owner / publisher / operator). The backend is the AUTHORITY — we
// render every action but disable + tooltip the ones the caller lacks, and
// surface the server's 403 {error, detail} when it refuses.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiRegistry.js).
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
import CloseIcon from '@mui/icons-material/Close';
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
  AI_PUBLISHER,
  hasAnyCap,
} from '../../../capabilities';
import {
  createProcess,
  deprecateProcess,
  getAutonomy,
  getDiff,
  getProcess,
  listProcesses,
  publishProcess,
  setAutonomy as saveAutonomyDial,
  setKillSwitch,
  submitProcess,
  updateProcess,
} from '../../../api/aiRegistry';

const AUTONOMY_LEVELS = [
  'observe',
  'propose',
  'act_confirm',
  'act_notify',
  'act_silent',
  'human_only',
];

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

/** Normalize `useAuth().userCapabilities` to plain string keys. */
export function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || ''
    )
    .filter(Boolean);
}

/** `objective` may be a string or `{predicate}`. */
export function objectiveText(def) {
  const o = def?.objective;
  if (!o) return '—';
  if (typeof o === 'string') return o;
  if (o && typeof o === 'object' && o.predicate) return o.predicate;
  return JSON.stringify(o);
}

/**
 * Flatten a recursive registry diff into a flat list of
 * {kind: 'added'|'removed'|'changed', label, value?, from?, to?}.
 */
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

function valueText(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function errorText(err) {
  const d = err?.data?.detail ?? err?.message;
  if (typeof d === 'string') return d;
  if (d && typeof d === 'object') return JSON.stringify(d, null, 2);
  return 'Request failed';
}

/** Button that is disabled + tooltipped when the caller lacks a capability. */
function GatedButton({ allowed, reason, children, ...props }) {
  const button = (
    <Button {...props} disabled={props.disabled || !allowed}>
      {children}
    </Button>
  );
  if (!allowed) {
    return (
      <Tooltip title={reason}>
        <span>{button}</span>
      </Tooltip>
    );
  }
  return button;
}

export default function ProcessRegistry() {
  useDocumentTitle('Process Registry');
  const theme = useTheme();
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const isOwner = useMemo(() => hasAnyCap(caps, [AI_PROCESS_OWNER]), [caps]);
  const isPublisher = useMemo(() => hasAnyCap(caps, [AI_PUBLISHER]), [caps]);
  const canKill = useMemo(
    () => hasAnyCap(caps, [AI_OPERATOR, AI_PROCESS_OWNER]),
    [caps]
  );
  const canDeprecate = useMemo(
    () => hasAnyCap(caps, [AI_PROCESS_OWNER, AI_PUBLISHER]),
    [caps]
  );

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [status, setStatus] = useState('all');

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
    [token, status]
  );

  useEffect(() => {
    load(status);
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Detail drawer state ──────────────────────────────────────────
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [diff, setDiff] = useState(null);
  const [, setAutonomy] = useState(null);
  const [autonomyDraft, setAutonomyDraft] = useState({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const [acting, setActing] = useState(false);

  const openDetail = useCallback(
    async (id) => {
      setSelectedId(id);
      setDetailLoading(true);
      setDetailError(false);
      setDetail(null);
      setDiff(null);
      setAutonomy(null);
      try {
        const [d, df, au] = await Promise.all([
          getProcess(token, id),
          getDiff(token, id),
          getAutonomy(token, id),
        ]);
        setDetail(d);
        setDiff(df);
        setAutonomy(au);
        setAutonomyDraft(au || {});
      } catch {
        setDetailError(true);
      } finally {
        setDetailLoading(false);
      }
    },
    [token]
  );

  const closeDetail = useCallback(() => {
    setSelectedId(null);
    setDetail(null);
    setDiff(null);
    setAutonomy(null);
  }, []);

  // ── New draft dialog ─────────────────────────────────────────────
  const [draftOpen, setDraftOpen] = useState(false);
  const [draftText, setDraftText] = useState(SKELETON);
  const [draftError, setDraftError] = useState('');
  const [creating, setCreating] = useState(false);

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
      await load();
    } catch (err) {
      setDraftError(errorText(err));
    } finally {
      setCreating(false);
    }
  };

  const runAction = useCallback(
    async (fn, args, successMsg) => {
      setActing(true);
      try {
        await fn(...args);
        notify({ message: successMsg, type: 'success' });
        if (selectedId) await openDetail(selectedId);
        await load();
      } catch (err) {
        notifyFromError(err, 'Action failed');
      } finally {
        setActing(false);
      }
    },
    [notify, notifyFromError, openDetail, load, selectedId]
  );

  const handleEdit = async () => {
    // Edit re-opens the JSON dialog pre-filled with the current definition.
    const current = detail?.definition || {};
    setDraftText(JSON.stringify(current, null, 2));
    setDraftError('');
    setDraftOpen(true);
    // NOTE: reuse the create dialog but PATCH the existing draft.
  };

  const saveEdit = async () => {
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
    setCreating(true);
    setDraftError('');
    try {
      const updated = await updateProcess(token, selectedId, doc);
      notify({ message: `Updated draft ${updated.process_id}.`, type: 'success' });
      setDraftOpen(false);
      await openDetail(selectedId);
      await load();
    } catch (err) {
      setDraftError(errorText(err));
    } finally {
      setCreating(false);
    }
  };

  const saveAutonomy = async () => {
    await runAction(saveAutonomyDial, [token, selectedId, autonomyDraft], 'Autonomy dial saved.');
  };

  const steps = Array.isArray(detail?.definition?.steps)
    ? detail.definition.steps
    : [];

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
                        disabled={!canKill}
                        onChange={(e) =>
                          runAction(
                            setKillSwitch,
                            [token, row.process_id, e.target.checked],
                            'Kill switch updated.'
                          )
                        }
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

      {/* ── New draft / edit JSON dialog ───────────────────────────── */}
      <Dialog open={draftOpen} onClose={() => setDraftOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{selectedId ? 'Edit draft' : 'New draft'}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 1 }}>
            {selectedId
              ? 'Edit the definition JSON. Only drafts can be edited (status stays "draft").'
              : 'Paste the full process definition JSON. It is created as a draft.'}
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
            sx={{ '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: '0.75rem' } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDraftOpen(false)} disabled={creating}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={creating || (!isOwner && !selectedId)}
            onClick={selectedId ? saveEdit : handleCreate}
          >
            {creating ? 'Saving…' : selectedId ? 'Save changes' : 'Create draft'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Detail drawer ───────────────────────────────────────────── */}
      <Drawer
        anchor="right"
        open={Boolean(selectedId)}
        onClose={closeDetail}
        PaperProps={{ sx: { width: 640, maxWidth: '100vw' } }}
      >
        <Box sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
            <Typography variant="h6">Process Detail</Typography>
            <IconButton onClick={closeDetail}>
              <CloseIcon />
            </IconButton>
          </Stack>

          {detailLoading ? (
            <Stack alignItems="center" sx={{ py: 6 }}>
              <CircularProgress />
            </Stack>
          ) : detailError ? (
            <Typography variant="body2" color="text.secondary">
              Could not load process detail.
            </Typography>
          ) : detail ? (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <Chip
                  size="small"
                  label={detail.status}
                  variant="outlined"
                  sx={{
                    color: statusColor(detail.status, theme),
                    borderColor: statusColor(detail.status, theme),
                  }}
                />
                <Typography variant="subtitle1">{detail.process_id}</Typography>
                <Typography variant="body2" color="text.secondary">
                  v{detail.version}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  · {detail.owner}
                </Typography>
              </Stack>

              <Divider />

              <Stack spacing={0.5}>
                <Typography variant="overline" sx={{ lineHeight: 1 }}>
                  Objective
                </Typography>
                <Typography variant="body2">{objectiveText(detail.definition)}</Typography>
              </Stack>

              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Step</TableCell>
                      <TableCell>Kind</TableCell>
                      <TableCell>Capability</TableCell>
                      <TableCell>Autonomy</TableCell>
                      <TableCell>Consent</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {steps.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell>{s.id}</TableCell>
                        <TableCell>{s.kind}</TableCell>
                        <TableCell>{s.capability || '—'}</TableCell>
                        <TableCell>{s.autonomy || '—'}</TableCell>
                        <TableCell>{s.consent === true ? 'Yes' : 'No'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

              <Stack direction="row" spacing={2} flexWrap="wrap">
                <Typography variant="body2">
                  <strong>Evidence:</strong>{' '}
                  {Array.isArray(detail.definition?.evidence)
                    ? detail.definition.evidence.length
                    : 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Tests:</strong>{' '}
                  {Array.isArray(detail.definition?.tests)
                    ? detail.definition.tests.length
                    : 0}
                </Typography>
                <Typography variant="body2">
                  <strong>Kill switch:</strong>{' '}
                  {detail.kill_switch ? 'enabled' : 'disabled'}
                </Typography>
              </Stack>

              {/* ── Actions (CBAC-gated, server-authoritative) ─────── */}
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {detail.status === 'draft' && (
                  <>
                    <GatedButton
                      allowed={isOwner}
                      reason="Requires ai:process_owner"
                      size="small"
                      variant="outlined"
                      onClick={handleEdit}
                      disabled={acting}
                    >
                      Edit
                    </GatedButton>
                    <GatedButton
                      allowed={isOwner}
                      reason="Requires ai:process_owner"
                      size="small"
                      variant="contained"
                      onClick={() => runAction(submitProcess, [token, selectedId], 'Submitted for review.')}
                      disabled={acting}
                    >
                      Submit
                    </GatedButton>
                  </>
                )}
                {detail.status === 'review' && (
                  <GatedButton
                    allowed={isPublisher}
                    reason="Requires ai:publisher"
                    size="small"
                    variant="contained"
                    color="success"
                    onClick={() => runAction(publishProcess, [token, selectedId], 'Published.')}
                    disabled={acting}
                  >
                    Publish
                  </GatedButton>
                )}
                {detail.status === 'active' && (
                  <GatedButton
                    allowed={canDeprecate}
                    reason="Requires ai:process_owner or ai:publisher"
                    size="small"
                    variant="outlined"
                    color="warning"
                    onClick={() => runAction(deprecateProcess, [token, selectedId], 'Deprecated.')}
                    disabled={acting}
                  >
                    Deprecate
                  </GatedButton>
                )}
                <Tooltip title={canKill ? '' : 'Requires ai:operator or ai:process_owner'}>
                  <span>
                    <Switch
                      size="small"
                      checked={Boolean(detail.kill_switch)}
                      disabled={!canKill || acting}
                      onChange={(e) =>
                        runAction(
                          setKillSwitch,
                          [token, selectedId, e.target.checked],
                          'Kill switch updated.'
                        )
                      }
                    />
                  </span>
                </Tooltip>
              </Stack>

              {/* ── Diff panel ──────────────────────────────────────── */}
              <Stack spacing={1}>
                <Typography variant="overline" sx={{ lineHeight: 1 }}>
                  Diff vs active
                </Typography>
                <DiffPanel diff={diff} />
              </Stack>

              {/* ── Autonomy dial editor ────────────────────────────── */}
              <Stack spacing={1}>
                <Typography variant="overline" sx={{ lineHeight: 1 }}>
                  Autonomy dial
                </Typography>
                {steps.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No steps.
                  </Typography>
                ) : (
                  steps.map((s) => (
                    <Stack key={s.id} direction="row" spacing={1} alignItems="center">
                      <Typography variant="body2" sx={{ minWidth: 140 }}>
                        {s.id}
                      </Typography>
                      <FormControl size="small" sx={{ minWidth: 180 }} disabled={!isOwner}>
                        <InputLabel id={`autonomy-${s.id}-label`}>Autonomy</InputLabel>
                        <Select
                          labelId={`autonomy-${s.id}-label`}
                          label="Autonomy"
                          value={autonomyDraft[s.id] || 'human_only'}
                          onChange={(e) =>
                            setAutonomyDraft((prev) => ({
                              ...prev,
                              [s.id]: e.target.value,
                            }))
                          }
                        >
                          {AUTONOMY_LEVELS.map((level) => (
                            <MenuItem key={level} value={level}>
                              {level}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  ))
                )}
                <GatedButton
                  allowed={isOwner}
                  reason="Requires ai:process_owner"
                  size="small"
                  variant="outlined"
                  onClick={saveAutonomy}
                  disabled={acting || steps.length === 0}
                >
                  Save autonomy
                </GatedButton>
              </Stack>

              {/* ── Full definition ─────────────────────────────────── */}
              <Stack spacing={0.5}>
                <Typography variant="overline" sx={{ lineHeight: 1 }}>
                  Full definition
                </Typography>
                <Typography
                  component="pre"
                  variant="body2"
                  sx={{
                    m: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontSize: '0.72rem',
                    bgcolor: theme.palette.background.default,
                    p: 1,
                    borderRadius: 1,
                  }}
                >
                  {JSON.stringify(detail.definition, null, 2)}
                </Typography>
              </Stack>
            </Stack>
          ) : null}
        </Box>
      </Drawer>
    </PageContainer>
  );
}

function DiffPanel({ diff }) {
  const theme = useTheme();

  if (!diff) {
    return (
      <Typography variant="body2" color="text.secondary">
        No diff loaded.
      </Typography>
    );
  }
  if (diff.diff === null) {
    return (
      <Typography variant="body2" color="text.secondary">
        No active version to diff against.
      </Typography>
    );
  }

  const lines = flattenDiff(diff.added, diff.removed, diff.changed);
  if (lines.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No differences vs active.
      </Typography>
    );
  }

  return (
    <Stack spacing={0.5}>
      {diff.from_version && diff.to_version ? (
        <Typography variant="caption" color="text.secondary">
          {diff.from_version} → {diff.to_version}
        </Typography>
      ) : null}
      {lines.map((line, i) => {
        const color =
          line.kind === 'added'
            ? theme.palette.success.main
            : line.kind === 'removed'
              ? theme.palette.error.main
              : theme.palette.warning.main;
        const text =
          line.kind === 'changed'
            ? `${line.from === undefined ? '—' : valueText(line.from)} → ${line.to === undefined ? '—' : valueText(line.to)}`
            : valueText(line.value);
        return (
          <Typography
            key={i}
            component="pre"
            variant="body2"
            sx={{
              m: 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: '0.72rem',
              color,
              textDecorationLine: line.kind === 'removed' ? 'line-through' : 'none',
            }}
          >
            {line.kind === 'added' ? '+ ' : line.kind === 'removed' ? '- ' : '~ '}
            {line.label}: {text}
          </Typography>
        );
      })}
    </Stack>
  );
}
