// src/pages/admin/ai/RunTimelinePanel.jsx
// Route /admin/ai/runs — AI Admin OBSERVE + MANAGE surface: cross-user run
// timeline for admins. Enter a run/plan id → GET /ai/runs/{id}/timeline/
// renders the ordered event log (RunTimeline). Resume + Replay are RULE_21
// consent-gated (confirm Dialog; the API is NOT called until the admin
// confirms). No run-list API exists on the backend, so the id is entered
// manually (see TASK-RESULTS W3-G assumptions).
//
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiCatalog.js);
// RULE_23: replay is staged outcome copy — no internal staging detail.
import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import PlayArrowOutlinedIcon from '@mui/icons-material/PlayArrowOutlined';
import ReplayOutlinedIcon from '@mui/icons-material/ReplayOutlined';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import RunTimeline from '../../../components/graph/RunTimeline';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { getRunTimeline, resumeRun, replayRun, compareRuns } from '../../../api/aiCatalog';

export default function RunTimelinePanel() {
  useDocumentTitle('Run Timeline');
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [runId, setRunId] = useState('');
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);
  const [searched, setSearched] = useState(false);

  // Run comparison state (Gap #4).
  const [runBId, setRunBId] = useState('');
  const [compare, setCompare] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareOffline, setCompareOffline] = useState(false);
  const [compareSearched, setCompareSearched] = useState(false);

  // RULE_21 confirm gates — the action executes only after explicit consent.
  const [confirmAction, setConfirmAction] = useState(null); // 'resume' | 'replay'
  const [acting, setActing] = useState(false);

  const fetchTimeline = async (id) => {
    setLoading(true);
    setOffline(false);
    setSearched(true);
    try {
      const payload = await getRunTimeline(token, id);
      setTimeline(payload);
    } catch {
      setTimeline(null);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  };

  const onLookup = () => {
    const id = runId.trim();
    if (!id) return;
    fetchTimeline(id);
  };

  const fetchCompare = async (a, b) => {
    setCompareLoading(true);
    setCompareOffline(false);
    setCompareSearched(true);
    try {
      const payload = await compareRuns(token, a, b);
      setCompare(payload);
    } catch {
      setCompare(null);
      setCompareOffline(true);
    } finally {
      setCompareLoading(false);
    }
  };

  const onCompare = () => {
    const a = runId.trim();
    const b = runBId.trim();
    if (!a || !b) return;
    fetchCompare(a, b);
  };

  const onConfirm = async () => {
    const id = runId.trim();
    if (!id || !confirmAction) return;
    setActing(true);
    try {
      if (confirmAction === 'resume') {
        await resumeRun(token, id);
        notify({ message: `Run ${id} resumed — crash-safe reconciliation done.`, type: 'success' });
      } else {
        await replayRun(token, id);
        notify({ message: `Replay staged for run ${id} — nothing re-executed.`, type: 'success' });
      }
      setConfirmAction(null);
      await fetchTimeline(id);
    } catch (err) {
      notifyFromError(err, `Could not ${confirmAction} run ${id}.`);
    } finally {
      setActing(false);
    }
  };

  const eventCount = Array.isArray(timeline?.events) ? timeline.events.length : 0;
  const statusLabel = timeline?.status ?? '';

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ width: '100%', maxWidth: 1080 }}>
        <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700 }}>
          Run Timeline
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          Cross-user run observation for admins. Enter a run id to see its ordered event log
          (plan lifecycle, per-step state, resume/replay provenance). Resume and replay are
          explicit, admin-gated actions.
        </Typography>

        {/* Run id entry */}
        <Paper variant="outlined" sx={{ p: 1.25 }}>
          <Stack direction="row" spacing={1} alignItems="flex-start" flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="Run / plan id"
              placeholder="e.g. 7f3a9c21-…"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onLookup();
              }}
              sx={{ flex: 1, maxWidth: 300, '& .MuiInputBase-input': { fontSize: '0.8125rem' } }}
            />
            <Button
              variant="contained"
              size="small"
              onClick={onLookup}
              disabled={loading || !runId.trim()}
              sx={{ fontSize: '0.75rem' }}
            >
              Load timeline
            </Button>
            {timeline && !loading && (
              <Button
                size="small"
                startIcon={<PlayArrowOutlinedIcon sx={{ fontSize: '0.9375rem' }} />}
                disabled={acting}
                onClick={() => setConfirmAction('resume')}
                sx={{ fontSize: '0.75rem' }}
              >
                Resume
              </Button>
            )}
            {timeline && !loading && (
              <Button
                size="small"
                startIcon={<ReplayOutlinedIcon sx={{ fontSize: '0.9375rem' }} />}
                disabled={acting}
                onClick={() => setConfirmAction('replay')}
                sx={{ fontSize: '0.75rem' }}
              >
                Replay
              </Button>
            )}
          </Stack>
        </Paper>

        {/* Run comparison entry (Gap #4) */}
        <Paper variant="outlined" sx={{ p: 1.25 }}>
          <Stack direction="row" spacing={1} alignItems="flex-start" flexWrap="wrap" useFlexGap>
            <TextField
              size="small"
              label="Run A"
              placeholder="e.g. 7f3a9c21-…"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              sx={{ flex: 1, minWidth: 200, maxWidth: 300, '& .MuiInputBase-input': { fontSize: '0.8125rem' } }}
            />
            <TextField
              size="small"
              label="Run B"
              placeholder="e.g. 9c21f3a7-…"
              value={runBId}
              onChange={(e) => setRunBId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onCompare();
              }}
              sx={{ flex: 1, minWidth: 200, maxWidth: 300, '& .MuiInputBase-input': { fontSize: '0.8125rem' } }}
            />
            <Button
              size="small"
              startIcon={<CompareArrowsIcon sx={{ fontSize: '0.9375rem' }} />}
              onClick={onCompare}
              disabled={compareLoading || !runId.trim() || !runBId.trim()}
              sx={{ fontSize: '0.75rem' }}
            >
              Compare
            </Button>
          </Stack>
        </Paper>

        {loading && (
          <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <CircularProgress size={28} />
          </Paper>
        )}

        {!loading && searched && offline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Timeline unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                No timeline found for run <strong>{runId.trim()}</strong>. Check the id — the
                backend returns 404 when the run is not accessible or does not exist.
              </Typography>
            </Stack>
          </Paper>
        )}

        {!loading && timeline && (
          <Box>
            {statusLabel && eventCount === 0 && (
              <Alert severity="info" sx={{ mb: 1, fontSize: '0.75rem' }}>
                Run {timeline.run_id ?? runId.trim()} is {statusLabel} — no events recorded yet.
              </Alert>
            )}
            <RunTimeline timeline={timeline} />
          </Box>
        )}

        {compareLoading && (
          <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <CircularProgress size={28} />
          </Paper>
        )}

        {!compareLoading && compareSearched && compareOffline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Comparison unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                One or both runs were not accessible (or do not exist). Check the ids — the
                backend returns 404 when a run is not accessible.
              </Typography>
            </Stack>
          </Paper>
        )}

        {!compareLoading && compare && (
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="body2" fontWeight={700} sx={{ fontSize: '0.8125rem' }}>
                  Run comparison
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  A: {compare.a.status} · {compare.a.step_count} step(s)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  B: {compare.b.status} · {compare.b.step_count} step(s)
                </Typography>
                {compare.status_changed && (
                  <Alert severity="info" sx={{ py: 0, fontSize: '0.75rem' }}>
                    Run status differs ({compare.a.status} vs {compare.b.status})
                  </Alert>
                )}
              </Stack>

              {(!compare.diverged_steps || compare.diverged_steps.length === 0) ? (
                <Alert severity="success" sx={{ fontSize: '0.75rem' }}>
                  No diverging steps — both ledgers match.
                </Alert>
              ) : (
                <Stack spacing={0.75}>
                  <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem' }}>
                    Diverging steps ({compare.diverged_steps.length})
                  </Typography>
                  {compare.diverged_steps.map((d) => (
                    <Paper key={d.step_index} variant="outlined" sx={{ p: 1 }}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem' }}>
                          Step {d.step_index}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem', flex: 1, minWidth: 160 }}>
                          {d.intent || '—'}
                        </Typography>
                        {d.only_in ? (
                          <Alert severity="warning" sx={{ py: 0, fontSize: '0.75rem' }}>
                            only in run {d.only_in.toUpperCase()}
                          </Alert>
                        ) : (
                          <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
                            {d.a_status} <CompareArrowsIcon sx={{ fontSize: '0.75rem', verticalAlign: 'middle' }} /> {d.b_status}
                          </Typography>
                        )}
                      </Stack>
                      {(d.a_error || d.b_error) && (
                        <Typography variant="caption" color="error" sx={{ fontSize: '0.6875rem', display: 'block', mt: 0.5 }}>
                          {d.a_error ? `A: ${d.a_error}` : ''}
                          {d.a_error && d.b_error ? ' · ' : ''}
                          {d.b_error ? `B: ${d.b_error}` : ''}
                        </Typography>
                      )}
                    </Paper>
                  ))}
                </Stack>
              )}
            </Stack>
          </Paper>
        )}

        {/* RULE_21 consent dialog — API is not called until this is confirmed. */}
        <Dialog
          open={Boolean(confirmAction)}
          onClose={() => !acting && setConfirmAction(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ fontSize: '1rem', fontWeight: 700 }}>
            {confirmAction === 'replay' ? 'Confirm replay staging' : 'Confirm resume'}
          </DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ fontSize: '0.8125rem' }}>
              {confirmAction === 'replay' ? (
                <>
                  This stages a deterministic replay of run <strong>{runId.trim()}</strong> from the
                  step ledger + trajectory rows. Replay is read-only: it produces a timeline and
                  <strong> never re-executes</strong> anything.
                </>
              ) : (
                <>
                  This crash-safe resume reconciles run <strong>{runId.trim()}</strong> (marks
                  running / awaiting-approval steps correctly, skips completed steps) and re-enters
                  execution.
                </>
              )}
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button size="small" onClick={() => setConfirmAction(null)} disabled={acting} sx={{ fontSize: '0.75rem' }}>
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              color={confirmAction === 'replay' ? 'warning' : 'primary'}
              onClick={onConfirm}
              disabled={acting}
              sx={{ fontSize: '0.75rem' }}
            >
              {acting ? 'Working…' : confirmAction === 'replay' ? 'Stage replay' : 'Resume run'}
            </Button>
          </DialogActions>
        </Dialog>
      </Stack>
    </PageContainer>
  );
}
