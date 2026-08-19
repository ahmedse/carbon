// src/shell/AIActionRunner.jsx
// Sprint W2-A — clustered execution timeline (Copilot/Cursor/Cline shape,
// design §2.5): one user action = one collapsible turn cluster; each
// tool/MCP/agent step = one collapsible card (status icon + name + status
// chip; args/result body). Frames arrive over SSE from `runActionStream`
// (W1-A backend seam). Failure/stop lives INSIDE the card — never a red
// full-width banner. Staged host mutations render a confirm gate
// (RULE_21 — never a silent write). RULE_8 tokens only; RULE_23 outcome
// copy only (no engine class names, no transport details).
import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import StopIcon from '@mui/icons-material/Stop';
import { useNotification } from '../components/NotificationProvider';
import {
  confirmToolExecution,
  declineToolExecution,
  runActionStream,
  stopGeneration,
} from '../api/aiWorkspace';

// ── Status copy + icons (RULE_23: outcome language, never internals) ──────
const STEP_STATUS = {
  running: { label: 'Running…', color: 'primary', icon: 'spinner' },
  completed: { label: 'Finished', color: 'success', icon: 'done' },
  failed: { label: 'Failed', color: 'error', icon: 'error' },
  stopped: { label: 'Stopped', color: 'warning', icon: 'stopped' },
  needs_confirmation: { label: 'Needs approval', color: 'warning', icon: 'help' },
  declined: { label: 'Declined', color: 'default', icon: 'stopped' },
};

function StepStatusIcon({ status }) {
  const meta = STEP_STATUS[status] || STEP_STATUS.running;
  if (meta.icon === 'spinner') return <CircularProgress size={12} thickness={6} sx={{ color: 'primary.main' }} />;
  if (meta.icon === 'done') return <CheckCircleOutlineIcon sx={{ fontSize: 15, color: 'success.main' }} />;
  if (meta.icon === 'error') return <ErrorOutlineIcon sx={{ fontSize: 15, color: 'error.main' }} />;
  if (meta.icon === 'help') return <HelpOutlineIcon sx={{ fontSize: 15, color: 'warning.main' }} />;
  return <StopCircleOutlinedIcon sx={{ fontSize: 15, color: 'warning.main' }} />;
}

StepStatusIcon.propTypes = { status: PropTypes.string };

function JsonBlock({ title, value }) {
  if (value === null || value === undefined) return null;
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return (
    <Box sx={{ mt: 0.5 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title}
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          mt: 0.25,
          p: 1,
          borderRadius: 1,
          bgcolor: 'action.hover',
          fontSize: '0.6875rem',
          lineHeight: 1.45,
          maxHeight: 200,
          overflow: 'auto', // wide output scrolls inside the card (§2.5.5)
          whiteSpace: 'pre',
        }}
      >
        {text}
      </Box>
    </Box>
  );
}

JsonBlock.propTypes = { title: PropTypes.string, value: PropTypes.any };

/**
 * Clustered execution timeline for one agent/tool run.
 *
 * @param {object} props
 * @param {string} props.token - JWT access token
 * @param {string|null} props.conversationId - anchor conversation UUID
 * @param {object|null} props.run - { runId, action_type, tool?, agent?, args?, verbosity }
 *   A new runId starts a fresh timeline (collapse state per-run, in-memory).
 * @param {function} [props.onPhaseChange] - (phase) => void, phase ∈ working|finished|stopped|error
 */
function AIActionRunner({ token, conversationId, run, onPhaseChange }) {
  const { notifyFromError } = useNotification();
  const [phase, setPhase] = useState('idle');
  const [turn, setTurn] = useState(null);
  const [steps, setSteps] = useState([]);
  const [turnExpanded, setTurnExpanded] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const updatePhase = (next) => {
    setPhase(next);
    onPhaseChange?.(next);
  };

  useEffect(() => {
    if (!run?.runId) return;
    let cancelled = false;
    setPhase('working');
    onPhaseChange?.('working');
    setTurn(null);
    setSteps([]);
    setTurnExpanded(true);
    setErrorMessage(null);

    const defaultExpanded = run.verbosity === 'full';
    const upsert = (patch) => {
      setSteps((prev) => {
        const idx = prev.findIndex((s) => s.step_id === patch.step_id);
        if (idx === -1) {
          return [
            ...prev,
            {
              step_id: patch.step_id,
              tool: '',
              category: 'tool',
              status: 'running',
              args: null,
              result: null,
              execution_id: null,
              expanded: defaultExpanded,
              ...patch,
            },
          ];
        }
        const next = [...prev];
        const cur = next[idx];
        let { result, args } = patch;
        // Streaming results accumulate when both chunks are strings.
        if (result !== undefined && typeof result === 'string' && typeof cur.result === 'string') {
          result = cur.result + result;
        }
        next[idx] = {
          ...cur,
          ...patch,
          result: result !== undefined ? result : cur.result,
          args: args !== undefined ? args : cur.args,
        };
        return next;
      });
    };

    runActionStream(
      token,
      conversationId,
      {
        action_type: run.action_type,
        tool: run.tool,
        agent: run.agent,
        args: run.args,
        verbosity: run.verbosity,
      },
      {
        onTurnStart: (frame) => {
          if (cancelled) return;
          setTurn({ turn_id: frame.turn_id, label: frame.label, verbosity: frame.verbosity, status: null, summary: null });
        },
        onToolStart: (frame) => {
          if (cancelled) return;
          upsert({ step_id: frame.step_id, tool: frame.tool, category: frame.category, status: 'running' });
        },
        onToolArg: (frame) => {
          if (cancelled) return;
          upsert({ step_id: frame.step_id, args: frame.args });
        },
        onToolResult: (frame) => {
          if (cancelled) return;
          upsert({ step_id: frame.step_id, result: frame.result });
        },
        onToolEnd: (frame) => {
          if (cancelled) return;
          upsert({ step_id: frame.step_id, status: frame.status, execution_id: frame.execution_id ?? null });
        },
        onTurnEnd: (frame) => {
          if (cancelled) return;
          setTurn((prev) => ({ ...prev, status: frame.status, summary: frame.summary ?? null }));
          if (frame.status === 'stopped') updatePhase('stopped');
          else if (frame.status === 'failed') updatePhase('error');
          else updatePhase('finished');
        },
        onDone: () => {
          if (cancelled) return;
          updatePhase('finished');
        },
        onStopped: () => {
          if (cancelled) return;
          updatePhase('stopped');
        },
        onError: (message) => {
          if (cancelled) return;
          setErrorMessage(message || 'Run failed');
          updatePhase('error');
        },
      },
    );

    return () => {
      cancelled = true;
    };
    // A new runId is a fresh timeline; token/conversationId are settled by
    // the parent before `run` is set (lazy conversation creation).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.runId]);

  // ── Abort: flip to stopped immediately, request cancellation (idempotent).
  const handleStop = async () => {
    if (phaseRef.current !== 'working') return;
    updatePhase('stopped');
    try {
      await stopGeneration(token, conversationId);
    } catch {
      // The terminal stopped/error frame decides; stop is idempotent.
    }
  };

  // ── Confirm gate (RULE_21): staged mutations never run silently.
  const handleConfirm = async (executionId) => {
    setConfirmingId(executionId);
    try {
      await confirmToolExecution(token, conversationId, executionId);
      setSteps((prev) =>
        prev.map((s) => (s.execution_id === executionId ? { ...s, status: 'completed' } : s)),
      );
    } catch (err) {
      notifyFromError(err, 'Could not approve the action');
      setSteps((prev) =>
        prev.map((s) => (s.execution_id === executionId ? { ...s, status: 'failed' } : s)),
      );
    } finally {
      setConfirmingId(null);
    }
  };

  const handleDecline = async (executionId) => {
    setConfirmingId(executionId);
    try {
      await declineToolExecution(token, conversationId, executionId);
      setSteps((prev) =>
        prev.map((s) => (s.execution_id === executionId ? { ...s, status: 'declined' } : s)),
      );
    } catch (err) {
      notifyFromError(err, 'Could not decline the action');
    } finally {
      setConfirmingId(null);
    }
  };

  if (!run?.runId) {
    return (
      <Paper variant="outlined" sx={{ p: 1.5, bgcolor: 'background.paper' }}>
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          Run an agent or tool from the tabs above — progress appears here.
        </Typography>
      </Paper>
    );
  }

  const doneSteps = steps.length;
  const finishedCopy =
    phase === 'stopped' ? 'Stopped by you'
      : phase === 'error' ? 'Run failed'
        : phase === 'finished' ? `Finished · ${doneSteps} tool${doneSteps === 1 ? '' : 's'}`
          : 'Working…';

  return (
    <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
      {/* ── L1 turn cluster header ── */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1.25, py: 0.875, cursor: 'pointer', borderBottom: 1, borderColor: 'divider' }}
        onClick={() => setTurnExpanded((v) => !v)}
      >
        <IconButton size="small" sx={{ p: 0, m: 0 }} aria-label={turnExpanded ? 'Collapse run' : 'Expand run'}>
          {turnExpanded ? <ExpandMoreIcon sx={{ fontSize: 16 }} /> : <ChevronRightIcon sx={{ fontSize: 16 }} />}
        </IconButton>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {turn?.label || (run.action_type === 'agent' ? 'Running agent…' : 'Running tool…')}
          </Typography>
        </Box>
        <Chip
          size="small"
          label={finishedCopy}
          color={phase === 'error' ? 'error' : phase === 'stopped' ? 'warning' : phase === 'finished' ? 'success' : 'primary'}
          sx={{ height: 20, fontSize: '0.625rem' }}
        />
        {phase === 'working' && (
          <Tooltip title="Stop the run">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                handleStop();
              }}
              aria-label="Stop run"
              sx={{ p: 0.375 }}
            >
              <StopIcon sx={{ fontSize: 15, color: 'error.main' }} />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {/* ── L2 step cards ── */}
      <Collapse in={turnExpanded} unmountOnExit>
        <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {steps.length === 0 && phase === 'working' && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              Starting…
            </Typography>
          )}
          {steps.map((step) => {
            const meta = STEP_STATUS[step.status] || STEP_STATUS.running;
            const showBody = step.expanded || step.status === 'needs_confirmation' || step.status === 'failed' || step.status === 'stopped';
            return (
              <Paper key={step.step_id} variant="outlined" sx={{ borderRadius: 1 }}>
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={0.75}
                  sx={{ px: 0.875, py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                  onClick={() =>
                    setSteps((prev) => prev.map((s) => (s.step_id === step.step_id ? { ...s, expanded: !s.expanded } : s)))
                  }
                >
                  <IconButton size="small" sx={{ p: 0, m: 0 }} aria-label={`Toggle ${step.tool || 'step'} details`}>
                    {step.expanded ? <ExpandMoreIcon sx={{ fontSize: 15 }} /> : <ChevronRightIcon sx={{ fontSize: 15 }} />}
                  </IconButton>
                  <StepStatusIcon status={step.status} />
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 500, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {step.tool || 'Step'}
                  </Typography>
                  <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 18, fontSize: '0.625rem' }} />
                </Stack>

                {/* Bodies render conditionally — instant show/hide, and
                    failure/stop state always lives inside the card. */}
                {showBody && (
                  <Box sx={{ px: 1.25, pb: 0.875 }}>
                    {step.args !== null && step.args !== undefined && <JsonBlock title="Input" value={step.args} />}
                    {step.result !== null && step.result !== undefined && <JsonBlock title="Output" value={step.result} />}

                    {step.status === 'needs_confirmation' && (
                      <Box sx={{ mt: 0.75, p: 1, borderRadius: 1, bgcolor: 'warning.soft' }}>
                        <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.5 }}>
                          This action writes to Carbon. Approve it to run, or decline to skip it.
                        </Typography>
                        <Stack direction="row" spacing={1}>
                          <Button
                            size="small"
                            variant="contained"
                            disabled={confirmingId === step.execution_id}
                            onClick={() => handleConfirm(step.execution_id)}
                            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                          >
                            {confirmingId === step.execution_id ? 'Approving…' : 'Approve'}
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            disabled={confirmingId === step.execution_id}
                            onClick={() => handleDecline(step.execution_id)}
                            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                          >
                            Decline
                          </Button>
                        </Stack>
                      </Box>
                    )}

                    {step.status === 'stopped' && (
                      <Typography variant="caption" color="warning.main" sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem' }}>
                        Stopped by you.
                      </Typography>
                    )}
                    {step.status === 'failed' && (
                      <Typography variant="caption" color="error.main" sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem' }}>
                        This step failed.
                      </Typography>
                    )}
                  </Box>
                )}
              </Paper>
            );
          })}

          {/* Stream-level failure lives inline, not as a banner (§2.5.4). */}
          {phase === 'error' && errorMessage && (
            <Box sx={{ px: 0.5, py: 0.25 }}>
              <Typography variant="caption" color="error.main" sx={{ fontSize: '0.6875rem' }}>
                {errorMessage}
              </Typography>
            </Box>
          )}
          <Divider sx={{ mx: 0.5 }} />
          <Typography variant="caption" color="text.disabled" sx={{ px: 0.5, fontSize: '0.625rem' }}>
            {run.action_type === 'agent' ? `Agent · ${run.agent || ''}` : `Tool · ${run.tool || ''}`} — {run.verbosity} detail
          </Typography>
        </Box>
      </Collapse>
    </Paper>
  );
}

AIActionRunner.propTypes = {
  token: PropTypes.string,
  conversationId: PropTypes.string,
  run: PropTypes.shape({
    runId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
    action_type: PropTypes.oneOf(['tool', 'agent']).isRequired,
    tool: PropTypes.string,
    agent: PropTypes.string,
    args: PropTypes.object,
    verbosity: PropTypes.oneOf(['concise', 'full']),
  }),
  onPhaseChange: PropTypes.func,
};

export default AIActionRunner;
