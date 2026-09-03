// src/shell/AITaskPanel.jsx
// Sprint 23 W3-B + W3-F — agentic task orchestration surface: a user brief
// becomes a reviewable plan (W3-A backend) that runs only after the plan-level
// consent gate (RULE_21), streams step frames over SSE, pauses at any step
// that writes to Carbon (per-step Approve/Decline), and lands in a durable
// audit ledger. W3-F adds the plan controls (edit / pause / resume / fork)
// wired to W3-C, each edit passing through the diff-review consent gate, and
// a live plan DAG that polls the plan while a run is active. One activity
// icon, two internal tabs persisted to localStorage (RULE_17). Outcome copy
// only (RULE_23); theme tokens only (RULE_8); compact density throughout.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import LeaderboardOutlinedIcon from '@mui/icons-material/LeaderboardOutlined';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import StopIcon from '@mui/icons-material/Stop';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { useTranslation } from 'react-i18next';
import {
  approvePlan,
  confirmPlanStep,
  createSchedule,
  declinePlan,
  declinePlanStep,
  deletePlan,
  deleteSchedule,
  dispatchSubagent,
  downloadArtifact,
  editPlan,
  editPlanStep,
  editSchedule,
  forkPlan,
  getPlan,
  getPlanLedger,
  listPlanArtifacts,
  listPlans,
  listPlanTemplates,
  listSchedules,
  listSubagents,
  instantiatePlanTemplate,
  pausePlan,
  pauseSchedule,
  promotePlanTemplate,
  resumePlanStream,
  runPlanStream,
  stopPlan,
} from '../api/aiWorkspace';
import ScheduleDialog from '../components/ai/ScheduleDialog';
import ScheduleList from '../components/ai/ScheduleList';
import SystemDialog from '../components/SystemDialog';
import { buildPlanPhases, summarizePlanDiff } from '../utils/planGraph';
import { agentRoleLabel, toolLabel } from './aiTaskStatus';
import AITaskPlanCard from './AITaskPlanCard';
import AITaskAuditCard from './AITaskAuditCard';
import SubagentResultCard from './SubagentResultCard';
import PlanDiffReviewDialog from './PlanDiffReviewDialog';
import StepEditDialog from './StepEditDialog';
import DiscoveryComposer from './DiscoveryComposer';
import StepOutputRenderer, { ArtifactCard } from '../components/ai/StepOutputRenderer';

dayjs.extend(utc);
dayjs.extend(timezone);

const TASK_TAB_KEY = 'carbon-ai-task-tab';
const PROJECT_TIMEZONE = 'Africa/Cairo';

// W5-D — estimated token cost uses a single DeepSeek V4-Flash blended rate
// (USD per 1M tokens). Kept as a named constant until a server-side rate
// config lands (no hardcoded secrets; this is a public list price).
const LLM_COST_PER_1M_TOKENS = 0.28;

function formatWhen(value) {
  if (!value) return '';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.tz(PROJECT_TIMEZONE).format('MMM D, YYYY · HH:mm') : '';
}

// W5-D — human duration for the Monitor tab (elapsed, never negative).
function formatDuration(startIso, endIso) {
  if (!startIso) return '—';
  const start = dayjs(startIso);
  if (!start.isValid()) return '—';
  const end = endIso ? dayjs(endIso) : dayjs();
  if (!end.isValid()) return '—';
  const secs = Math.max(0, end.diff(start, 'second'));
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${mins % 60}m`;
}

// W5-D — compact USD rendering for estimated cost.
function formatCost(usd) {
  if (usd == null || Number.isNaN(usd)) return '—';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

// W5-D — emoji file icon by mime_type (RULE_23 outcome copy only).
function artifactIcon(mime) {
  const m = (mime || '').toLowerCase();
  if (m.includes('spreadsheet') || m.includes('excel') || m.includes('xlsx') || m.includes('csv')) return '📊';
  if (m.includes('json')) return '🗄';
  if (m.includes('pdf') || m.includes('word') || m.includes('doc')) return '📄';
  return '📁';
}

// W5-D — a mime type is inline-previewable when its text can be read as lines.
function isPreviewableMime(mime) {
  const m = (mime || '').toLowerCase();
  return /json|csv|text|plain|markdown|xml|yaml|yml/.test(m);
}

// W5-D — human file size for the Results artifact cards.
function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(bytes)) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// W5-D — trigger a browser download for an in-memory blob (Share/Export).
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// W5-A (ADR-0014) — panel run phase + plan status → workspace-level lifecycle
// state consumed by the header safety-contract text (ADR-0014 §4).
// phase: {idle,working,paused,finished,stopped,error} + plan.status
//   → {idle,plan_pending,running,consent_needed,done,error}
function deriveLifecycleState(phase, planStatus) {
  switch (phase) {
    case 'working': return 'running';
    case 'paused': return 'consent_needed';
    case 'finished': return 'done';
    case 'error': return 'error';
    case 'stopped': return 'idle';
    default: break;
  }
  switch (planStatus) {
    case 'pending_approval':
    case 'discovering': return 'plan_pending';
    case 'paused': return 'consent_needed';
    case 'running': return 'running';
    case 'completed': return 'done';
    case 'failed': return 'error';
    default: return 'idle';
  }
}

// ── Step card — one planned step, live status, consent gate ──────────────
const STEP_STATUS_ICON = {
  running: { label: 'Running…', color: 'primary', icon: 'spinner' },
  completed: { label: 'Finished', color: 'success', icon: 'done' },
  failed: { label: 'Failed', color: 'error', icon: 'error' },
  skipped: { label: 'Skipped', color: 'default', icon: 'stopped' },
  awaiting_approval: { label: 'Needs approval', color: 'warning', icon: 'help' },
};

function StepStatusIcon({ status }) {
  const meta = STEP_STATUS_ICON[status] || { icon: 'spinner' };
  if (meta.icon === 'spinner') return <CircularProgress size={12} thickness={6} sx={{ color: 'primary.main' }} />;
  if (meta.icon === 'done') return <CheckCircleOutlineIcon sx={{ fontSize: 15, color: 'success.main' }} />;
  if (meta.icon === 'error') return <CloudOffIcon sx={{ fontSize: 15, color: 'error.main' }} />;
  if (meta.icon === 'help') return <HelpOutlineIcon sx={{ fontSize: 15, color: 'warning.main' }} />;
  return <StopCircleOutlinedIcon sx={{ fontSize: 15, color: 'warning.main' }} />;
}

StepStatusIcon.propTypes = { status: PropTypes.string };

// W5-C — collapsible "Input parameters" section (key→value rows, not raw JSON).
function InputParams({ value }) {
  const [open, setOpen] = useState(false);
  if (value === null || value === undefined) return null;
  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const entries = isObject ? Object.entries(value) : null;
  if (entries && entries.length === 0) return null;
  if (!entries && String(value).length === 0) return null;

  return (
    <Box sx={{ mt: 0.5 }}>
      <Button
        size="small"
        color="inherit"
        onClick={() => setOpen((v) => !v)}
        endIcon={open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        sx={{ fontSize: '0.625rem', textTransform: 'none', px: 0, minWidth: 0 }}
      >
        Input parameters
      </Button>
      <Collapse in={open}>
        {entries ? (
          <Stack spacing={0.25} sx={{ mt: 0.5 }}>
            {entries.map(([key, val]) => (
              <Box key={key} sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
                <Typography
                  variant="caption"
                  sx={{
                    fontSize: '0.625rem',
                    fontWeight: 600,
                    color: 'text.secondary',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    minWidth: 88,
                    flexShrink: 0,
                  }}
                >
                  {key.replace(/_/g, ' ')}
                </Typography>
                <Typography sx={{ fontSize: '0.6875rem', wordBreak: 'break-word', minWidth: 0 }}>
                  {typeof val === 'string' ? val : JSON.stringify(val)}
                </Typography>
              </Box>
            ))}
          </Stack>
        ) : (
          <Typography sx={{ fontSize: '0.6875rem', mt: 0.5, wordBreak: 'break-word' }}>
            {String(value)}
          </Typography>
        )}
      </Collapse>
    </Box>
  );
}

InputParams.propTypes = { value: PropTypes.any };

function StepCard({ step, phaseName, confirming, onConfirm, onDecline }) {
  const [open, setOpen] = useState(true);
  const meta = STEP_STATUS_ICON[step.status] || { label: 'Pending', color: 'default' };
  const showBody = open || step.status === 'awaiting_approval' || step.status === 'failed';

  return (
    <Paper variant="outlined" sx={{ borderRadius: 1 }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.75}
        sx={{ px: 0.875, py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
        onClick={() => setOpen((v) => !v)}
      >
        <IconButton size="small" sx={{ p: 0, m: 0 }} aria-label={`Toggle step ${step.step_id} details`}>
          {open ? <ExpandMoreIcon sx={{ fontSize: 15 }} /> : <ChevronRightIcon sx={{ fontSize: 15 }} />}
        </IconButton>
        <StepStatusIcon status={step.status} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {step.intent || `Step ${step.step_id}`}
        </Typography>
        {phaseName && (
          <Chip size="small" variant="outlined" label={phaseName} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        {step.agent_role && step.agent_role !== 'orchestrator' && (
          <Chip size="small" variant="outlined" color="secondary" label={`Agent ${step.step_id + 1} · ${agentRoleLabel(step.agent_role)}`} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        {step.tool_name && (
          <Chip size="small" variant="outlined" label={toolLabel(step.tool_name)} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
      </Stack>

      {showBody && (
        <Box sx={{ px: 1.25, pb: 0.875 }}>
          <InputParams value={step.tool_args} />
          <StepOutputRenderer outputType={step.output_type} value={step.tool_output} />
          {Array.isArray(step.artifacts) && step.artifacts.length > 0 && (
            <Stack spacing={0.5} sx={{ mt: 0.5 }}>
              {step.artifacts.map((artifact) => (
                <ArtifactCard key={artifact.id ?? artifact.name} value={artifact} />
              ))}
            </Stack>
          )}
          {step.verdict && step.verdict !== 'ok' && step.verdict !== 'accepted' && (
            <Typography variant="caption" color={step.verdict === 'veto' ? 'error.main' : 'text.secondary'} sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem' }}>
              Review: {step.verdict}
            </Typography>
          )}

          {step.status === 'awaiting_approval' && (
            <Box sx={{ mt: 0.75, p: 1, borderRadius: 1, bgcolor: 'warning.soft' }}>
              <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.5 }}>
                This action writes to Carbon. Approve it to run, or decline to skip it.
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="contained"
                  disabled={confirming}
                  onClick={() => onConfirm(step.step_id)}
                  sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                >
                  {confirming ? 'Approving…' : 'Approve'}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={confirming}
                  onClick={() => onDecline(step.step_id)}
                  sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                >
                  Decline
                </Button>
              </Stack>
            </Box>
          )}
          {step.status === 'skipped' && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem' }}>
              Skipped — not executed.
            </Typography>
          )}
          {step.status === 'failed' && (
            <Typography variant="caption" color="error.main" sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem' }}>
              {step.error || 'This step failed.'}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
}

StepCard.propTypes = {
  step: PropTypes.object.isRequired,
  phaseName: PropTypes.string,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
};

// W5-D — labelled metric for the Monitor grid (mirrors AITaskAuditCard Stat).
function MonitorMetric({ label, value }) {
  return (
    <Box sx={{ minWidth: 88 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
        {value}
      </Typography>
    </Box>
  );
}

MonitorMetric.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

// W5-D — one artifact in the Results grid: emoji icon by mime_type, name +
// size, Download, and an inline Preview (first 20 lines, collapsible) for
// text-like artifacts.
function ResultArtifactCard({ artifact, planId, token }) {
  const { notifyFromError } = useNotification();
  const [busy, setBusy] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLines, setPreviewLines] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  const name = artifact.name || 'artifact';
  const mime = artifact.mime_type || '';
  const previewable = isPreviewableMime(mime);

  const fetchBlobUrl = async () => downloadArtifact(token, planId, artifact.id);

  const handleDownload = async () => {
    setBusy(true);
    try {
      const url = await fetchBlobUrl();
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      notifyFromError(err, 'Could not download the artifact');
    } finally {
      setBusy(false);
    }
  };

  const handlePreview = async () => {
    if (previewOpen) {
      setPreviewOpen(false);
      return;
    }
    if (previewLines.length === 0) {
      setPreviewLoading(true);
      try {
        const url = await fetchBlobUrl();
        const text = await fetch(url).then((r) => r.text());
        URL.revokeObjectURL(url);
        setPreviewLines(text.split('\n').slice(0, 20));
      } catch (err) {
        notifyFromError(err, 'Could not preview the artifact');
      } finally {
        setPreviewLoading(false);
      }
    }
    setPreviewOpen(true);
  };

  return (
    <Paper variant="outlined" sx={{ p: 1 }}>
      <Stack direction="row" alignItems="flex-start" spacing={0.75}>
        <Typography component="span" sx={{ fontSize: '1rem', lineHeight: 1 }} aria-hidden>
          {artifactIcon(mime)}
        </Typography>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {name}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
            {artifact.size_bytes != null ? formatBytes(artifact.size_bytes) : (mime || 'Unknown size')}
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Button
            size="small"
            variant="outlined"
            disabled={busy}
            onClick={handleDownload}
            sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
          >
            {busy ? '…' : 'Download'}
          </Button>
          {previewable && (
            <Button
              size="small"
              variant="outlined"
              disabled={previewLoading}
              onClick={handlePreview}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
            >
              {previewLoading ? '…' : previewOpen ? 'Hide' : 'Preview'}
            </Button>
          )}
        </Stack>
      </Stack>
      <Collapse in={previewOpen}>
        <Box sx={{ mt: 0.75, p: 0.75, borderRadius: 1, bgcolor: 'background.default', maxHeight: 220, overflowY: 'auto' }}>
          {previewLines.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              No text to preview.
            </Typography>
          ) : (
            <Typography variant="caption" component="pre" sx={{ m: 0, fontSize: '0.6875rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {previewLines.join('\n')}
            </Typography>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}

ResultArtifactCard.propTypes = {
  artifact: PropTypes.object.isRequired,
  planId: PropTypes.string.isRequired,
  token: PropTypes.string,
};

/**
 * Agentic task orchestration panel.
 * @param {object} props
 * @param {string|null} props.conversationId - anchor conversation UUID
 * @param {string|null} props.focusPlanId - plan to auto-open (chat "Open in Tasks" jump)
 * @param {function} props.onFocusPlanConsumed - called once the focus is handled
 * @param {function} props.onLifecycleStateChange - W5-A: reports the workspace-level
 *   lifecycle state (idle|plan_pending|running|consent_needed|done|error) so the
 *   header can show the right safety-contract text (ADR-0014 §4).
 * @param {string} props.externalTab - W5-D: the workspace activity-bar view
 *   (tasks|monitor|results) that drives this panel's internal tab, so the
 *   Monitor and Results activity icons open the right internal view.
 */
function AITaskPanel({ conversationId, focusPlanId = null, onFocusPlanConsumed, onLifecycleStateChange, onSwitchToChat, externalTab = 'tasks' }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const { t } = useTranslation('ai');
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const notifyFromErrorRef = useRef(notifyFromError);
  notifyFromErrorRef.current = notifyFromError;

  const [tab, setTab] = useState(() => {
    try {
      return localStorage.getItem(TASK_TAB_KEY) || 'tasks';
    } catch {
      return 'tasks';
    }
  });

  // Task list + composer
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);

  // Selected plan detail + run state
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [runSteps, setRunSteps] = useState([]);
  const [phase, setPhase] = useState('idle'); // idle|working|paused|finished|stopped|error
  const [errorMessage, setErrorMessage] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [ledgerLoading, setLedgerLoading] = useState(false);

  // W5-D — Results tab artifacts (from GET .../artifacts/).
  const [artifacts, setArtifacts] = useState([]);
  const [artifactsLoading, setArtifactsLoading] = useState(false);

  // W3-F — plan controls: edits are gated by the diff-review consent dialog
  const [mutating, setMutating] = useState(false);
  const [editStepTarget, setEditStepTarget] = useState(null);
  const [diffReview, setDiffReview] = useState(null); // { diff, plan }

  // W3-D — plan templates (Gap #3)
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateDescription, setTemplateDescription] = useState('');
  const [templateSaving, setTemplateSaving] = useState(false);

  // W6-E F-29 — schedules (6th tab). `scheduleDialog` is null when closed, or
  // `{ template }` (create from a template row) / `{ schedule }` (edit).
  const [schedules, setSchedules] = useState([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [schedulesError, setSchedulesError] = useState(null);
  const [scheduleDialog, setScheduleDialog] = useState(null);
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deletingPlanId, setDeletingPlanId] = useState(null); // plan pending inline delete confirm

  // I4-F — subagents (conversation-scoped worker tasks, polled per card).
  const [subagents, setSubagents] = useState([]);
  const [subagentsLoading, setSubagentsLoading] = useState(false);
  const [subagentDialogOpen, setSubagentDialogOpen] = useState(false);
  const [subagentSubmitting, setSubagentSubmitting] = useState(false);
  const [subagentForm, setSubagentForm] = useState({ name: '', brief: '', scope: '' });

  const runPhaseRef = useRef(phase);
  runPhaseRef.current = phase;

  // W5-A — emit the workspace-level lifecycle state whenever the run phase or
  // the plan status changes so the header contract text stays in sync. The
  // callback rides a ref so a new identity from the parent never re-triggers
  // the effect (mirrors the notifyRef pattern above).
  const onLifecycleStateChangeRef = useRef(onLifecycleStateChange);
  onLifecycleStateChangeRef.current = onLifecycleStateChange;
  useEffect(() => {
    onLifecycleStateChangeRef.current?.(deriveLifecycleState(phase, selectedPlan?.status));
  }, [phase, selectedPlan?.status]);

  const handleTabChange = useCallback((e, value) => {
    setTab(value);
    try {
      localStorage.setItem(TASK_TAB_KEY, value);
    } catch {
      // storage may be unavailable — tab still switches in-memory
    }
  }, []);

  // W5-D — the workspace activity bar (Monitor 📊 / Results 📦) drives this
  // panel's internal tab. Only external *changes* move the tab, so the RULE_17
  // persisted value still wins on mount and internal tab clicks aren't fought.
  const prevExternalTabRef = useRef(externalTab);
  useEffect(() => {
    if (prevExternalTabRef.current === externalTab) return;
    prevExternalTabRef.current = externalTab;
    if (externalTab === 'tasks' || externalTab === 'monitor' || externalTab === 'results' || externalTab === 'scheduled') {
      setTab(externalTab);
    }
  }, [externalTab]);

  const loadPlans = useCallback(async () => {
    setPlansLoading(true);
    try {
      const data = await listPlans(token, { limit: 50 });
      setPlans(Array.isArray(data?.plans) ? data.plans : []);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not load tasks');
    } finally {
      setPlansLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  // I4-F — hydrate the conversation's dispatched subagents quietly (no toast).
  useEffect(() => {
    let active = true;
    if (!conversationId) {
      setSubagents([]);
      return undefined;
    }
    setSubagentsLoading(true);
    listSubagents(token, conversationId)
      .then((list) => {
        if (!active) return;
        setSubagents(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!active) return;
        setSubagents([]);
      })
      .finally(() => {
        if (active) setSubagentsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [conversationId, token]);

  const handleDispatchSubagent = async () => {
    if (!conversationId) return;
    let scope_restriction;
    if (subagentForm.scope.trim()) {
      try {
        scope_restriction = JSON.parse(subagentForm.scope.trim());
      } catch {
        notify({ message: t('scopeInvalidJson'), type: 'error' });
        return;
      }
    }
    setSubagentSubmitting(true);
    try {
      const created = await dispatchSubagent(token, conversationId, {
        name: subagentForm.name.trim(),
        brief: subagentForm.brief.trim(),
        ...(scope_restriction ? { scope_restriction } : {}),
      });
      setSubagents((prev) => [created, ...prev.filter((s) => s.id !== created.id)]);
      setSubagentDialogOpen(false);
      setSubagentForm({ name: '', brief: '', scope: '' });
      notify({ message: t('subagentDispatched'), type: 'success' });
    } catch (err) {
      notifyFromError(err);
    } finally {
      setSubagentSubmitting(false);
    }
  };

  const refreshPlan = useCallback(async (planId) => {
    try {
      const plan = await getPlan(token, planId);
      setSelectedPlan(plan);
      setPlans((prev) => prev.map((p) => (p.id === planId ? { ...p, status: plan.status } : p)));
      return plan;
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not refresh the plan');
      return null;
    }
  }, [token]);

  // Live plan polling — while a run is active, refresh the plan so the plan
  // DAG reflects live step statuses (W3-F).
  useEffect(() => {
    const planId = selectedPlan?.id;
    if (!planId || phase !== 'working') return undefined;
    const timer = setInterval(() => {
      refreshPlan(planId);
    }, 3000);
    return () => clearInterval(timer);
  }, [selectedPlan?.id, phase, refreshPlan]);

  const applyPlanToView = useCallback((plan) => {
    setSelectedPlan(plan);
    setRunSteps(
      Array.isArray(plan.steps)
        ? plan.steps.map((s) => ({
            step_id: s.step_id,
            intent: s.intent,
            tool_name: s.tool_name,
            tool_args: s.tool_args,
            depends_on: s.depends_on || [],
            instructions: s.instructions || '',
            agent_role: s.agent_role || 'orchestrator',
            status: s.status || 'pending',
            tool_output: s.tool_output ?? null,
            output_type: s.output_type ?? null,
            artifacts: s.artifacts ?? [],
            error: s.error ?? null,
            // W7-A execution contract (F-26 / F-28): parallel lane grouping
            // + the runnable_state enum the UI locks/edits on.
            strategy: s.strategy || 'sequential',
            parallel_group: s.parallel_group ?? null,
            runnable_state: s.runnable_state ?? (s.status === 'pending' || s.status === 'awaiting_approval' ? 'pending' : 'completed'),
          }))
        : [],
    );
    // A paused plan reopens on the consent surface (its awaiting_approval
    // steps must be actionable), not on the idle surface.
    setPhase(
      plan.status === 'completed'
        ? 'finished'
        : plan.status === 'cancelled'
          ? 'stopped'
          : plan.status === 'failed'
            ? 'error'
            : plan.status === 'paused'
              ? 'paused'
              : 'idle',
    );
    setLedger(null);
  }, []);

  const openPlan = useCallback(async (planId) => {
    setDetailLoading(true);
    try {
      const plan = await getPlan(token, planId);
      applyPlanToView(plan);
      setTab('run');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not open the plan');
    } finally {
      setDetailLoading(false);
    }
  }, [token, applyPlanToView]);

  // Chat → Tasks jump: a chat reply's "Open in Tasks" button lands here with
  // the plan id of the just-drafted plan. Open it once, then signal the
  // workspace that the focus was consumed so the same plan can be re-focused.
  const focusPlanRef = useRef(null);
  useEffect(() => {
    if (!focusPlanId || focusPlanRef.current === focusPlanId) return;
    focusPlanRef.current = focusPlanId;
    openPlan(focusPlanId);
    onFocusPlanConsumed?.();
  }, [focusPlanId, openPlan, onFocusPlanConsumed]);

  // W5-B — when discovery finishes, open the reviewable plan on the Run tab
  // (where AITaskPlanCard renders with the consent gate) and refresh the list.
  const handleDiscoveryReady = useCallback((plan) => {
    applyPlanToView(plan);
    loadPlans();
    setTab('run');
  }, [applyPlanToView, loadPlans]);

  // ── Plan-level consent gate (RULE_21) ─────────────────────────────────
  const handleApprove = async () => {
    if (!selectedPlan) return;
    try {
      const updated = await approvePlan(token, selectedPlan.id);
      setSelectedPlan(updated);
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? { ...p, status: updated.status } : p)));
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not approve the plan');
    }
  };

  const handleDecline = async () => {
    if (!selectedPlan) return;
    try {
      const updated = await declinePlan(token, selectedPlan.id);
      setSelectedPlan(updated);
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? { ...p, status: updated.status } : p)));
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not decline the plan');
    }
  };

  // ── Streamed run ──────────────────────────────────────────────────────
  const loadLedger = useCallback(async (planId) => {
    setLedgerLoading(true);
    try {
      const data = await getPlanLedger(token, planId);
      setLedger(data);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not load the audit ledger');
    } finally {
      setLedgerLoading(false);
    }
  }, [token]);

  // W5-D — Monitor/Results auto-load the ledger. Poll every 5s while a run is
  // live; load once when the run has settled and no ledger is present yet.
  useEffect(() => {
    const planId = selectedPlan?.id;
    if (!planId || (tab !== 'monitor' && tab !== 'results')) return undefined;
    if (phase === 'working') {
      const timer = setInterval(() => loadLedger(planId), 5000);
      return () => clearInterval(timer);
    }
    if (['finished', 'paused', 'stopped', 'error'].includes(phase) && !ledger) {
      loadLedger(planId);
    }
    return undefined;
  }, [tab, phase, selectedPlan?.id, ledger, loadLedger]);

  // W5-D — Results tab loads the plan's artifacts once the run has finished.
  useEffect(() => {
    const planId = selectedPlan?.id;
    if (tab !== 'results' || !planId || phase !== 'finished') return undefined;
    let cancelled = false;
    setArtifactsLoading(true);
    listPlanArtifacts(token, planId)
      .then((data) => {
        if (!cancelled) setArtifacts(Array.isArray(data?.artifacts) ? data.artifacts : []);
      })
      .catch((err) => {
        if (!cancelled) notifyFromErrorRef.current(err, 'Could not load artifacts');
      })
      .finally(() => {
        if (!cancelled) setArtifactsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, phase, selectedPlan?.id, token]);

  const upsertStep = useCallback((patch) => {
    setRunSteps((prev) => {
      const idx = prev.findIndex((s) => s.step_id === patch.step_id);
      if (idx === -1) {
        return [...prev, {
          step_id: patch.step_id,
          intent: patch.intent || `Step ${patch.step_id}`,
          tool_name: null,
          tool_args: null,
          status: 'running',
          tool_output: null,
          error: null,
          ...patch,
        }];
      }
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  }, []);

  const handleRun = async () => {
    if (!selectedPlan) return;
    const planId = selectedPlan.id;
    const streamFn = selectedPlan.status === 'paused' ? resumePlanStream : runPlanStream;
    setPhase('working');
    setErrorMessage(null);
    setLedger(null);
    setRunSteps((prev) =>
      prev.map((s) => (s.status === 'awaiting_approval' ? { ...s, status: 'running' } : s)),
    );

    try {
      await streamFn(token, planId, {
        onFrame: (frame) => {
          if (frame.type === 'step_start') {
            upsertStep({ step_id: frame.step_id, intent: frame.intent, status: 'running' });
          } else if (frame.type === 'step_confirm') {
            upsertStep({ step_id: frame.step_id, intent: frame.intent, status: 'awaiting_approval' });
          } else if (frame.type === 'step_result') {
            upsertStep({
              step_id: frame.step_id,
              intent: frame.intent,
              status: frame.status || 'completed',
              tool_output: frame.tool_output ?? null,
              output_type: frame.output_type ?? null,
              artifacts: frame.artifacts ?? [],
              error: frame.error ?? null,
            });
          } else if (frame.type === 'step_end') {
            upsertStep({ step_id: frame.step_id, status: frame.status });
          }
        },
        onDone: async (frame) => {
          const doneStatus = frame?.status || 'completed';
          if (doneStatus === 'paused') setPhase('paused');
          else if (doneStatus === 'stopped') setPhase('stopped');
          else if (doneStatus === 'failed') { setPhase('error'); setErrorMessage('The run failed.'); }
          else setPhase('finished');
          await refreshPlan(planId);
          if (doneStatus === 'completed') loadLedger(planId);
        },
        onError: (message) => {
          setPhase('error');
          setErrorMessage(message || 'The run failed');
          refreshPlan(planId);
        },
      });
    } catch (err) {
      setPhase('error');
      setErrorMessage(err.message || 'The run failed');
      refreshPlan(planId);
    }
  };

  const handleStop = async () => {
    if (!selectedPlan || runPhaseRef.current !== 'working') return;
    setPhase('stopped');
    try {
      await stopPlan(token, selectedPlan.id);
      await refreshPlan(selectedPlan.id);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not stop the run');
    }
  };

  // ── Per-step consent (resumes the run afterwards via "Resume run") ────
  const handleConfirmStep = async (stepId) => {
    if (!selectedPlan) return;
    setConfirmingId(stepId);
    try {
      const result = await confirmPlanStep(token, selectedPlan.id, stepId);
      if (result?.unstaged) {
        // Pre-execution consent: the step hasn't run yet; token is now set.
        // Auto-resume so the user only needs one click instead of Approve → Resume.
        await handleRun();
      } else {
        // Post-execution confirmation: the staged host mutation ran; step done.
        upsertStep({ step_id: stepId, status: 'completed' });
      }
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not approve the step');
    } finally {
      setConfirmingId(null);
    }
  };

  const handleDeclineStep = async (stepId) => {
    if (!selectedPlan) return;
    setConfirmingId(stepId);
    try {
      await declinePlanStep(token, selectedPlan.id, stepId);
      upsertStep({ step_id: stepId, status: 'skipped' });
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not decline the step');
    } finally {
      setConfirmingId(null);
    }
  };

  const handleDeletePlan = async (planId) => {
    try {
      await deletePlan(token, planId);
      setPlans((prev) => prev.filter((p) => p.id !== planId));
      if (selectedPlan?.id === planId) {
        setSelectedPlan(null);
        setTab('tasks');
      }
      setDeletingPlanId(null);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not delete the task');
      setDeletingPlanId(null);
    }
  };

  // ── W3-F — plan controls (edit / pause / fork) ─────────────────────────
  // Edits never auto-approve (RULE_21): the PATCH returns the revised plan +
  // diff; a diff with real changes opens the consent gate; an empty diff is
  // applied directly (nothing changed beyond the plan state).
  const handleEditPlan = async (newBrief) => {
    if (!selectedPlan || !newBrief) return;
    setMutating(true);
    try {
      const updated = await editPlan(token, selectedPlan.id, { brief: newBrief });
      if (summarizePlanDiff(updated?.diff).count > 0) {
        setDiffReview({ diff: updated.diff, plan: updated });
      } else {
        applyPlanToView(updated);
        notifyRef.current('Plan updated.', 'success');
      }
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not update the plan');
    } finally {
      setMutating(false);
    }
  };

  const saveStepEdit = async (fields) => {
    if (!selectedPlan || !editStepTarget) return;
    const stepId = editStepTarget.step.step_id;
    setEditStepTarget(null);
    setMutating(true);
    try {
      const updated = await editPlanStep(token, selectedPlan.id, stepId, fields);
      if (summarizePlanDiff(updated?.diff).count > 0) {
        setDiffReview({ diff: updated.diff, plan: updated });
      } else {
        applyPlanToView(updated);
        notifyRef.current('Step updated.', 'success');
      }
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not update the step');
    } finally {
      setMutating(false);
    }
  };

  // User reviewed the diff and keeps the revised plan. For a paused run the
  // plan stays paused (only the edited step is re-approved server-side, so the
  // user still controls when to resume). For a reviewable plan it returns to
  // pending_approval and needs the plan consent gate again before running.
  const confirmDiff = () => {
    if (!diffReview) return;
    applyPlanToView(diffReview.plan);
    setPlans((prev) =>
      prev.map((p) => (p.id === diffReview.plan.id ? { ...p, status: diffReview.plan.status } : p)),
    );
    const isPaused = diffReview.plan.status === 'paused';
    notifyRef.current(
      isPaused
        ? 'Step updated — the run stays paused. Resume when ready.'
        : 'Changes kept — the plan needs your approval again.',
      'info',
    );
    setDiffReview(null);
  };

  const handlePause = async () => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      const updated = await pausePlan(token, selectedPlan.id);
      // F-28 — re-sync steps so `runnable_state` drives the paused banner and
      // per-step lock/edit affordances (completed/in_flight locked, pending editable).
      applyPlanToView(updated);
      setPhase('paused');
      setPlans((prev) =>
        prev.map((p) => (p.id === updated.id ? { ...p, status: updated.status } : p)),
      );
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not pause the run');
    } finally {
      setMutating(false);
    }
  };

  const handleFork = async () => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      const forked = await forkPlan(token, selectedPlan.id);
      await loadPlans();
      await openPlan(forked.id);
      notifyRef.current('Forked — a reviewable copy was created.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not fork the plan');
    } finally {
      setMutating(false);
    }
  };

  // ── W3-D — plan templates (Gap #3) ─────────────────────────────────────
  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const data = await listPlanTemplates(token);
      setTemplates(Array.isArray(data?.templates) ? data.templates : []);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not load templates');
    } finally {
      setTemplatesLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (tab === 'templates') loadTemplates();
  }, [tab, loadTemplates]);

  const handleSaveTemplate = async () => {
    if (!selectedPlan || !templateName.trim()) return;
    setTemplateSaving(true);
    try {
      await promotePlanTemplate(token, selectedPlan.id, {
        name: templateName.trim(),
        description: templateDescription.trim(),
      });
      setTemplateName('');
      setTemplateDescription('');
      await loadTemplates();
      notifyRef.current('Saved as a template.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not save the template');
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleInstantiateTemplate = async (templateId) => {
    try {
      const plan = await instantiatePlanTemplate(token, templateId);
      await loadPlans();
      await openPlan(plan.id);
      notifyRef.current('Created from template — review and approve to run.', 'info');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not create from the template');
    }
  };

  // ── W6-E F-29 — schedules (list/create/edit/delete/pause) ──────────────
  const loadSchedules = useCallback(async () => {
    setSchedulesLoading(true);
    setSchedulesError(null);
    try {
      const data = await listSchedules(token);
      setSchedules(Array.isArray(data?.schedules) ? data.schedules : []);
    } catch (err) {
      setSchedulesError(err?.message || 'Could not load schedules');
      notifyFromErrorRef.current(err, 'Could not load schedules');
    } finally {
      setSchedulesLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (tab === 'scheduled') loadSchedules();
  }, [tab, loadSchedules]);

  const openScheduleCreate = (template) => setScheduleDialog({ template });
  const openScheduleEdit = (schedule) => setScheduleDialog({ schedule });
  const closeScheduleDialog = () => {
    if (!scheduleSaving) setScheduleDialog(null);
  };

  const handleScheduleSave = async (fields) => {
    setScheduleSaving(true);
    try {
      if (scheduleDialog?.schedule) {
        await editSchedule(token, scheduleDialog.schedule.id, fields);
        notifyRef.current('Schedule updated.', 'success');
      } else {
        await createSchedule(token, {
          ...fields,
          template_id: scheduleDialog?.template?.id,
        });
        notifyRef.current('Schedule saved.', 'success');
      }
      setScheduleDialog(null);
      await loadSchedules();
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not save the schedule');
    } finally {
      setScheduleSaving(false);
    }
  };

  const handleSchedulePause = async (schedule) => {
    try {
      await pauseSchedule(token, schedule.id);
      await loadSchedules();
      notifyRef.current(schedule.enabled ? 'Schedule paused.' : 'Schedule resumed.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not update the schedule');
    }
  };

  const handleScheduleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteSchedule(token, deleteTarget.id);
      setDeleteTarget(null);
      await loadSchedules();
      notifyRef.current('Schedule deleted.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not delete the schedule');
    }
  };

  // ── Tasks tab: composer + list ────────────────────────────────────────
  const renderTasks = () => (
    <Stack spacing={1.25}>
      {/* New-plan composer — W5-B guided discovery (brief → Pulse questions → plan) */}
      <DiscoveryComposer conversationId={conversationId} onPlanReady={handleDiscoveryReady} />

      {/* Task list */}
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
          My tasks
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          {plans.length}
        </Typography>
      </Stack>

      {plansLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
      ) : plans.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2, fontSize: '0.75rem' }}>
          No task plans yet — describe one above.
        </Typography>
      ) : (
        <Stack spacing={0.75}>
          {plans.map((plan) => {
            const meta = { pending_approval: { label: 'Needs review', color: 'warning' }, approved: { label: 'Approved', color: 'primary' }, running: { label: 'Running…', color: 'primary' }, paused: { label: 'Needs approval', color: 'warning' }, completed: { label: 'Completed', color: 'success' }, failed: { label: 'Failed', color: 'error' }, cancelled: { label: 'Cancelled', color: 'default' } }[plan.status] || { label: plan.status, color: 'default' };
            const deletable = ['cancelled', 'failed', 'completed'].includes(plan.status);
            const confirming = deletingPlanId === plan.id;
            return (
              <Paper
                key={plan.id}
                variant="outlined"
                sx={{ p: 1, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                onClick={() => { if (!confirming) openPlan(plan.id); }}
              >
                <Stack direction="row" alignItems="center" spacing={0.75}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {plan.brief}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', mt: 0.25 }}>
                      {formatWhen(plan.created_at) || ''}
                    </Typography>
                  </Box>
                  <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
                  {deletable && !confirming && (
                    <Tooltip title="Delete task">
                      <IconButton
                        size="small"
                        onClick={(e) => { e.stopPropagation(); setDeletingPlanId(plan.id); }}
                        sx={{ p: 0.375 }}
                      >
                        <DeleteOutlinedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                      </IconButton>
                    </Tooltip>
                  )}
                  {confirming && (
                    <Stack direction="row" spacing={0.5} onClick={(e) => e.stopPropagation()}>
                      <Button size="small" color="error" variant="contained" onClick={() => handleDeletePlan(plan.id)} sx={{ fontSize: '0.5625rem', textTransform: 'none', minWidth: 0, px: 0.75, height: 20 }}>Delete</Button>
                      <Button size="small" onClick={() => setDeletingPlanId(null)} sx={{ fontSize: '0.5625rem', textTransform: 'none', minWidth: 0, px: 0.75, height: 20 }}>Cancel</Button>
                    </Stack>
                  )}
                </Stack>
              </Paper>
            );
          })}
        </Stack>
      )}
    </Stack>
  );

  // ── Run tab: plan card + streamed steps + audit ───────────────────────
  const renderRun = () => {
    if (detailLoading) {
      return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={22} /></Box>;
    }
    if (!selectedPlan) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
          Open a task from the Tasks tab to review, approve and run it.
        </Typography>
      );
    }

    // step_id → phase name for step chips in the live run stream.
    const phaseView = buildPlanPhases(selectedPlan);
    const phaseNameByStep = {};
    phaseView.phases.forEach((p) => {
      p.step_ids.forEach((id) => {
        phaseNameByStep[id] = p.name;
      });
    });
    const phaseNameFor = (stepId) => phaseNameByStep[stepId] || null;

    // F-28 — paused progress counts (runnable_state enum from W7-A).
    const completedCount = runSteps.filter((s) => s.runnable_state === 'completed').length;
    const pendingCount = runSteps.filter((s) => s.runnable_state === 'pending').length;

    return (
      <Stack spacing={1.25}>
        <AITaskPlanCard
          plan={selectedPlan}
          busy={mutating}
          running={phase === 'working'}
          live={phase === 'working'}
          onApprove={handleApprove}
          onDecline={handleDecline}
          onRun={handleRun}
          onPause={handlePause}
          onFork={handleFork}
          onEditPlan={handleEditPlan}
          onEditStep={(step) => setEditStepTarget({ step })}
          onConfirmStep={handleConfirmStep}
          onDeclineStep={handleDeclineStep}
          onSwitchToChat={onSwitchToChat}
          confirmingId={confirmingId}
        />

        {phase === 'paused' && (
          <Alert
            severity="info"
            data-testid="paused-banner"
            sx={{ fontSize: '0.6875rem', py: 0.25, '& .MuiAlert-message': { py: 0 } }}
          >
            Paused — {completedCount} step{completedCount === 1 ? '' : 's'} completed, {pendingCount} to go
          </Alert>
        )}

        {phase === 'working' && (
          <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875, borderBottom: 1, borderColor: 'divider' }}>
              <CircularProgress size={14} thickness={6} sx={{ color: 'primary.main' }} />
              <Typography variant="body2" sx={{ flex: 1, fontWeight: 600, fontSize: '0.75rem' }}>
                Running…
              </Typography>
              <Tooltip title="Stop the run">
                <IconButton size="small" onClick={handleStop} aria-label="Stop run" sx={{ p: 0.375 }}>
                  <StopIcon sx={{ fontSize: 15, color: 'error.main' }} />
                </IconButton>
              </Tooltip>
            </Stack>
            <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              {runSteps.length === 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Starting…
                </Typography>
              )}
              {runSteps.map((step) => (
                <StepCard
                  key={step.step_id}
                  step={step}
                  phaseName={phaseNameFor(step.step_id)}
                  confirming={confirmingId === step.step_id}
                  onConfirm={handleConfirmStep}
                  onDecline={handleDeclineStep}
                />
              ))}
            </Box>
          </Paper>
        )}

        {(phase === 'paused' || phase === 'finished' || phase === 'stopped' || phase === 'error') && (
          <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875, borderBottom: 1, borderColor: 'divider' }}>
              <Typography variant="body2" sx={{ flex: 1, fontWeight: 600, fontSize: '0.75rem' }}>
                {phase === 'paused'
                  ? 'Run paused — a step needs your approval'
                  : phase === 'finished'
                    ? 'Run completed'
                    : phase === 'stopped'
                      ? 'Run stopped'
                      : 'Run failed'}
              </Typography>
              {phase === 'error' && (
                <Chip size="small" color="error" variant="outlined" label="Failed" sx={{ height: 18, fontSize: '0.625rem' }} />
              )}
            </Stack>
            <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              {runSteps.map((step) => (
                <StepCard
                  key={step.step_id}
                  step={step}
                  phaseName={phaseNameFor(step.step_id)}
                  confirming={confirmingId === step.step_id}
                  onConfirm={handleConfirmStep}
                  onDecline={handleDeclineStep}
                />
              ))}
              {phase === 'paused' && (
                <Typography variant="caption" color="text.secondary" sx={{ px: 0.5, fontSize: '0.6875rem' }}>
                  Approve or decline the step above, then resume the run from the plan card.
                </Typography>
              )}
              {phase === 'error' && errorMessage && (
                <Typography variant="caption" color="error.main" sx={{ px: 0.5, fontSize: '0.6875rem' }}>
                  {errorMessage}
                </Typography>
              )}
              {phase === 'stopped' && (
                <Typography variant="caption" color="text.secondary" sx={{ px: 0.5, fontSize: '0.6875rem' }}>
                  Stopped — pending steps were skipped and nothing was executed without approval.
                </Typography>
              )}
            </Box>
          </Paper>
        )}

        {/* Audit ledger — durable record of what actually ran */}
        {(phase === 'finished' || (ledger && (phase === 'paused' || phase === 'stopped' || phase === 'error'))) && (
          <>
            <Stack direction="row" alignItems="center" spacing={1}>
              <HistoryOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
              <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
                Audit
              </Typography>
              {!ledger && !ledgerLoading && (
                <Button size="small" onClick={() => loadLedger(selectedPlan.id)} sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}>
                  Load
                </Button>
              )}
            </Stack>
            {ledgerLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
            ) : (
              <AITaskAuditCard ledger={ledger} />
            )}
          </>
        )}

        {/* I4-F — conversation-scoped subagents, nested under this section. */}
        {conversationId && (
          <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875, borderBottom: 1, borderColor: 'divider' }}>
              <Typography variant="body2" sx={{ flex: 1, fontWeight: 600, fontSize: '0.75rem' }}>
                {t('subagents')}
              </Typography>
              <Button
                size="small"
                onClick={() => setSubagentDialogOpen(true)}
                disabled={subagentSubmitting}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                {t('dispatchSubagent')}
              </Button>
            </Stack>
            {subagentsLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={18} />
              </Box>
            ) : subagents.length === 0 ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', px: 1.25, py: 1, fontSize: '0.6875rem' }}>
                {t('noSubagents')}
              </Typography>
            ) : (
              <Stack spacing={1} sx={{ p: 1 }}>
                {subagents.map((sub) => (
                  <SubagentResultCard
                    key={sub.id}
                    subagent={sub}
                    token={token}
                    conversationId={conversationId}
                    onResolved={(updated) =>
                      setSubagents((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
                    }
                  />
                ))}
              </Stack>
            )}
          </Paper>
        )}
      </Stack>
    );
  };

  // ── Templates tab: save current plan + reuse a saved template ──────────
  const renderTemplates = () => (
    <Stack spacing={1.25}>
      {/* Save current plan as a template */}
      <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', mb: 0.25 }}>
          Save current plan as a template
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.75 }}>
          {selectedPlan
            ? 'Captures the plan steps so you can reuse this workflow later.'
            : 'Open a task from the Tasks tab, then save its plan shape here.'}
        </Typography>
        <TextField
          size="small"
          fullWidth
          placeholder="Template name"
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          disabled={!selectedPlan || templateSaving}
          inputProps={{ 'aria-label': 'Template name' }}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        <TextField
          size="small"
          fullWidth
          placeholder="Description (optional)"
          value={templateDescription}
          onChange={(e) => setTemplateDescription(e.target.value)}
          disabled={!selectedPlan || templateSaving}
          sx={{ mt: 0.75, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        <Button
          size="small"
          variant="contained"
          disabled={!selectedPlan || templateSaving || !templateName.trim()}
          onClick={handleSaveTemplate}
          sx={{ mt: 1, fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {templateSaving ? 'Saving…' : 'Save template'}
        </Button>
      </Paper>

      {/* Template list */}
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
          Saved templates
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          {templates.length}
        </Typography>
      </Stack>

      {templatesLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
      ) : templates.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2, fontSize: '0.75rem' }}>
          No templates yet — save a plan as a template to reuse it.
        </Typography>
      ) : (
        <Stack spacing={0.75}>
          {templates.map((tpl) => (
            <Paper key={tpl.id} variant="outlined" sx={{ p: 1 }}>
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {tpl.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', mt: 0.25 }}>
                    {tpl.step_count} step{(tpl.step_count || 0) === 1 ? '' : 's'}
                    {tpl.description ? ` · ${tpl.description}` : ''}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5}>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => handleInstantiateTemplate(tpl.id)}
                    sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
                  >
                    Use
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => openScheduleCreate(tpl)}
                    aria-label={`Schedule ${tpl.name}`}
                    sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
                  >
                    Schedule
                  </Button>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  );

  // ── Scheduled tab (F-29): list of owned schedules with manage actions ──
  const renderScheduled = () => (
    <Stack spacing={1.25}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
          Scheduled runs
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          {schedules.length}
        </Typography>
      </Stack>
      <ScheduleList
        schedules={schedules}
        loading={schedulesLoading}
        error={schedulesError}
        onEdit={openScheduleEdit}
        onPause={handleSchedulePause}
        onDelete={(s) => setDeleteTarget(s)}
      />
    </Stack>
  );

  // ── Monitor tab: live run metrics + per-step health table ─────────────
  const renderMonitor = () => {
    if (!selectedPlan) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
          Open a task from the Tasks tab to monitor its run.
        </Typography>
      );
    }

    const planMeta = { pending_approval: { label: 'Needs review', color: 'warning' }, approved: { label: 'Approved', color: 'primary' }, running: { label: 'Running…', color: 'primary' }, paused: { label: 'Needs approval', color: 'warning' }, completed: { label: 'Completed', color: 'success' }, failed: { label: 'Failed', color: 'error' }, cancelled: { label: 'Cancelled', color: 'default' } }[selectedPlan.status] || { label: selectedPlan.status, color: 'default' };
    const usage = ledger?.usage || {};
    const steps = Array.isArray(ledger?.steps) ? ledger.steps : runSteps;
    const total = steps.length;
    const completed = steps.filter((s) => s.status === 'completed').length;
    const failed = steps.filter((s) => s.status === 'failed').length;
    const skipped = steps.filter((s) => s.status === 'skipped').length;
    const latencies = steps.map((s) => s.latency_ms).filter((v) => typeof v === 'number' && Number.isFinite(v));
    const minLat = latencies.length ? Math.min(...latencies) : null;
    const maxLat = latencies.length ? Math.max(...latencies) : null;
    const avgLat = latencies.length ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : null;
    const tokens = usage.total_tokens ?? 0;
    const llmCalls = usage.total_llm_calls ?? 0;
    const cost = (tokens / 1_000_000) * LLM_COST_PER_1M_TOKENS;
    const completedAt = ledger?.provenance?.completed_at || (phase === 'finished' ? selectedPlan.updated_at : null);
    const duration = formatDuration(selectedPlan.created_at, completedAt);

    return (
      <Stack spacing={1.25}>
        <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
            <LeaderboardOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="body2" sx={{ flex: 1, fontWeight: 600, fontSize: '0.75rem' }}>
              Monitor
            </Typography>
            <Chip size="small" label={planMeta.label} color={planMeta.color} variant="outlined" sx={{ height: 18, fontSize: '0.625rem' }} />
          </Stack>

          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            <MonitorMetric label="Duration" value={duration} />
            <MonitorMetric label="Steps" value={`${completed}/${total}`} />
            <MonitorMetric label="Failed" value={failed} />
            <MonitorMetric label="Skipped" value={skipped} />
            <MonitorMetric label="Tokens" value={tokens.toLocaleString()} />
            <MonitorMetric label="LLM calls" value={llmCalls} />
            <MonitorMetric label="Est. cost" value={formatCost(cost)} />
            <MonitorMetric label="Latency (min/max/avg)" value={minLat == null ? '—' : `${minLat}/${maxLat}/${avgLat} ms`} />
          </Box>
        </Paper>

        <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
              Step health
            </Typography>
            {ledgerLoading && <CircularProgress size={14} />}
          </Stack>
          {steps.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 1.25, fontSize: '0.6875rem' }}>
              {phase === 'working' ? 'Waiting for steps to start…' : 'No steps recorded yet.'}
            </Typography>
          ) : (
            <Stack sx={{ maxHeight: 320, overflowY: 'auto' }}>
              {steps.map((step) => {
                const stepMeta = STEP_STATUS_ICON[step.status] || { label: step.status || 'Pending', color: 'default' };
                return (
                  <Stack key={step.step_id} direction="row" alignItems="center" spacing={0.75} sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', minWidth: 52, fontFamily: 'monospace' }}>
                      {step.step_id}
                    </Typography>
                    <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {step.intent || `Step ${step.step_id}`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
                      {step.latency_ms != null ? `${step.latency_ms} ms` : '—'}
                    </Typography>
                    <Chip size="small" variant="outlined" label={stepMeta.label} color={stepMeta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
                  </Stack>
                );
              })}
            </Stack>
          )}
        </Paper>
      </Stack>
    );
  };

  // ── Share/Export helpers (RULE_23 — outcome copy only) ────────────────
  const exportLedgerJson = () => {
    if (!ledger || !selectedPlan) return;
    triggerDownload(
      new Blob([JSON.stringify(ledger, null, 2)], { type: 'application/json' }),
      `plan-${selectedPlan.id}-ledger.json`,
    );
  };

  const exportFinalResponseMd = () => {
    if (!selectedPlan) return;
    const text = ledger?.final_response || 'No final response recorded.';
    triggerDownload(new Blob([text], { type: 'text/markdown' }), `plan-${selectedPlan.id}-response.md`);
  };

  // ── Results tab: final response + artifacts + actions ─────────────────
  const renderResults = () => {
    if (!selectedPlan) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
          Open a task from the Tasks tab to see its results.
        </Typography>
      );
    }

    if (phase !== 'finished') {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
            Run the plan to see results.
          </Typography>
        </Box>
      );
    }

    const finalResponse = ledger?.final_response;
    const rerunnable = selectedPlan.status === 'approved';

    return (
      <Stack spacing={1.25}>
        <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary', mb: 0.5 }}>
            Final response
          </Typography>
          {finalResponse ? (
            <Typography variant="body2" sx={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {finalResponse}
            </Typography>
          ) : (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              No final response recorded for this run.
            </Typography>
          )}
        </Paper>

        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
            Artifacts
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {artifacts.length}
          </Typography>
        </Stack>

        {artifactsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
        ) : artifacts.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2, fontSize: '0.75rem' }}>
            This run produced no artifacts.
          </Typography>
        ) : (
          <Stack spacing={0.75}>
            {artifacts.map((artifact) => (
              <ResultArtifactCard key={artifact.id ?? artifact.name} artifact={artifact} planId={selectedPlan.id} token={token} />
            ))}
          </Stack>
        )}

        <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary', mb: 0.75 }}>
            Actions
          </Typography>
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Tooltip title={rerunnable ? 'Run the plan again' : 'Approve the plan to run it again'}>
              <span>
                <Button
                  size="small"
                  variant="contained"
                  disabled={!rerunnable || mutating}
                  onClick={handleRun}
                  sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                >
                  Rerun
                </Button>
              </span>
            </Tooltip>
            <Button
              size="small"
              variant="outlined"
              disabled={mutating}
              onClick={handleFork}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Fork
            </Button>
            <Button
              size="small"
              variant="outlined"
              disabled={!ledger}
              onClick={exportLedgerJson}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Ledger JSON
            </Button>
            <Button
              size="small"
              variant="outlined"
              disabled={!finalResponse}
              onClick={exportFinalResponseMd}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Response .md
            </Button>
          </Stack>
        </Paper>
      </Stack>
    );
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, bgcolor: 'background.default' }}>
      {/* Internal views — one Tasks icon, two tabs (RULE_17) */}
      <Box sx={{ px: 1, pt: 0.5, borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={tab}
          onChange={handleTabChange}
          variant="fullWidth"
          aria-label="Task views"
          sx={{
            minHeight: 34,
            '& .MuiTab-root': { minHeight: 34, fontSize: '0.6875rem', py: 0.5 },
          }}
        >
          <Tab value="tasks" label="Tasks" />
          <Tab value="run" label="Run" />
          <Tab value="monitor" label="Monitor" />
          <Tab value="results" label="Results" />
          <Tab value="templates" label="Templates" />
          <Tab value="scheduled" label="Scheduled" />
        </Tabs>
      </Box>

      {/* Tab content */}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
        {tab === 'tasks'
          ? renderTasks()
          : tab === 'run'
            ? renderRun()
            : tab === 'monitor'
              ? renderMonitor()
              : tab === 'results'
                ? renderResults()
                : tab === 'templates'
                  ? renderTemplates()
                  : renderScheduled()}
      </Box>

      {/* W3-F — diff-review consent gate + step edit dialog (survive tab switches) */}
      <PlanDiffReviewDialog
        open={!!diffReview}
        diff={diffReview?.diff}
        busy={mutating}
        onConfirm={confirmDiff}
        onCancel={() => setDiffReview(null)}
      />
      <StepEditDialog
        open={!!editStepTarget}
        step={editStepTarget?.step}
        steps={selectedPlan?.steps || []}
        busy={mutating}
        onSave={saveStepEdit}
        onClose={() => setEditStepTarget(null)}
      />

      {/* F-29 — schedule create/edit dialog (cadence + plain-language preview) */}
      <ScheduleDialog
        open={!!scheduleDialog}
        schedule={scheduleDialog?.schedule}
        template={scheduleDialog?.template}
        busy={scheduleSaving}
        onSave={handleScheduleSave}
        onClose={closeScheduleDialog}
      />

      {/* I4-F — dispatch a named subagent (name + brief + optional scope). */}
      <SystemDialog
        open={subagentDialogOpen}
        title={t('dispatchSubagent')}
        onClose={() => {
          if (!subagentSubmitting) setSubagentDialogOpen(false);
        }}
        onCancel={() => {
          if (!subagentSubmitting) setSubagentDialogOpen(false);
        }}
        showCancel
        width={480}
        actions={
          <Button
            size="small"
            variant="contained"
            disabled={subagentSubmitting || !subagentForm.name.trim() || !subagentForm.brief.trim()}
            onClick={handleDispatchSubagent}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            {subagentSubmitting ? t('dispatching') : t('dispatchSubagent')}
          </Button>
        }
      >
        <Stack spacing={1.5}>
          <TextField
            size="small"
            fullWidth
            required
            id="subagent-name"
            label={t('subagentName')}
            value={subagentForm.name}
            onChange={(e) => setSubagentForm((prev) => ({ ...prev, name: e.target.value }))}
          />
          <TextField
            size="small"
            fullWidth
            required
            multiline
            minRows={3}
            id="subagent-brief"
            label={t('subagentBrief')}
            value={subagentForm.brief}
            onChange={(e) => setSubagentForm((prev) => ({ ...prev, brief: e.target.value }))}
          />
          <TextField
            size="small"
            fullWidth
            id="subagent-scope"
            label={t('subagentScope')}
            placeholder={'{"tables": ["emissions"]}'}
            helperText={t('scopeInvalidJson')}
            value={subagentForm.scope}
            onChange={(e) => setSubagentForm((prev) => ({ ...prev, scope: e.target.value }))}
          />
        </Stack>
      </SystemDialog>

      {/* F-29 — delete confirm names the consequence before removing (RULE_21) */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: '0.875rem', fontWeight: 700, py: 1.5 }}>
          Delete schedule?
        </DialogTitle>
        <DialogContent dividers>
          <DialogContentText sx={{ fontSize: '0.75rem' }}>
            “{deleteTarget?.name || 'This schedule'}” will stop running on its own. This removes the
            schedule permanently — it cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 2, py: 1 }}>
          <Button size="small" onClick={() => setDeleteTarget(null)} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
            Cancel
          </Button>
          <Button size="small" variant="contained" color="error" onClick={handleScheduleDelete} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

AITaskPanel.propTypes = {
  conversationId: PropTypes.string,
  focusPlanId: PropTypes.string,
  onFocusPlanConsumed: PropTypes.func,
  onLifecycleStateChange: PropTypes.func,
  externalTab: PropTypes.oneOf(['tasks', 'run', 'monitor', 'results', 'templates', 'scheduled']),
};

export default AITaskPanel;
