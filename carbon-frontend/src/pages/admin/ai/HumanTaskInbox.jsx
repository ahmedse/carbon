// src/pages/admin/ai/HumanTaskInbox.jsx
// Route /admin/ai/inbox — P3-09 Human Task Inbox. Dense list of pending
// human-approval tasks + a detail drawer (consequence, before/after, evidence,
// reversibility, required authority, expiry, alternatives) + Approve/Decline
// actions. Subscribes to the SSE stream and prepends newly-created tasks.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiInbox.js);
// RULE_16 grounded states (loading spinner, offline, empty).
import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckIcon from '@mui/icons-material/Check';
import BlockIcon from '@mui/icons-material/Block';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import {
  approveTask,
  declineTask,
  listInbox,
  subscribeInboxStream,
} from '../../../api/aiInbox';

/** Format an ISO timestamp defensively (em-dash when missing/invalid). */
function formatTimestamp(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

/** Pending → warning, approved → success, otherwise muted/error. */
function statusColor(status, theme) {
  if (status === 'approved') return theme.palette.success.main;
  if (status === 'declined' || status === 'expired' || status === 'cancelled') {
    return theme.palette.error.main;
  }
  return theme.palette.warning.main;
}

/** Pretty-print a JSON-ish value (dict/list/string) in a dense block. */
function JsonBlock({ label, value }) {
  const theme = useTheme();
  const text =
    value === null || value === undefined
      ? '—'
      : typeof value === 'string'
        ? value
        : JSON.stringify(value, null, 2);
  return (
    <Stack spacing={0.5}>
      <Typography variant="overline" sx={{ lineHeight: 1 }}>
        {label}
      </Typography>
      <Typography
        component="pre"
        variant="body2"
        sx={{
          m: 0,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: '0.75rem',
          bgcolor: theme.palette.background.default,
          p: 1,
          borderRadius: 1,
        }}
      >
        {text}
      </Typography>
    </Stack>
  );
}

export default function HumanTaskInbox() {
  useDocumentTitle('Human Task Inbox');
  const theme = useTheme();
  const { token } = useAuth();

  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);
  const [actioning, setActioning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listInbox(token, { status: 'pending' });
      setTasks(Array.isArray(rows) ? rows : []);
      setOffline(false);
    } catch {
      setTasks([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  // SSE — prepend newly-created tasks (dedupe by id).
  useEffect(() => {
    const stop = subscribeInboxStream(token, {
      onTask: (task) => {
        if (!task) return;
        setTasks((prev) => {
          if (prev.some((t) => t.id === task.id)) return prev;
          return [task, ...prev];
        });
      },
      onError: () => {},
    });
    return stop;
  }, [token]);

  const act = useCallback(
    async (id, kind) => {
      setActioning(true);
      try {
        const fn = kind === 'approve' ? approveTask : declineTask;
        const updated = await fn(token, id);
        setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
        setSelected((cur) => (cur && cur.id === id ? updated : cur));
      } catch {
        // keep the row; a 403 (insufficient authority) is left as-is
      } finally {
        setActioning(false);
      }
    },
    [token],
  );

  const pending = tasks.filter((t) => t.status === 'pending');

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h5">Human Task Inbox</Typography>
          <Button startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
            Refresh
          </Button>
        </Stack>

        {offline && (
          <Paper sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
            <CloudOffIcon color="disabled" />
            <Typography variant="body2">
              Inbox is temporarily unavailable.
            </Typography>
          </Paper>
        )}

        {loading ? (
          <Stack alignItems="center" sx={{ py: 6 }}>
            <CircularProgress />
          </Stack>
        ) : pending.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No pending tasks.
            </Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Capability</TableCell>
                  <TableCell>Title</TableCell>
                  <TableCell>Object</TableCell>
                  <TableCell>Authority</TableCell>
                  <TableCell>Expires</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pending.map((task) => (
                  <TableRow
                    key={task.id}
                    hover
                    onClick={() => setSelected(task)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>
                      <Chip size="small" label={task.capability} variant="outlined" />
                    </TableCell>
                    <TableCell>{task.title || '—'}</TableCell>
                    <TableCell>{task.object_id || '—'}</TableCell>
                    <TableCell>{task.required_authority || '—'}</TableCell>
                    <TableCell>{formatTimestamp(task.expires_at)}</TableCell>
                    <TableCell align="right">
                      <Stack
                        direction="row"
                        spacing={1}
                        justifyContent="flex-end"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          size="small"
                          variant="contained"
                          startIcon={<CheckIcon />}
                          disabled={actioning}
                          onClick={() => act(task.id, 'approve')}
                        >
                          Approve
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          startIcon={<BlockIcon />}
                          disabled={actioning}
                          onClick={() => act(task.id, 'decline')}
                        >
                          Decline
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Stack>

      <Drawer anchor="right" open={Boolean(selected)} onClose={() => setSelected(null)}>
        {selected && (
          <Box sx={{ width: 420, maxWidth: '100vw', p: 2 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
              <Typography variant="h6">Task Detail</Typography>
              <IconButton onClick={() => setSelected(null)}>
                <CloseIcon />
              </IconButton>
            </Stack>
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  size="small"
                  label={selected.status}
                  variant="outlined"
                  sx={{
                    color: statusColor(selected.status, theme),
                    borderColor: statusColor(selected.status, theme),
                  }}
                />
                <Chip size="small" label={selected.capability} variant="outlined" />
              </Stack>
              <Typography variant="subtitle1">{selected.title || '—'}</Typography>
              <Typography variant="body2">{selected.description || '—'}</Typography>
              <Divider />
              <JsonBlock label="Before" value={selected.before_state} />
              <JsonBlock label="After" value={selected.after_state} />
              <JsonBlock label="Evidence" value={selected.evidence} />
              <JsonBlock label="Object Revisions" value={selected.object_revisions} />
              <Typography variant="body2">
                <strong>Reversibility:</strong> {selected.reversibility || '—'}
              </Typography>
              <Typography variant="body2">
                <strong>Required authority:</strong> {selected.required_authority || '—'}
              </Typography>
              <Typography variant="body2">
                <strong>Expires:</strong> {formatTimestamp(selected.expires_at)}
              </Typography>
              <JsonBlock label="Alternatives" value={selected.alternatives} />
              <Stack direction="row" spacing={1}>
                <Button
                  fullWidth
                  variant="contained"
                  startIcon={<CheckIcon />}
                  disabled={actioning || selected.status !== 'pending'}
                  onClick={() => act(selected.id, 'approve')}
                >
                  Approve
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  color="error"
                  startIcon={<BlockIcon />}
                  disabled={actioning || selected.status !== 'pending'}
                  onClick={() => act(selected.id, 'decline')}
                >
                  Decline
                </Button>
              </Stack>
            </Stack>
          </Box>
        )}
      </Drawer>
    </PageContainer>
  );
}
