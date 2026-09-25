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
import LeaderboardOutlinedIcon from '@mui/icons-material/LeaderboardOutlined';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import StopIcon from '@mui/icons-material/Stop';
import ReplayIcon from '@mui/icons-material/Replay';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import CloseIcon from '@mui/icons-material/Close';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
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
  confirmPlanEdit,
  discardPlanEdit,
  forkPlan,
  rerunPlan,
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
  stepCancel,
  stepPause,
  stepResume,
  stepRetry,
  stepSkip,
  stopPlan,
  durableResumeRun,
  deletePlanArtifact,
} from '../api/aiWorkspace';
import ScheduleDialog from '../components/ai/ScheduleDialog';
import ScheduleList from '../components/ai/ScheduleList';
import SystemDialog from '../components/SystemDialog';
import { buildPlanPhases, summarizePlanDiff } from '../utils/planGraph';
import {
  agentRoleLabel,
  effectivePlanStatus,
  isRerunnableStatus,
  isSettledPhase,
  planStatusMeta,
  runHeaderStatusChip,
  stepStatusMeta,
  toolLabel,
} from './aiTaskStatus';
import AITaskPlanCard from './AITaskPlanCard';
import PlanDiffReviewDialog from './PlanDiffReviewDialog';
import StepEditDialog from './StepEditDialog';
import DiscoveryComposer from './DiscoveryComposer';
import PulseWorkspaceFooter from './PulseWorkspaceFooter';
import { usePulsePrefs } from './pulsePrefs';
import AgentTaskPicker from './AgentTaskPicker';
import AgentStage, { stageForStatus } from './AgentStage';
import TaskBoard from './TaskBoard';
import AgentRunSurface, { mergePlanWithRunSteps } from './AgentRunSurface';
import { LIVE_PLAN_POLL_MS } from './pulseProgressCadence';
import AgentReviewSurface from './AgentReviewSurface';
import AgentCockpit, { defaultCockpitSegment, normalizeCockpitSegment } from './AgentCockpit';
import AgentPlanToolbar from './AgentPlanToolbar';
import AgentRunToolbar from './AgentRunToolbar';
import AgentResultToolbar from './AgentResultToolbar';
import TaskJourney from './TaskJourney';
import AITaskAuditCard from './AITaskAuditCard';
import OutcomeReceipt from './OutcomeReceipt';
import ResultProofFold from './ResultProofFold';
import {
  receiptFactsFromActions,
  receiptStateFromPlan,
  receiptTitleFromAnswer,
} from './resultOutcome';
import { hasTaskOutcome, humanTaskTitle, taskCoworkerLine } from './taskWorkspace';
import { ArtifactCard } from '../components/ai/StepOutputRenderer';
import { buildDiscussHandoff } from './buildDiscussDraft';
import { humanizeStepError } from './humanizeStepError';
import ConsentHeroCard from './ConsentHeroCard';
import { stripEngineJargon } from './humanizeOperatorCopy';
import { resolveOutputActions } from './resolveOutputActions';
import { autonomyDefaultListOpen, readAutonomyMode } from './autonomyMode';
import { isImageMime, isPreviewableMime } from './artifactMime';
import {
  readActivePlanId,
  writeActivePlanId,
  clearActivePlanId,
} from './sessionRestore';

dayjs.extend(utc);
dayjs.extend(timezone);

const TASK_TAB_KEY = 'carbon-ai-task-tab';
// Chat-first Agent remake — single workspace (picker + stage). Classic 6-tab
// IA is debug-only via localStorage carbon-ai-cockpit=off.
const COCKPIT_KEY = 'carbon-ai-cockpit';
const COCKPIT_SEGMENT_KEY = 'carbon-ai-cockpit-segment';
const chatFirstEnabled = () => {
  try {
    return localStorage.getItem(COCKPIT_KEY) !== 'off';
  } catch {
    return true;
  }
};
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

/** Compact step latency — never dump raw float milliseconds. */
function formatLatencyMs(ms) {
  if (ms == null || !Number.isFinite(Number(ms))) return '—';
  const n = Number(ms);
  if (n < 1000) return `${Math.round(n)} ms`;
  return `${(n / 1000).toFixed(1)} s`;
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
  if (m.includes('png') || m.includes('jpeg') || m.includes('jpg') || m.includes('image/')) return '🖼';
  if (m.includes('pdf')) return '📕';
  if (m.includes('word') || m.includes('doc')) return '📄';
  return '📁';
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
  running: { icon: 'spinner' },
  completed: { icon: 'done' },
  failed: { icon: 'error' },
  skipped: { icon: 'stopped' },
  awaiting_approval: { icon: 'help' },
  pending: { icon: 'stopped' },
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

/** Failed-step banner: short outcome + optional collapsed traceback. */
function StepErrorBanner({ error }) {
  const [open, setOpen] = useState(false);
  const { summary, detail } = humanizeStepError(error);
  return (
    <Box sx={{ mt: 0.5 }}>
      <Typography variant="caption" color="error.main" sx={{ display: 'block', fontSize: '0.6875rem' }}>
        {summary}
      </Typography>
      {detail ? (
        <>
          <Button
            size="small"
            color="inherit"
            onClick={() => setOpen((v) => !v)}
            endIcon={open ? <ExpandLessIcon sx={{ fontSize: 14 }} /> : <ExpandMoreIcon sx={{ fontSize: 14 }} />}
            sx={{ fontSize: '0.625rem', textTransform: 'none', px: 0, minWidth: 0, mt: 0.25, color: 'text.secondary' }}
            aria-expanded={open}
          >
            Technical details
          </Button>
          <Collapse in={open} unmountOnExit>
            <Box
              component="pre"
              sx={{
                m: 0,
                mt: 0.25,
                p: 1,
                borderRadius: 1,
                bgcolor: 'action.hover',
                fontSize: '0.625rem',
                lineHeight: 1.4,
                maxHeight: 160,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {detail}
            </Box>
          </Collapse>
        </>
      ) : null}
    </Box>
  );
}

StepErrorBanner.propTypes = { error: PropTypes.string };

// W-7 — per-step control toolbar. The visible set of controls is driven purely
// by the step's status (see STEP_CONTROLS). Every action stops event
// propagation so it never toggles the row's expand/collapse.
const STEP_ANY = ['retry', 'pause', 'resume'];
const STEP_CONTROLS = {
  pending: [...STEP_ANY, 'skip', 'cancel'],
  running: [...STEP_ANY, 'cancel'],
  paused: [...STEP_ANY, 'skip', 'cancel'],
  failed: [...STEP_ANY, 'skip'],
  completed: [...STEP_ANY],
  skipped: [...STEP_ANY],
  awaiting_approval: [...STEP_ANY],
};

const STEP_CONTROL_META = {
  retry: { label: 'Retry', icon: ReplayIcon },
  skip: { label: 'Skip', icon: SkipNextIcon },
  cancel: { label: 'Cancel', icon: CloseIcon },
  pause: { label: 'Pause', icon: PauseIcon },
  resume: { label: 'Resume', icon: PlayArrowIcon },
};

export function StepToolbar({ step, busy, onRetry, onSkip, onCancel, onPause, onResume }) {
  const controls = STEP_CONTROLS[step.status] || [];
  if (controls.length === 0) return null;
  const handlers = { retry: onRetry, skip: onSkip, cancel: onCancel, pause: onPause, resume: onResume };
  const run = (name) => (event) => {
    event.stopPropagation();
    handlers[name]?.(step.step_id);
  };
  return (
    <Stack direction="row" spacing={0.25} alignItems="center">
      {controls.map((name) => {
        const meta = STEP_CONTROL_META[name];
        const Icon = meta.icon;
        return (
          <Tooltip key={name} title={meta.label}>
            <span>
              <IconButton
                size="small"
                disabled={busy}
                aria-label={meta.label}
                onClick={run(name)}
                sx={{ p: 0.375 }}
              >
                <Icon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
        );
      })}
    </Stack>
  );
}

StepToolbar.propTypes = {
  step: PropTypes.object.isRequired,
  busy: PropTypes.bool,
  onRetry: PropTypes.func,
  onSkip: PropTypes.func,
  onCancel: PropTypes.func,
  onPause: PropTypes.func,
  onResume: PropTypes.func,
};

function StepCard({
  step, phaseName, confirming, busy, onConfirm, onDecline, onRetry, onSkip, onCancel, onPause, onResume, onEdit, forceOpen = null,
}) {
  const meta = stepStatusMeta(step.status, step);
  const urgent = step.status === 'awaiting_approval' || step.status === 'failed';
  const [open, setOpen] = useState(urgent);
  const expanded = forceOpen == null ? open : forceOpen;
  const showBody = expanded || urgent;

  return (
    <Paper
      variant="outlined"
      sx={{ borderRadius: 1 }}
      data-testid={`agent-step-card-${step.step_id}`}
      data-expanded={expanded ? 'true' : 'false'}
    >
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.75}
        sx={{ px: 0.875, py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
        onClick={() => setOpen((v) => !v)}
      >
        <IconButton size="small" sx={{ p: 0, m: 0 }} aria-label={`Toggle step ${step.step_id} details`}>
          {expanded ? <ExpandMoreIcon sx={{ fontSize: 15 }} /> : <ChevronRightIcon sx={{ fontSize: 15 }} />}
        </IconButton>
        <StepStatusIcon status={step.status} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {stripEngineJargon(step.intent) || `Step ${step.step_id}`}
        </Typography>
        {expanded && phaseName && (
          <Chip size="small" variant="outlined" label={phaseName} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        {/* Analyst chips only when expanded — Operator default stays calm (progressive disclosure). */}
        {expanded && step.agent_role && step.agent_role !== 'orchestrator' && (
          <Chip size="small" variant="outlined" color="secondary" label={agentRoleLabel(step.agent_role)} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        {expanded && step.tool_name && (
          <Chip size="small" variant="outlined" label={toolLabel(step.tool_name)} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        {onEdit && (
          <Tooltip title="Edit step">
            <IconButton
              size="small"
              aria-label={`Edit step ${step.step_id}`}
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onEdit(step);
              }}
              sx={{ p: 0.25 }}
            >
              <EditOutlinedIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        )}
        <StepToolbar
          step={step}
          busy={busy}
          onRetry={onRetry}
          onSkip={onSkip}
          onCancel={onCancel}
          onPause={onPause}
          onResume={onResume}
        />
        <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
        {step.consent_granted && step.status === 'completed' && (
          <Chip
            size="small"
            color="success"
            variant="outlined"
            label="✓ Approved by you"
            sx={{ height: 16, fontSize: '0.5625rem' }}
          />
        )}
      </Stack>

      {showBody && (
        <Box sx={{ px: 1.25, pb: 0.875 }}>
          {/* Operator Run: no Input params / Raw JSON — approve on the timeline. */}
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
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75, fontSize: '0.6875rem' }}>
              Use Approve / Decline on the timeline step to continue.
            </Typography>
          )}
          {step.status === 'skipped' && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem' }}>
              Skipped — not executed.
            </Typography>
          )}
          {step.status === 'failed' && (
            <StepErrorBanner error={step.error || 'This step failed.'} />
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
  busy: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
  onRetry: PropTypes.func,
  onSkip: PropTypes.func,
  onCancel: PropTypes.func,
  onPause: PropTypes.func,
  onResume: PropTypes.func,
  onEdit: PropTypes.func,
  forceOpen: PropTypes.bool,
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

// W5-D — one artifact in the Results grid: Download, Preview, Delete (confirm).
function ResultArtifactCard({ artifact, planId, token, onDeleted }) {
  const { t } = useTranslation('ai');
  const { notify, notifyFromError } = useNotification();
  const [busy, setBusy] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLines, setPreviewLines] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const name = artifact.name || 'artifact';
  const mime = artifact.mime_type || '';
  const previewable = isPreviewableMime(mime);
  const imageable = isImageMime(mime);
  const [imageUrl, setImageUrl] = useState(null);

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
    if (imageable) {
      if (!imageUrl) {
        setPreviewLoading(true);
        try {
          const url = await fetchBlobUrl();
          setImageUrl(url);
        } catch (err) {
          notifyFromError(err, 'Could not preview the artifact');
        } finally {
          setPreviewLoading(false);
        }
      }
      setPreviewOpen(true);
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

  const handleDelete = async () => {
    if (!artifact?.id || !planId) return;
    setBusy(true);
    setConfirmDelete(false);
    try {
      // Plan Output artifacts are RunArtifact rows — not workspace AIArtifact.
      // Hitting DELETE /ai/artifacts/{int}/ blew up (UUID PK) → red banner.
      await deletePlanArtifact(token, planId, artifact.id);
      notify({ message: t('artifactDeleted'), type: 'success' });
      onDeleted?.(artifact.id);
    } catch (err) {
      notifyFromError(err, t('artifactDeleteFailed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 1 }} data-testid="result-artifact-card">
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
            {busy ? '…' : t('download')}
          </Button>
          {(previewable || imageable) && (
            <Button
              size="small"
              variant="outlined"
              disabled={previewLoading}
              onClick={handlePreview}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
            >
              {previewLoading ? '…' : previewOpen ? t('hidePreview') : t('preview')}
            </Button>
          )}
          {artifact.id && (
            <Button
              size="small"
              variant="text"
              color="error"
              disabled={busy}
              onClick={() => setConfirmDelete(true)}
              aria-label={t('deleteArtifact')}
              data-testid="result-artifact-delete"
              sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.5 }}
            >
              {t('delete')}
            </Button>
          )}
        </Stack>
      </Stack>
      <Collapse in={previewOpen}>
        <Box sx={{ mt: 0.75, p: 0.75, borderRadius: 1, bgcolor: 'background.default', maxHeight: 220, overflowY: 'auto' }}>
          {imageable && imageUrl ? (
            <Box
              component="img"
              src={imageUrl}
              alt={name}
              sx={{ maxWidth: '100%', maxHeight: 200, display: 'block', borderRadius: 0.5 }}
            />
          ) : previewLines.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              {t('noPreviewText')}
            </Typography>
          ) : (
            <Typography variant="caption" component="pre" sx={{ m: 0, fontSize: '0.6875rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {previewLines.join('\n')}
            </Typography>
          )}
        </Box>
      </Collapse>
      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle sx={{ fontSize: '0.875rem' }}>{t('deleteArtifactTitle')}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: '0.8125rem' }}>
            {t('deleteArtifactConfirm', { name })}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
            {t('keepFile')}
          </Button>
          <Button color="error" variant="contained" onClick={handleDelete} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
            {t('deleteForever')}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}

ResultArtifactCard.propTypes = {
  artifact: PropTypes.object.isRequired,
  planId: PropTypes.string.isRequired,
  token: PropTypes.string,
  onDeleted: PropTypes.func,
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
function taskFooterStatus(phase, planStatus, errorMessage) {
  const life = deriveLifecycleState(phase, planStatus);
  if (life === 'running') return { variant: 'working', label: 'Working…' };
  if (life === 'consent_needed') return { variant: 'needs-input', label: 'Needs approval' };
  if (life === 'error') return { variant: 'transient', label: errorMessage || 'Failed' };
  if (life === 'plan_pending') return { variant: 'working', label: 'Planning…' };
  return { variant: 'ready', label: 'Ready' };
}

function AITaskPanel({ conversationId, focusPlanId = null, onFocusPlanConsumed, seedBrief = null, onSeedBriefConsumed, pendingRevision = null, onPendingRevisionConsumed, onLifecycleStateChange, onSwitchToChat, externalTab = 'tasks' }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const { t } = useTranslation('ai');
  const pulsePrefs = usePulsePrefs();
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

  // Chat-first layout (default). Classic 6-tab only when carbon-ai-cockpit=off.
  const [chatFirst, setChatFirst] = useState(chatFirstEnabled);
  // ADR-0043 — Plan · Run · Canvas · Output (migrate legacy steps/metrics).
  const [segment, setSegment] = useState(() => {
    try {
      return normalizeCockpitSegment(localStorage.getItem(COCKPIT_SEGMENT_KEY) || 'run');
    } catch {
      return 'run';
    }
  });
  // Soft lifecycle defaults: after the user picks a segment for a plan, keep it.
  const segmentOverrideRef = useRef(null);
  // Once a task has shown Result, retry/rerun must not dim or hide that tab.
  const resultStickyRef = useRef(null);
  const [runHealthOpen, setRunHealthOpen] = useState(false);

  // Task list + composer
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansLoadError, setPlansLoadError] = useState(false);

  // Selected plan detail + run state
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [runSteps, setRunSteps] = useState([]);
  const [phase, setPhase] = useState('idle'); // idle|working|paused|finished|stopped|error
  const [autonomyMode, setAutonomyMode] = useState(() => readAutonomyMode());
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

  // ADR-0043 — cockpit segment (Plan · Run · Canvas · Output), RULE_17 persist.
  // Manual switches pin the choice for the current plan (soft lifecycle defaults).
  const handleSegmentChange = useCallback((value, { user = true } = {}) => {
    if (!value) return;
    let next = normalizeCockpitSegment(value);
    const effective = selectedPlan ? effectivePlanStatus(selectedPlan) : '';
    if (
      next === 'output'
      && !hasTaskOutcome(effective, phaseRef.current)
      && resultStickyRef.current !== selectedPlan?.id
    ) {
      next = 'run';
    }
    setSegment(next);
    if (user) segmentOverrideRef.current = selectedPlan?.id ?? true;
    try {
      localStorage.setItem(COCKPIT_SEGMENT_KEY, next);
    } catch {
      // storage may be unavailable — segment still switches in-memory
    }
  }, [selectedPlan]);

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

  // ADR-0043 — activity-bar drives cockpit: monitor→Run, results→Output.
  // Tasks/run follow soft lifecycle defaults (do NOT force Run on completed).
  const selectedPlanRef = useRef(selectedPlan);
  const phaseRef = useRef(phase);
  const runStepsRef = useRef(runSteps);
  selectedPlanRef.current = selectedPlan;
  phaseRef.current = phase;
  runStepsRef.current = runSteps;

  useEffect(() => {
    const onAutonomy = (event) => {
      const next = event?.detail;
      if (next) setAutonomyMode(next);
      else setAutonomyMode(readAutonomyMode());
    };
    window.addEventListener('carbon-ai-autonomy', onAutonomy);
    return () => window.removeEventListener('carbon-ai-autonomy', onAutonomy);
  }, []);

  const prevExternalSegRef = useRef(externalTab);
  useEffect(() => {
    if (prevExternalSegRef.current === externalTab) return;
    prevExternalSegRef.current = externalTab;
    if (externalTab === 'monitor') {
      handleSegmentChange('run', { user: true });
      return;
    }
    if (externalTab === 'results') {
      handleSegmentChange('output', { user: true });
      return;
    }
    if (externalTab === 'tasks' || externalTab === 'run') {
      const plan = selectedPlanRef.current;
      if (!plan || plan.status === 'discovering') {
        handleSegmentChange('run', { user: false });
        return;
      }
      const effective = effectivePlanStatus(
        runStepsRef.current.length
          ? { ...plan, steps: mergePlanWithRunSteps(plan, runStepsRef.current).steps }
          : plan,
      );
      const next = defaultCockpitSegment(effective, phaseRef.current);
      handleSegmentChange(next, { user: false });
    }
  }, [externalTab, handleSegmentChange]);

  const loadPlans = useCallback(async () => {
    if (!token) return;
    setPlansLoading(true);
    setPlansLoadError(false);
    try {
      const data = await listPlans(token, { limit: 50 });
      setPlans(Array.isArray(data?.plans) ? data.plans : []);
    } catch (err) {
      setPlansLoadError(true);
      notifyFromErrorRef.current(err, 'Could not load tasks');
    } finally {
      setPlansLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  // Returning to the board — refresh once (not while a task is open).
  const boardHome = chatFirst && !selectedPlan;
  const boardHomeRef = useRef(false);
  useEffect(() => {
    if (!boardHome || !token) {
      boardHomeRef.current = boardHome;
      return;
    }
    if (boardHomeRef.current) return;
    boardHomeRef.current = true;
    loadPlans();
  }, [boardHome, token, loadPlans]);

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

  const refreshPlan = useCallback(async (planId, { quiet = false } = {}) => {
    try {
      const plan = await getPlan(token, planId);
      setSelectedPlan(plan);
      setPlans((prev) => prev.map((p) => (p.id === planId ? { ...p, ...plan } : p)));
      // The Now timeline reads runSteps, snapshotted as Pending when the run
      // opened. A quiet poll used to update the plan row only, so every step
      // stayed Pending while the chip said Working.
      if (Array.isArray(plan.steps) && plan.steps.length) {
        setRunSteps((prev) => {
          if (!prev.length) return prev;
          const byId = new Map(plan.steps.map((s) => [s.step_id, s]));
          const rank = {
            pending: 0,
            running: 1,
            paused: 2,
            awaiting_approval: 3,
            completed: 4,
            failed: 4,
            skipped: 4,
          };
          return prev.map((s) => {
            const fresh = byId.get(s.step_id);
            if (!fresh?.status) return s;
            // A poll that left before the step finished must not paint
            // Running back over a step the stream already settled.
            if ((rank[fresh.status] ?? 0) < (rank[s.status] ?? 0)) return s;
            return {
              ...s,
              status: fresh.status,
              error: fresh.error ?? s.error,
              tool_output: fresh.tool_output ?? s.tool_output,
              output_type: fresh.output_type ?? s.output_type,
              artifacts: fresh.artifacts ?? s.artifacts,
              consent_granted: Boolean(fresh.consent_granted) || Boolean(s.consent_granted),
              consent_slots: Array.isArray(fresh.consent_slots)
                ? fresh.consent_slots
                : s.consent_slots,
              tool_args: fresh.tool_args ?? s.tool_args,
            };
          });
        });
      }
      return plan;
    } catch (err) {
      if (!quiet) {
        notifyFromErrorRef.current(err, 'Could not refresh the plan');
      }
      return null;
    }
  }, [token]);

  // Poll only while a run is actually working. A paused consent wait used to
  // poll every 2s (~1800/hour) and trip the production 1000/hour user cap.
  useEffect(() => {
    const planId = selectedPlan?.id;
    const waiting = runSteps.some((s) => s.status === 'awaiting_approval');
    if (!planId || phase !== 'working' || waiting) return undefined;
    const timer = setInterval(() => {
      refreshPlan(planId, { quiet: true });
    }, LIVE_PLAN_POLL_MS);
    return () => clearInterval(timer);
  }, [selectedPlan?.id, phase, refreshPlan, runSteps]);

  const applyPlanToView = useCallback((plan) => {
    // New plan → allow lifecycle default to re-apply (ADR-0043 soft defaults).
    // Retry/rerun of the plan already on Result keeps that tab pinned.
    if (resultStickyRef.current !== plan?.id) segmentOverrideRef.current = null;
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
            retry_count: s.retry_count ?? 0,
            is_mutation: Boolean(s.is_mutation),
            heal_note: s.heal_note || '',
            consent_granted: Boolean(s.consent_granted),
            consent_slots: Array.isArray(s.consent_slots) ? s.consent_slots : [],
            // W7-A execution contract (F-26 / F-28): parallel lane grouping
            // + the runnable_state enum the UI locks/edits on.
            strategy: s.strategy || 'sequential',
            parallel_group: s.parallel_group ?? null,
            runnable_state: s.runnable_state ?? (s.status === 'pending' || s.status === 'awaiting_approval' ? 'pending' : 'completed'),
          }))
        : [],
    );
    // A paused plan reopens on the consent surface (its awaiting_approval
    // steps must be actionable), not on the idle surface. Trust server
    // `paused` even when step rows look terminal (race / steer edge).
    const effective = effectivePlanStatus(plan);
    setPhase(
      plan.status === 'paused' || effective === 'paused'
        ? 'paused'
        : effective === 'completed' || effective === 'completed_with_gaps'
          ? 'finished'
          : effective === 'cancelled'
            ? 'stopped'
            : effective === 'failed'
              ? 'error'
              : 'idle',
    );
    setLedger(null);
  }, []);

  const openPlan = useCallback(async (planId, { activateRunTab = true } = {}) => {
    setDetailLoading(true);
    try {
      const plan = await getPlan(token, planId);
      applyPlanToView(plan);
      writeActivePlanId(planId);
      if (activateRunTab) setTab('run');
    } catch (err) {
      // Stale pointer (deleted plan) — drop it so the next open does not loop.
      if (readActivePlanId() === String(planId)) clearActivePlanId();
      notifyFromErrorRef.current(err, 'Could not open the plan');
    } finally {
      setDetailLoading(false);
    }
  }, [token, applyPlanToView]);

  // Restore last Task on reopen (chat-first used to always land on the empty board).
  // focusPlanId (Chat → Tasks jump) wins over the stored pointer.
  const autoOpenedRef = useRef(false);
  useEffect(() => {
    if (autoOpenedRef.current || selectedPlan || focusPlanId) return;
    const stored = readActivePlanId();
    if (stored) {
      autoOpenedRef.current = true;
      openPlan(stored, { activateRunTab: false });
      return;
    }
    if (chatFirst) return;
    if (plansLoading || !plans.length) return;
    autoOpenedRef.current = true;
    const active = ['discovering', 'pending_approval', 'approved', 'running', 'paused'];
    const preferred = plans.find((p) => active.includes(p.status)) || plans[0];
    if (preferred?.id) openPlan(preferred.id, { activateRunTab: false });
  }, [chatFirst, plans, plansLoading, selectedPlan, focusPlanId, openPlan]);

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

  // ADR-0043 — soft lifecycle defaults for Plan · Run · Canvas · Output.
  // Manual segment choice for this plan wins until another plan is opened.
  useEffect(() => {
    if (!chatFirst || !selectedPlan?.id || selectedPlan.status === 'discovering') return;
    if (segmentOverrideRef.current === selectedPlan.id) return;
    if (segment === 'output' && resultStickyRef.current === selectedPlan.id) return;
    const effective = effectivePlanStatus(
      runSteps.length
        ? { ...selectedPlan, steps: mergePlanWithRunSteps(selectedPlan, runSteps).steps }
        : selectedPlan,
    );
    const next = defaultCockpitSegment(effective, phase);
    if (segment !== next) handleSegmentChange(next, { user: false });
  }, [
    chatFirst,
    selectedPlan?.id,
    selectedPlan?.status,
    phase,
    segment,
    handleSegmentChange,
  ]);

  // W5-B — discovery finished → open reviewable plan in the Review stage.
  const handleDiscoveryReady = useCallback((plan) => {
    applyPlanToView(plan);
    loadPlans();
  }, [applyPlanToView, loadPlans]);

  // New discovering run started — select it so the picker + stage stay in sync.
  // Do not GET the plan yet (list/detail may lag); hydrate from the start payload.
  const handleDiscoveryStarted = useCallback((started) => {
    loadPlans();
    if (!started?.id) return;
    applyPlanToView({
      id: started.id,
      status: 'discovering',
      brief: started.brief || '',
      discovery_turns: Array.isArray(started.turns) ? started.turns : [],
      steps: [],
      created_at: new Date().toISOString(),
    });
  }, [loadPlans, applyPlanToView]);

  // ── Plan-level consent gate (RULE_21) ─────────────────────────────────
  const handleApprove = async () => {
    if (!selectedPlan) return;
    try {
      const updated = await approvePlan(token, selectedPlan.id);
      setSelectedPlan(updated);
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? { ...p, status: updated.status } : p)));
      handleSegmentChange('run', { user: false });
      loadPlans();
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
      loadPlans();
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
  // live; load once when the run has settled (prefetch so Output/Run health
  // are ready without an extra click).
  useEffect(() => {
    const planId = selectedPlan?.id;
    const settled = isSettledPhase(phase)
      || isRerunnableStatus(selectedPlan?.status)
      || isRerunnableStatus(effectivePlanStatus(selectedPlan));
    const ledgerVisible =
      tab === 'monitor' || tab === 'results'
      || (chatFirst && (segment === 'run' || segment === 'output' || runHealthOpen || settled));
    if (!planId || !ledgerVisible) return undefined;
    if (phase === 'working') {
      const timer = setInterval(() => loadLedger(planId), 5000);
      return () => clearInterval(timer);
    }
    if (settled && !ledger) {
      loadLedger(planId);
    }
    return undefined;
  }, [tab, chatFirst, segment, runHealthOpen, phase, selectedPlan, ledger, loadLedger]);

  // Settled runs: open Run health by default so audit is not a hidden click
  // (Screen Spec — completed-plan actions).
  useEffect(() => {
    if (isSettledPhase(phase)) setRunHealthOpen(true);
  }, [phase, selectedPlan?.id]);

  // W5-D — load plan artifacts on Results/Output OR graph-first Run when settled.
  useEffect(() => {
    const planId = selectedPlan?.id;
    const status = selectedPlan?.status;
    const terminal = ['completed', 'failed', 'cancelled'].includes(status)
      || ['finished', 'stopped', 'error'].includes(phase);
    const runStage = stageForStatus(status, phase) === 'run';
    const artifactsVisible =
      tab === 'results'
      || (chatFirst && (segment === 'output' || runStage))
      || (!chatFirst && tab === 'run' && terminal);
    if (!artifactsVisible || !planId || !terminal) return undefined;
    let cancelled = false;
    setArtifactsLoading(true);
    const pending = listPlanArtifacts(token, planId);
    if (!pending || typeof pending.then !== 'function') {
      setArtifactsLoading(false);
      return undefined;
    }
    pending
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
  }, [tab, chatFirst, segment, phase, selectedPlan?.id, selectedPlan?.status, token]);

  const upsertStep = useCallback((patch) => {
    setRunSteps((prev) => {
      const idx = prev.findIndex((s) => s.step_id === patch.step_id);
      if (idx === -1) {
        return [...prev, {
          step_id: patch.step_id,
          intent: patch.intent || `Step ${patch.step_id}`,
          tool_name: null,
          tool_args: null,
          status: 'pending',
          tool_output: null,
          error: null,
          ...patch,
        }];
      }
      const current = prev[idx].status;
      const patchStatus = patch.status;
      const settled = current === 'completed' || current === 'failed'
        || current === 'skipped' || current === 'awaiting_approval';
      const nextPatch = (patchStatus === 'running' && settled)
        ? (({ status, ...rest }) => rest)(patch)
        : patch;
      const next = [...prev];
      next[idx] = { ...next[idx], ...nextPatch };
      return next;
    });
  }, []);

  const stopRequestedRef = useRef(false);

  const handleRun = async ({ forceResume = false } = {}) => {
    if (!selectedPlan) return;
    const planId = selectedPlan.id;
    // Resume only from durable paused/approved. Never trust phase alone —
    // after Approve, get_plan may already reconcile to completed while phase
    // still says paused; resuming then paints a false "Didn't finish".
    const durableResume = (
      selectedPlan.status === 'paused'
      || selectedPlan.status === 'approved'
    );
    if (
      forceResume
      && !durableResume
      && (selectedPlan.status === 'completed' || selectedPlan.status === 'completed_with_gaps')
    ) {
      setPhase('finished');
      setErrorMessage(null);
      await refreshPlan(planId);
      return;
    }
    const streamFn = (
      forceResume || durableResume
    ) ? resumePlanStream : runPlanStream;
    stopRequestedRef.current = false;
    setPhase('working');
    setErrorMessage(null);
    if (resultStickyRef.current !== planId) setLedger(null);
    // Do NOT flip awaiting_approval → running here: Approve already owns
    // that transition, and a premature "Running…" hides the consent surface
    // when the stream pauses again or times out mid-poll.

    try {
      await streamFn(token, planId, {
        onFrame: (frame) => {
          if (stopRequestedRef.current) return;
          if (frame.type === 'step_start') {
            upsertStep({
              step_id: frame.step_id,
              intent: frame.intent,
              status: 'running',
            });
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
              ...(frame.consent_granted ? { consent_granted: true } : {}),
            });
          } else if (frame.type === 'step_end') {
            upsertStep({ step_id: frame.step_id, status: frame.status });
          }
        },
        onDone: async (frame) => {
          // Operator Stop wins over a late stream "completed" frame.
          if (stopRequestedRef.current || runPhaseRef.current === 'stopped') {
            setPhase('stopped');
            await refreshPlan(planId);
            return;
          }
          const doneStatus = frame?.status || 'completed';
          if (doneStatus === 'paused') setPhase('paused');
          else if (doneStatus === 'stopped' || doneStatus === 'cancelled') setPhase('stopped');
          else if (doneStatus === 'failed') { setPhase('error'); setErrorMessage('The run failed.'); }
          else setPhase('finished');
          // Apply Answer immediately from the done frame so Output works
          // without waiting on Ledger (plan DTO also carries final_response).
          if (typeof frame?.final_response === 'string' && frame.final_response.trim()) {
            setSelectedPlan((prev) => (
              prev && prev.id === planId
                ? { ...prev, final_response: frame.final_response }
                : prev
            ));
          }
          await refreshPlan(planId);
          if (doneStatus === 'completed' || doneStatus === 'completed_with_gaps') {
            loadLedger(planId);
          }
        },
        onError: async (message) => {
          const msg = message || 'The run failed';
          const fresh = await refreshPlan(planId);
          // Resume after Approve can race a completed reconcile ("Plan is not
          // runnable (status: completed)"). If the host write already landed,
          // keep the success receipt — never paint "Didn't finish".
          if (
            /not runnable.*completed/i.test(msg)
            && (fresh?.status === 'completed' || fresh?.status === 'completed_with_gaps')
          ) {
            setPhase('finished');
            setErrorMessage(null);
            return;
          }
          setPhase('error');
          setErrorMessage(msg);
        },
      });
    } catch (err) {
      const msg = err.message || 'The run failed';
      const fresh = await refreshPlan(planId);
      if (
        /not runnable.*completed/i.test(msg)
        && (fresh?.status === 'completed' || fresh?.status === 'completed_with_gaps')
      ) {
        setPhase('finished');
        setErrorMessage(null);
        return;
      }
      setPhase('error');
      setErrorMessage(msg);
    }
  };

  const handleStop = async () => {
    if (!selectedPlan || runPhaseRef.current !== 'working') return;
    await handleCancel();
  };

  const handleCancel = async () => {
    if (!selectedPlan) return;
    const live = runPhaseRef.current === 'working'
      || runPhaseRef.current === 'paused'
      || phase === 'paused';
    if (!live) return;
    stopRequestedRef.current = true;
    setPhase('stopped');
    setMutating(true);
    try {
      await stopPlan(token, selectedPlan.id);
      const updated = await refreshPlan(selectedPlan.id);
      if (updated?.steps) applyPlanToView(updated);
      setPhase('stopped');
    } catch (err) {
      stopRequestedRef.current = false;
      notifyFromErrorRef.current(err, 'Could not cancel the run');
    } finally {
      setMutating(false);
    }
  };

  // ── Per-step consent (resume only when work remains) ────
  const handleConfirmStep = async (stepId, opts = {}) => {
    if (!selectedPlan) return;
    setConfirmingId(stepId);
    try {
      const result = await confirmPlanStep(token, selectedPlan.id, stepId, opts);
      upsertStep({ step_id: stepId, status: 'completed' });
      const updated = await refreshPlan(selectedPlan.id);
      const planStatus = (
        result?.plan_status
        || updated?.status
        || selectedPlan.status
      );
      const stillRunnable = planStatus === 'paused' || planStatus === 'approved';
      const alreadyDone = (
        planStatus === 'completed'
        || planStatus === 'completed_with_gaps'
      );
      if (alreadyDone) {
        // Host write already landed (loan/leave/etc). Do not resume a
        // completed plan — that surfaces as "Didn't finish".
        setPhase('finished');
        setErrorMessage(null);
        return;
      }
      if (result?.unstaged || result?.committed || result?.committed_inline || stillRunnable) {
        if (stillRunnable) {
          setSelectedPlan((prev) => (
            prev ? { ...prev, status: planStatus } : prev
          ));
          await handleRun({ forceResume: true });
        }
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

  // ── W-7 — per-step controls. Each transitions a single step; a guard
  // violation (409) means the step already changed state — surfaced gracefully
  // via notifyFromError. The plan is re-fetched so the toolbar reflects the
  // new status.
  const handleStepRetry = async (stepId) => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      await stepRetry(token, selectedPlan.id, stepId);
      await refreshPlan(selectedPlan.id);
      notifyRef.current('Step re-queued.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not retry the step');
    } finally {
      setMutating(false);
    }
  };

  const handleStepSkip = async (stepId) => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      await stepSkip(token, selectedPlan.id, stepId);
      await refreshPlan(selectedPlan.id);
      notifyRef.current('Step skipped.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not skip the step');
    } finally {
      setMutating(false);
    }
  };

  const handleStepCancel = async (stepId) => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      await stepCancel(token, selectedPlan.id, stepId);
      await refreshPlan(selectedPlan.id);
      notifyRef.current('Step cancelled.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not cancel the step');
    } finally {
      setMutating(false);
    }
  };

  const handleStepPause = async (stepId) => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      await stepPause(token, selectedPlan.id, stepId);
      await refreshPlan(selectedPlan.id);
      notifyRef.current('Step paused.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not pause the step');
    } finally {
      setMutating(false);
    }
  };

  const handleStepResume = async (stepId) => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      await stepResume(token, selectedPlan.id, stepId);
      await refreshPlan(selectedPlan.id);
      notifyRef.current('Step resumed.', 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not resume the step');
    } finally {
      setMutating(false);
    }
  };

  const closePlan = useCallback(() => {
    segmentOverrideRef.current = null;
    setSelectedPlan(null);
    setRunSteps([]);
    setPhase('idle');
    setLedger(null);
    clearActivePlanId();
  }, []);

  const handleDeletePlan = async (planId) => {
    try {
      await deletePlan(token, planId);
      setPlans((prev) => prev.filter((p) => p.id !== planId));
      if (selectedPlan?.id === planId) {
        closePlan();
        setTab('tasks');
      }
      setDeletingPlanId(null);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not delete the task');
      setDeletingPlanId(null);
    }
  };

  // ── W3-F — plan controls (rename / replan / pause / fork) ──────────────
  // Rename = label only. Replan = decompose + diff (RULE_21); Cancel restores
  // the pre-edit snapshot via discardPlanEdit.
  const handleRenamePlan = async (newBrief) => {
    if (!selectedPlan || !newBrief) return;
    setMutating(true);
    try {
      const updated = await editPlan(token, selectedPlan.id, {
        brief: newBrief,
        mode: 'rename',
      });
      applyPlanToView(updated);
      notifyRef.current(t('titleUpdated'), 'success');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not rename the plan');
    } finally {
      setMutating(false);
    }
  };

  const handleReplanPlan = async (newBrief) => {
    if (!selectedPlan || !newBrief) return;
    setMutating(true);
    try {
      const updated = await editPlan(token, selectedPlan.id, {
        brief: newBrief,
        mode: 'replan',
      });
      if (summarizePlanDiff(updated?.diff).count > 0) {
        setDiffReview({ diff: updated.diff, plan: updated, kind: 'replan' });
      } else {
        await confirmPlanEdit(token, selectedPlan.id).catch(() => null);
        applyPlanToView(updated);
        notifyRef.current(t('planUpdated'), 'success');
      }
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not replan');
    } finally {
      setMutating(false);
    }
  };

  /** @deprecated Prefer handleRenamePlan / handleReplanPlan — kept for step card wiring. */
  const handleEditPlan = handleReplanPlan;

  const saveStepEdit = async (fields) => {
    if (!selectedPlan || !editStepTarget) return;
    const stepId = editStepTarget.step.step_id;
    setEditStepTarget(null);
    setMutating(true);
    try {
      const updated = await editPlanStep(token, selectedPlan.id, stepId, fields);
      if (summarizePlanDiff(updated?.diff).count > 0) {
        setDiffReview({ diff: updated.diff, plan: updated, kind: 'step' });
      } else {
        applyPlanToView(updated);
        notifyRef.current(t('planUpdated'), 'success');
      }
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not update the step');
    } finally {
      setMutating(false);
    }
  };

  const confirmDiff = async () => {
    if (!diffReview) return;
    setMutating(true);
    try {
      await confirmPlanEdit(token, selectedPlan.id);
      applyPlanToView(diffReview.plan);
      setPlans((prev) =>
        prev.map((p) => (p.id === diffReview.plan.id ? { ...p, status: diffReview.plan.status } : p)),
      );
      const isPaused = diffReview.plan.status === 'paused';
      notifyRef.current(
        isPaused
          ? 'Step updated — the run stays paused. Resume when ready.'
          : t('changesKeptNeedApproval'),
        'info',
      );
      setDiffReview(null);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not confirm the changes');
    } finally {
      setMutating(false);
    }
  };

  const cancelDiff = async () => {
    if (!selectedPlan) {
      setDiffReview(null);
      return;
    }
    setMutating(true);
    try {
      const restored = await discardPlanEdit(token, selectedPlan.id);
      applyPlanToView(restored);
      setPlans((prev) =>
        prev.map((p) => (p.id === restored.id ? { ...p, ...restored } : p)),
      );
      notifyRef.current(t('changesDiscarded'), 'info');
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not discard the changes');
    } finally {
      setDiffReview(null);
      setMutating(false);
    }
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

  // Retry failed steps: crash-resume re-queues failed steps, then stream.
  const handleRetry = async () => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      await durableResumeRun(token, selectedPlan.id);
      await refreshPlan(selectedPlan.id);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not re-queue failed steps');
      setMutating(false);
      return;
    }
    setMutating(false);
    handleRun();
  };

  const handleFork = async () => {
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

  // Re-run an executed plan from a clean slate: refresh → POST rerun (when
  // terminal) → stream. Aligns toolbar `selectedEffective` with API status
  // (including completed_with_gaps) so Play-on-stale-status never skips reset.
  const handleRerun = async () => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      const reset = await rerunPlan(token, selectedPlan.id);
      // refreshPlan only replaces the plan row. The run list and the
      // finished phase live in separate state, so a rerun stayed on Done
      // with every step still completed until the stream happened to
      // overwrite one. Apply the reset payload: steps are pending, phase
      // leaves finished.
      if (reset?.steps) applyPlanToView(reset);
      else await refreshPlan(selectedPlan.id);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not re-run the plan');
      setMutating(false);
      return;
    }
    setMutating(false);
    handleRun();
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

  // ── Classic Tasks tab (debug fallback only) ───────────────────────────
  const renderTasks = () => (
    <Stack spacing={1.25}>
      <AgentTaskPicker
        plans={plans}
        loading={plansLoading}
        selectedId={selectedPlan?.id || ''}
        onSelect={(id) => {
          if (id) openPlan(id);
          else closePlan();
        }}
        onDelete={handleDeletePlan}
        deletingId={deletingPlanId}
      />
    </Stack>
  );

  // ── Run: graph-first surface (DAG hero; list behind toggle) ───────────
    const renderRun = ({ hideInherited = false, quietChrome = false } = {}) => {
    if (detailLoading) {
      return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={22} /></Box>;
    }
    if (!selectedPlan) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
          Pick a task. New work starts in Chat, in Plan mode.
        </Typography>
      );
    }

    const phaseView = buildPlanPhases(selectedPlan);
    const phaseNameByStep = {};
    phaseView.phases.forEach((p) => {
      p.step_ids.forEach((id) => {
        phaseNameByStep[id] = p.name;
      });
    });
    const phaseNameFor = (stepId) => phaseNameByStep[stepId] || null;

    const listSteps = runSteps.length ? runSteps : (Array.isArray(selectedPlan.steps)
      ? selectedPlan.steps.map((s) => ({
          step_id: s.step_id,
          intent: s.intent,
          tool_name: s.tool_name,
          tool_args: s.tool_args,
          status: s.status || 'pending',
          tool_output: s.tool_output ?? null,
          output_type: s.output_type ?? null,
          artifacts: s.artifacts ?? [],
          error: s.error ?? null,
          runnable_state: s.runnable_state,
          agent_role: s.agent_role,
          consent_granted: Boolean(s.consent_granted),
        }))
      : []);
    const completedCount = listSteps.filter(
      (s) => s.status === 'completed' || s.runnable_state === 'completed',
    ).length;
    const pendingCount = listSteps.filter(
      (s) => s.status === 'pending' || s.status === 'awaiting_approval' || s.runnable_state === 'pending',
    ).length;
    const awaitingStep = listSteps.find((s) => s.status === 'awaiting_approval') || null;
    const pausedCompletedLabel = `${completedCount} step${completedCount === 1 ? '' : 's'} completed, ${pendingCount} to go`;

    const statusBanner = (() => {
      if (phase === 'paused' || awaitingStep) {
        return (
          <Alert
            severity="info"
            data-testid="paused-banner"
            sx={{ fontSize: '0.6875rem', py: 0.25, '& .MuiAlert-message': { py: 0 } }}
          >
            Paused — {pausedCompletedLabel}
          </Alert>
        );
      }
      if (phase === 'working') {
        return (
          <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875 }}>
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
          </Paper>
        );
      }
      if (phase === 'finished' || phase === 'stopped' || phase === 'error') {
        return (
          <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875 }}>
              <Typography variant="body2" sx={{ flex: 1, fontWeight: 600, fontSize: '0.75rem' }}>
                {phase === 'finished'
                  ? 'Run completed'
                  : phase === 'stopped'
                    ? 'Run stopped'
                    : 'Run failed'}
              </Typography>
              {phase === 'error' && (
                <Chip size="small" color="error" variant="outlined" label="Failed" sx={{ height: 18, fontSize: '0.625rem' }} />
              )}
            </Stack>
            {phase === 'error' && errorMessage && (
              <Typography variant="caption" color="error.main" sx={{ display: 'block', px: 1.25, pb: 1, fontSize: '0.6875rem' }}>
                {errorMessage}
              </Typography>
            )}
            {phase === 'stopped' && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', px: 1.25, pb: 1, fontSize: '0.6875rem' }}>
                Stopped — pending steps were skipped and nothing was executed without approval.
              </Typography>
            )}
          </Paper>
        );
      }
      return null;
    })();

    const listContent = (
      <Stack spacing={1}>
        {(phase === 'paused' || awaitingStep) && !awaitingStep && (
          <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
            Run paused — a step needs your approval
          </Typography>
        )}
        {listSteps.map((step) => (
          <StepCard
            key={step.step_id}
            step={step}
            phaseName={phaseNameFor(step.step_id)}
            confirming={confirmingId === step.step_id}
            busy={mutating}
            onConfirm={handleConfirmStep}
            onDecline={handleDeclineStep}
            onRetry={handleStepRetry}
            onSkip={handleStepSkip}
            onCancel={handleStepCancel}
            onPause={handleStepPause}
            onResume={handleStepResume}
            onEdit={(s) => setEditStepTarget({ step: s })}
          />
        ))}
      </Stack>
    );

    // Status strip only — Approve/Decline live on the timeline node.
    const consentHero = awaitingStep ? (
      <ConsentHeroCard
        step={awaitingStep}
        completedLabel={pausedCompletedLabel}
      />
    ) : null;

    // Chat-first cockpit: Plan owns Approve/Cancel. Classic tabs still use the plan card.
    const needsPlanCard = chatFirst
      ? false
      : ['pending_approval', 'approved', 'paused', 'running', 'failed'].includes(selectedPlan.status);

    return (
      <Stack spacing={1.25}>
        {needsPlanCard && (
          <AITaskPlanCard
            plan={selectedPlan}
            busy={mutating}
            running={phase === 'working'}
            live={phase === 'working'}
            onApprove={handleApprove}
            onDecline={handleDecline}
            onRun={handleRun}
            onPause={handlePause}
            onRetry={handleRetry}
            onEditPlan={handleEditPlan}
            onEditStep={(step) => setEditStepTarget({ step })}
            onConfirmStep={handleConfirmStep}
            onDeclineStep={handleDeclineStep}
            onSwitchToChat={
              onSwitchToChat
                ? () => onSwitchToChat(
                  buildDiscussHandoff(
                    selectedPlan,
                    ledger?.final_response || selectedPlan.final_response,
                  ),
                )
                : undefined
            }
            confirmingId={confirmingId}
          />
        )}

        {!needsPlanCard && !chatFirst && selectedPlan.brief && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              fontSize: '0.75rem',
              px: 0.25,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {selectedPlan.brief}
          </Typography>
        )}

        {!chatFirst && showRunToolbar && (
          <AgentRunToolbar
            {...buildRunToolbarProps()}
            onOpenPlan={() => setTab('tasks')}
            onOpenOutput={() => setTab('results')}
          />
        )}

        <AgentRunSurface
          hideInherited={hideInherited}
          plan={selectedPlan}
          runSteps={runSteps}
          phase={phase}
          live={phase === 'working'}
          defaultListOpen={autonomyDefaultListOpen(autonomyMode, {
            paused: phase === 'paused',
            awaiting: Boolean(awaitingStep),
            finished: phase === 'finished' || phase === 'stopped' || phase === 'error',
          })}
          artifacts={artifacts}
          banner={quietChrome ? null : statusBanner}
          consentHero={consentHero}
          listContent={listContent}
          onOpenOutput={chatFirst
            ? () => handleSegmentChange('output', { user: true })
            : () => setTab('results')}
          busy={mutating}
          confirmingId={confirmingId}
          onConfirmStep={handleConfirmStep}
          onDeclineStep={handleDeclineStep}
          stepActions={{
            onRetry: handleStepRetry,
            onSkip: handleStepSkip,
            onPause: handleStepPause,
            onResume: handleStepResume,
            onCancel: handleStepCancel,
            onEditInPlan: chatFirst
              ? () => handleSegmentChange('plan', { user: true })
              : () => setTab('tasks'),
            onDiscussInPlan: onSwitchToChat
              ? (step) => onSwitchToChat(
                buildDiscussHandoff(
                  selectedPlan,
                  ledger?.final_response || selectedPlan?.final_response,
                  { refine: true, failedStep: step },
                ),
              )
              : null,
          }}
        />

        {isSettledPhase(phase) && (
          <Paper variant="outlined" data-testid="agent-run-health" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
            <Button
              fullWidth
              size="small"
              onClick={() => setRunHealthOpen((v) => !v)}
              endIcon={runHealthOpen
                ? <ExpandLessIcon sx={{ fontSize: 16 }} />
                : <ExpandMoreIcon sx={{ fontSize: 16 }} />}
              sx={{
                justifyContent: 'space-between',
                textTransform: 'none',
                px: 1.25,
                py: 0.75,
                color: 'text.secondary',
                fontWeight: 600,
              }}
              aria-expanded={runHealthOpen}
            >
              {t('runHealth')}
            </Button>
            <Collapse in={runHealthOpen}>
              <Box sx={{ px: 1.25, pb: 1.25 }}>
                {ledger
                  ? <AITaskAuditCard ledger={ledger} />
                  : (
                    <Typography variant="caption" color="text.secondary">
                      {ledgerLoading ? t('boardCoworkerLoading') : t('resultNoConfirmations')}
                    </Typography>
                  )}
              </Box>
            </Collapse>
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
          {t('planTemplate.title')}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.75 }}>
          {selectedPlan
            ? t('planTemplate.hintWithPlan')
            : t('planTemplate.hintNoPlan')}
        </Typography>
        <TextField
          size="small"
          fullWidth
          placeholder={t('planTemplate.namePlaceholder')}
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          disabled={!selectedPlan || templateSaving}
          inputProps={{ 'aria-label': t('planTemplate.namePlaceholder') }}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        <TextField
          size="small"
          fullWidth
          placeholder={t('planTemplate.descriptionPlaceholder')}
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

    const planMeta = planStatusMeta(effectivePlanStatus(selectedPlan));
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
                const stepMeta = stepStatusMeta(step.status, step);
                return (
                  <Stack key={step.step_id} direction="row" alignItems="center" spacing={0.75} sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', minWidth: 52, fontFamily: 'monospace' }}>
                      {step.step_id}
                    </Typography>
                    <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {step.intent || `Step ${step.step_id}`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
                      {formatLatencyMs(step.latency_ms)}
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

    const outputSteps = runSteps.length
      ? runSteps
      : (Array.isArray(selectedPlan.steps) ? selectedPlan.steps : []);
    const awaitingOut = outputSteps.find((s) => s.status === 'awaiting_approval') || null;
    const doneOut = outputSteps.filter(
      (s) => s.status === 'completed' || s.runnable_state === 'completed',
    ).length;
    const leftOut = outputSteps.filter(
      (s) => s.status === 'pending' || s.status === 'awaiting_approval' || s.runnable_state === 'pending',
    ).length;
    const midRun = phase === 'paused'
      || phase === 'working'
      || Boolean(awaitingOut)
      || selectedPlan.status === 'paused'
      || selectedPlan.status === 'running';

    if (midRun && phase !== 'finished' && phase !== 'stopped' && phase !== 'error') {
      const effective = effectivePlanStatus(selectedPlan);
      if (!isRerunnableStatus(effective) && !isRerunnableStatus(selectedPlan.status)) {
        const interimArts = artifacts.filter(Boolean);
        return (
          <Stack spacing={1.25} data-testid="output-lifecycle-card">
            {(phase === 'paused' || awaitingOut) ? (
              <>
                <Alert
                  severity="info"
                  data-testid="paused-banner"
                  sx={{ fontSize: '0.6875rem', py: 0.25, '& .MuiAlert-message': { py: 0 } }}
                >
                  Paused — {doneOut} step{doneOut === 1 ? '' : 's'} completed, {leftOut} to go
                </Alert>
                {awaitingOut ? (
                  <ConsentHeroCard
                    step={awaitingOut}
                    onReviewStep={() => handleSegmentChange('run', { user: true })}
                  />
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                    Waiting on you — open Run to continue.
                  </Typography>
                )}
              </>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                Run in progress ({doneOut}/{outputSteps.length || 0} steps). Results and files will appear here as steps finish.
              </Typography>
            )}
            {interimArts.length > 0 && (
              <Stack spacing={0.75}>
                <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}>
                  Artifacts so far
                </Typography>
                {interimArts.map((artifact) => (
                  <ResultArtifactCard
                    key={artifact.id ?? artifact.name}
                    artifact={artifact}
                    planId={selectedPlan.id}
                    token={token}
                    onDeleted={(id) => setArtifacts((prev) => prev.filter((a) => a.id !== id))}
                  />
                ))}
              </Stack>
            )}
          </Stack>
        );
      }
    }

    if (phase !== 'finished' && phase !== 'stopped' && phase !== 'error') {
      const effective = effectivePlanStatus(selectedPlan);
      if (!isRerunnableStatus(effective) && !isRerunnableStatus(selectedPlan.status)) {
        return (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
              Approve the plan, then run it to see results here.
            </Typography>
          </Box>
        );
      }
    }

    const finalResponse = ledger?.final_response || selectedPlan.final_response;
    const outputActions = resolveOutputActions(selectedPlan, runSteps);
    const effective = effectivePlanStatus(selectedPlan);
    const rerunnable = isRerunnableStatus(selectedPlan.status)
      || isRerunnableStatus(effective)
      || selectedPlan.status === 'approved';

    const exportGaps = (runSteps.length ? runSteps : (selectedPlan.steps || [])).filter((s) => {
      const err = `${s.error || ''} ${typeof s.tool_output === 'object' && s.tool_output?.error ? s.tool_output.error : ''}`;
      return /export refused|no real findings|could not create export/i.test(err);
    });
    const priorRun = selectedPlan.prior_run;
    const priorComparison = priorRun?.comparison;
    const facts = receiptFactsFromActions(outputActions);
    const title = receiptTitleFromAnswer(finalResponse, humanTaskTitle(selectedPlan, t('untitledTask')));
    const state = receiptStateFromPlan(
      runSteps.length
        ? { ...selectedPlan, steps: mergePlanWithRunSteps(selectedPlan, runSteps).steps }
        : selectedPlan,
      phase,
    );
    const stateLabel = state.labelKey ? t(state.labelKey) : (state.label || '');

    return (
      <Stack spacing={1.25}>
        {exportGaps.length > 0 && (
          <Alert
            severity="warning"
            data-testid="output-export-gaps"
            sx={{ typography: 'caption', py: 0.5, '& .MuiAlert-message': { py: 0 } }}
          >
            <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: 0.25 }}>
              {t('resultExportGap')}
            </Typography>
            {exportGaps.map((s) => (
              <Typography key={s.step_id} variant="caption" sx={{ display: 'block' }}>
                {stripEngineJargon(s.intent) || t('resultStepFallback', { id: s.step_id })}
                {': '}
                {s.error || s.tool_output?.error || 'Document export was refused.'}
              </Typography>
            ))}
          </Alert>
        )}
        {priorRun && (
          <Alert
            severity={priorComparison === 'changed' ? 'info' : priorComparison === 'unchanged' ? 'success' : 'info'}
            data-testid="output-rerun-receipt"
            sx={{ typography: 'caption', py: 0.5, '& .MuiAlert-message': { py: 0 } }}
          >
            <Typography variant="caption" sx={{ display: 'block', fontWeight: 600, mb: 0.25 }}>
              {priorComparison === 'changed' && t('resultRerunChanged')}
              {priorComparison === 'unchanged' && t('resultRerunUnchanged')}
              {priorComparison === 'pending' && t('resultRerunPending')}
              {!priorComparison && t('resultRerunAvailable')}
            </Typography>
            {priorComparison === 'changed' && priorRun.prior_final_response && (
              <Typography
                variant="caption"
                component="div"
                sx={{
                  display: 'block',
                  mt: 0.5,
                  maxHeight: 120,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  opacity: 0.85,
                }}
              >
                {priorRun.prior_final_response.slice(0, 800)}
                {priorRun.prior_final_response.length > 800 ? '…' : ''}
              </Typography>
            )}
          </Alert>
        )}

        <OutcomeReceipt
          title={title}
          stateLabel={stateLabel}
          stateColor={state.color || 'default'}
          facts={facts}
          markdown={finalResponse || ''}
        />

        {artifactsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}><CircularProgress size={20} /></Box>
        ) : artifacts.length > 0 ? (
          <Stack spacing={0.75} data-testid="result-artifacts">
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
              {t('resultArtifactsHeading')}
              {' · '}
              {artifacts.length}
            </Typography>
            {artifacts.map((artifact) => (
              <ResultArtifactCard
                key={artifact.id ?? artifact.name}
                artifact={artifact}
                planId={selectedPlan.id}
                token={token}
                onDeleted={(id) => setArtifacts((prev) => prev.filter((a) => a.id !== id))}
              />
            ))}
          </Stack>
        ) : null}

        {/* Classic Results tab: same ≤3 toolbar (no duplicate Actions Paper). */}
        {!chatFirst && (
          <AgentResultToolbar
            hostActions={outputActions}
            rerunnable={rerunnable}
            busy={mutating}
            canExportLedger={Boolean(ledger)}
            canExportResponse={Boolean(finalResponse)}
            onRerun={handleRerun}
            onDiscuss={
              onSwitchToChat
                ? () => onSwitchToChat(buildDiscussHandoff(selectedPlan, finalResponse, { refine: true }))
                : undefined
            }
            onOpenPlan={() => setTab('tasks')}
            onExportLedger={exportLedgerJson}
            onExportResponse={exportFinalResponseMd}
          />
        )}
      </Stack>
    );
  };

  // ── U-1 cockpit — Plan segment handled by AgentReviewSurface (review + inspect).

  const clarifying = selectedPlan?.status === 'discovering';
  const showComposer = Boolean(clarifying);
  // Prefer live runSteps over stale selectedPlan.steps so chips flip as soon
  // as the stream finishes (before/without waiting on refreshPlan).
  const selectedEffective = selectedPlan
    ? effectivePlanStatus(
      runSteps.length
        ? { ...selectedPlan, steps: mergePlanWithRunSteps(selectedPlan, runSteps).steps }
        : selectedPlan,
    )
    : '';
  // Toolbar when runnable or mid/post-run (Approve stays on Plan / Review).
  const showRunToolbar = ['approved', 'running', 'paused', 'failed', 'completed', 'cancelled', 'completed_with_gaps'].includes(
    selectedEffective,
  );

  // Run controls — mounted under cockpit tabs via AgentRunToolbar (chat-first).
  const buildRunToolbarProps = () => {
    const awaitingConsent = (runSteps.length ? runSteps : (selectedPlan?.steps || []))
      .some((s) => s.status === 'awaiting_approval');
    return {
      plan: selectedPlan,
      phase,
      effectiveStatus: selectedEffective,
      busy: mutating,
      awaitingConsent,
      onRun: handleRun,
      onPause: handlePause,
      onStop: handleStop,
      onCancel: handleCancel,
      onRerun: handleRerun,
      onRetry: handleRetry,
      onOpenPlan: () => handleSegmentChange('plan', { user: true }),
      onOpenOutput: () => handleSegmentChange('output', { user: true }),
    };
  };

  const renderChatFirst = () => {
    const statusChip = selectedPlan
      ? runHeaderStatusChip(selectedPlan, runSteps, phase)
      : null;
    const showCockpit = Boolean(selectedPlan) && selectedPlan.status !== 'discovering';
    const liveSteps = runSteps.length ? runSteps : (selectedPlan?.steps || []);
    const awaitingNow = liveSteps.some((s) => s.status === 'awaiting_approval');
    const doneNow = liveSteps.filter((s) => s.status === 'completed' || s.runnable_state === 'completed').length;
    const pendingNow = liveSteps.filter(
      (s) => s.status === 'pending' || s.status === 'awaiting_approval' || s.runnable_state === 'pending',
    ).length;
    const coworkerText = selectedPlan
      ? [
        taskCoworkerLine({
          t,
          phase,
          effective: selectedEffective,
          awaiting: awaitingNow,
          pausedCounts: (phase === 'paused' || selectedEffective === 'paused')
            ? { done: doneNow, pending: pendingNow }
            : null,
        }),
        phase === 'error' && errorMessage ? errorMessage : '',
      ].filter(Boolean).join(' ')
      : '';
    const resultReady = hasTaskOutcome(selectedEffective, phase)
      || Boolean(selectedPlan?.final_response || ledger?.final_response || selectedPlan?.prior_run)
      || resultStickyRef.current === selectedPlan?.id;
    if (selectedPlan?.id && resultReady) resultStickyRef.current = selectedPlan.id;

    const renderCockpitPlan = () => {
      if (!selectedPlan) {
        return (
          <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
            {t('openPlanGraph')}
          </Typography>
        );
      }
      const revisionForThisPlan = pendingRevision?.planId && pendingRevision.planId === selectedPlan.id
        ? String(pendingRevision.brief || '').trim()
        : '';
      return (
        <>
        {revisionForThisPlan ? (
          <Box
            data-testid="plan-revision-from-chat"
            sx={{ mb: 1.25, p: 1.25, border: '1px solid', borderColor: 'primary.light', borderRadius: 1, bgcolor: 'action.hover' }}
            dir="auto"
          >
            <Typography variant="subtitle2" sx={{ fontSize: '0.8rem', mb: 0.5 }}>
              {t('revisionFromChatTitle', 'Revision proposed in Chat')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', mb: 1 }}>
              {revisionForThisPlan}
            </Typography>
            <Stack direction="row" spacing={1}>
              <Button
                size="small"
                variant="contained"
                disabled={mutating}
                onClick={async () => {
                  await handleReplanPlan(revisionForThisPlan);
                  onPendingRevisionConsumed?.();
                }}
              >
                {t('applyRevision', 'Apply revision')}
              </Button>
              <Button size="small" variant="text" disabled={mutating} onClick={() => onPendingRevisionConsumed?.()}>
                {t('dismiss', 'Dismiss')}
              </Button>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
              {t('revisionFromChatHint', 'Applying re-plans this task and shows the diff for review. Nothing runs until you approve.')}
            </Typography>
          </Box>
        ) : null}
        <AgentReviewSurface
          plan={
            runSteps.length
              ? { ...selectedPlan, steps: mergePlanWithRunSteps(selectedPlan, runSteps).steps }
              : selectedPlan
          }
          live={
            phase === 'working'
            || phase === 'paused'
            || ['running', 'paused', 'approved'].includes(selectedPlan?.status)
          }
          confirmingId={confirmingId}
          onConfirmStep={handleConfirmStep}
          onDeclineStep={handleDeclineStep}
          onOpenRun={() => handleSegmentChange('run', { user: true })}
          showLiveHandoff={
            phase === 'working'
            || phase === 'paused'
            || ['running', 'paused', 'awaiting_approval'].includes(selectedPlan?.status)
          }
        />
        </>
      );
    };

    const planToolbar = (() => {
      if (!selectedPlan || selectedPlan.status === 'discovering') return null;
      if (segment !== 'plan') return null;
      const reviewMode = selectedPlan.status === 'pending_approval' || selectedPlan.status === 'cancelled';
      return (
        <AgentPlanToolbar
          plan={selectedPlan}
          mode={reviewMode ? 'review' : 'inspect'}
          busy={mutating}
          onApprove={handleApprove}
          onDecline={handleDecline}
          onDiscuss={
            onSwitchToChat
              ? () => onSwitchToChat(
                buildDiscussHandoff(
                  selectedPlan,
                  ledger?.final_response || selectedPlan.final_response,
                  { refine: true },
                ),
              )
              : undefined
          }
        />
      );
    })();

    const runToolbar = (() => {
      if (!selectedPlan || selectedPlan.status === 'discovering') return null;
      if (segment !== 'run') return null;
      const live = ['approved', 'running', 'paused'].includes(selectedEffective)
        || phase === 'working'
        || phase === 'paused';
      if (!live) return null;
      return <AgentRunToolbar {...buildRunToolbarProps()} />;
    })();

    const resultToolbar = (() => {
      if (!selectedPlan || selectedPlan.status === 'discovering') return null;
      if (segment !== 'output') return null;
      const finalResponse = ledger?.final_response || selectedPlan.final_response;
      const hostActions = resolveOutputActions(selectedPlan, runSteps);
      const effective = effectivePlanStatus(selectedPlan);
      const rerunnable = isRerunnableStatus(selectedPlan.status)
        || isRerunnableStatus(effective)
        || selectedPlan.status === 'approved';
      return (
        <AgentResultToolbar
          hostActions={hostActions}
          rerunnable={rerunnable}
          busy={mutating}
          canExportLedger={Boolean(ledger)}
          canExportResponse={Boolean(finalResponse)}
          onRerun={handleRerun}
          onDiscuss={
            onSwitchToChat
              ? () => onSwitchToChat(buildDiscussHandoff(selectedPlan, finalResponse, { refine: true }))
              : undefined
          }
          onOpenPlan={() => handleSegmentChange('plan', { user: true })}
          onExportLedger={exportLedgerJson}
          onExportResponse={exportFinalResponseMd}
        />
      );
    })();

    const cockpitToolbar = segment === 'plan'
      ? planToolbar
      : segment === 'run'
        ? runToolbar
        : segment === 'output'
          ? resultToolbar
          : null;

    const renderCockpitRun = () => renderRun({ hideInherited: true, quietChrome: true });

    const renderCockpitOutput = () => {
      const journeySteps = runSteps.length
        ? runSteps
        : (Array.isArray(selectedPlan?.steps) ? selectedPlan.steps : []);
      const journeyPlan = selectedPlan
        ? {
          ...selectedPlan,
          steps: journeySteps,
          final_response: selectedPlan.final_response || ledger?.final_response || '',
        }
        : null;
      return (
        <Stack spacing={1.25} data-testid="agent-output-pure">
          {renderResults()}
          <TaskJourney plan={journeyPlan} />
          <ResultProofFold ledger={ledger} />
        </Stack>
      );
    };

    if (!selectedPlan) {
      return (
        <Box
          data-testid="agent-workspace"
          sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
        >
          <TaskBoard
            plans={plans}
            loading={plansLoading}
            loadError={plansLoadError}
            onRetry={loadPlans}
            onSelect={(id) => openPlan(id, { activateRunTab: false })}
            onDelete={handleDeletePlan}
            deletingId={deletingPlanId}
          />
        </Box>
      );
    }

    return (
      <Box
        data-testid="agent-workspace"
        sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
      >
        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{ px: 1, py: 0.75, borderBottom: 1, borderColor: 'divider' }}
        >
          <Button
            size="small"
            onClick={closePlan}
            data-testid="task-board-back"
            sx={{ textTransform: 'none', fontSize: '0.75rem', minWidth: 0, px: 0.75, flexShrink: 0 }}
          >
            {t('boardAllTasks')}
          </Button>
          <Typography
            variant="body2"
            title={String(selectedPlan.brief || '').trim()}
            sx={{
              flex: 1,
              minWidth: 0,
              fontSize: '0.8125rem',
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {humanTaskTitle(selectedPlan, t('untitledTask'))}
          </Typography>
          {statusChip && (
            <Chip
              size="small"
              variant="outlined"
              label={statusChip.label}
              color={statusChip.color}
              data-testid="agent-status-chip"
              sx={{ height: 20, fontSize: '0.625rem', flexShrink: 0, maxWidth: 200 }}
            />
          )}
        </Stack>
        {coworkerText ? (
          <Typography
            data-testid={
              phase === 'paused' || awaitingNow || selectedEffective === 'paused'
                ? 'paused-banner'
                : 'task-coworker-line'
            }
            variant="body2"
            color="text.secondary"
            sx={{ px: 1.25, py: 0.5, fontSize: '0.75rem', borderBottom: 1, borderColor: 'divider' }}
          >
            {coworkerText}
          </Typography>
        ) : null}

        {showComposer && (
          <Box sx={{ px: 1, pt: 1, borderBottom: 1, borderColor: 'divider' }}>
            <DiscoveryComposer
              conversationId={conversationId}
              onPlanReady={handleDiscoveryReady}
              onStarted={handleDiscoveryStarted}
              onSwitchToChat={onSwitchToChat}
              resumePlanId={clarifying ? selectedPlan.id : null}
              resumeTurns={clarifying ? (selectedPlan.discovery_turns || []) : null}
              seedBrief={seedBrief}
              onSeedBriefConsumed={onSeedBriefConsumed}
            />
          </Box>
        )}

        {showCockpit ? (
          <AgentCockpit
            segment={segment}
            onSegment={(value) => handleSegmentChange(value, { user: true })}
            plan={selectedPlan}
            resultReady={resultReady}
            toolbar={cockpitToolbar}
            renderPlan={renderCockpitPlan}
            renderRun={renderCockpitRun}
            renderOutput={renderCockpitOutput}
          />
        ) : (
          <AgentStage
            plan={selectedPlan}
            phase={phase}
            detailLoading={detailLoading}
            clarify={null}
            review={null}
            run={null}
            done={null}
          />
        )}
      </Box>
    );
  };

  const footerStatus = taskFooterStatus(phase, selectedPlan?.status, errorMessage);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, bgcolor: 'background.default' }}>
      <Box
        sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        style={{ zoom: pulsePrefs.contentZoom }}
      >
      {chatFirst ? (
        renderChatFirst()
      ) : (
        <>
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
              <Tab value="templates" label={t('templates')} />
              <Tab value="scheduled" label={t('scheduled')} />
            </Tabs>
          </Box>
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
          <Button
            size="small"
            onClick={() => {
              try { localStorage.setItem(COCKPIT_KEY, 'on'); } catch { /* ignore */ }
              setChatFirst(true);
            }}
            sx={{ textTransform: 'none', fontSize: '0.625rem' }}
          >
            {t('backToChatFirst')}
          </Button>
        </>
      )}

      </Box>
      <PulseWorkspaceFooter
        variant={footerStatus.variant}
        label={footerStatus.label}
        prefs={pulsePrefs}
      />

      {/* W3-F — diff-review consent gate + step edit dialog (survive tab switches) */}
      <PlanDiffReviewDialog
        open={!!diffReview}
        diff={diffReview?.diff}
        busy={mutating}
        onConfirm={confirmDiff}
        onCancel={cancelDiff}
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
  seedBrief: PropTypes.string,
  onSeedBriefConsumed: PropTypes.func,
  /** Chat-proposed revision for an existing plan: { planId, brief }. Applied via replan + diff review. */
  pendingRevision: PropTypes.shape({ planId: PropTypes.string, brief: PropTypes.string }),
  onPendingRevisionConsumed: PropTypes.func,
  onLifecycleStateChange: PropTypes.func,
  onSwitchToChat: PropTypes.func,
  externalTab: PropTypes.oneOf(['tasks', 'run', 'monitor', 'results', 'templates', 'scheduled']),
};

export default AITaskPanel;
