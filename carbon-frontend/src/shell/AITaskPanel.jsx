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
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddOutlinedIcon from '@mui/icons-material/AddOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import StopIcon from '@mui/icons-material/Stop';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  approvePlan,
  confirmPlanStep,
  createPlan,
  declinePlan,
  declinePlanStep,
  editPlan,
  editPlanStep,
  forkPlan,
  getPlan,
  getPlanLedger,
  listPlans,
  listPlanTemplates,
  instantiatePlanTemplate,
  pausePlan,
  promotePlanTemplate,
  resumePlanStream,
  runPlanStream,
  stopPlan,
} from '../api/aiWorkspace';
import { buildPlanPhases, summarizePlanDiff } from '../utils/planGraph';
import AITaskPlanCard from './AITaskPlanCard';
import AITaskAuditCard from './AITaskAuditCard';
import PlanDiffReviewDialog from './PlanDiffReviewDialog';
import StepEditDialog from './StepEditDialog';

dayjs.extend(utc);
dayjs.extend(timezone);

const TASK_TAB_KEY = 'carbon-ai-task-tab';
const PROJECT_TIMEZONE = 'Africa/Cairo';

function formatWhen(value) {
  if (!value) return '';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.tz(PROJECT_TIMEZONE).format('MMM D, YYYY · HH:mm') : '';
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

function StepCard({ step, phaseName, confirming, onConfirm, onDecline }) {
  const [open, setOpen] = useState(true);
  const meta = STEP_STATUS_ICON[step.status] || { label: 'Pending', color: 'default' };
  const showBody = open || step.status === 'awaiting_approval' || step.status === 'failed';
  const hasOutput = step.tool_output !== null && step.tool_output !== undefined && String(step.tool_output).length > 0;

  const renderJson = (title, value) => {
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
            overflow: 'auto',
            whiteSpace: 'pre',
          }}
        >
          {text}
        </Box>
      </Box>
    );
  };

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
          <Chip size="small" variant="outlined" color="secondary" label={step.agent_role.replace(/_/g, ' ')} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        {step.tool_name && (
          <Chip size="small" variant="outlined" label={step.tool_name} sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
      </Stack>

      {showBody && (
        <Box sx={{ px: 1.25, pb: 0.875 }}>
          {renderJson('Input', step.tool_args)}
          {hasOutput && renderJson('Output', step.tool_output)}
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

/**
 * Agentic task orchestration panel.
 * @param {object} props
 * @param {string|null} props.conversationId - anchor conversation UUID
 * @param {string|null} props.focusPlanId - plan to auto-open (chat "Open in Tasks" jump)
 * @param {function} props.onFocusPlanConsumed - called once the focus is handled
 */
function AITaskPanel({ conversationId, focusPlanId = null, onFocusPlanConsumed }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
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
  const [brief, setBrief] = useState('');
  const [creating, setCreating] = useState(false);

  // Selected plan detail + run state
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [runSteps, setRunSteps] = useState([]);
  const [phase, setPhase] = useState('idle'); // idle|working|paused|finished|stopped|error
  const [errorMessage, setErrorMessage] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [ledgerLoading, setLedgerLoading] = useState(false);

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

  const runPhaseRef = useRef(phase);
  runPhaseRef.current = phase;

  const handleTabChange = useCallback((e, value) => {
    setTab(value);
    try {
      localStorage.setItem(TASK_TAB_KEY, value);
    } catch {
      // storage may be unavailable — tab still switches in-memory
    }
  }, []);

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
    if (!selectedPlan || phase !== 'working') return undefined;
    const timer = setInterval(() => {
      refreshPlan(selectedPlan.id);
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
            tool_output: null,
            error: null,
          }))
        : [],
    );
    setPhase(plan.status === 'completed' ? 'finished' : plan.status === 'cancelled' ? 'stopped' : plan.status === 'failed' ? 'error' : 'idle');
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

  const handleCreate = async () => {
    const trimmed = brief.trim();
    if (!trimmed) return;
    setCreating(true);
    try {
      const plan = await createPlan(token, { brief: trimmed, conversation_id: conversationId || '' });
      setBrief('');
      await loadPlans();
      await openPlan(plan.id);
    } catch (err) {
      notifyFromErrorRef.current(err, 'Could not create the plan');
    } finally {
      setCreating(false);
    }
  };

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
      await confirmPlanStep(token, selectedPlan.id, stepId);
      upsertStep({ step_id: stepId, status: 'completed' });
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

  // User reviewed the diff and keeps the revised plan — it stays
  // pending_approval and needs the plan consent gate again before running.
  const confirmDiff = () => {
    if (!diffReview) return;
    applyPlanToView(diffReview.plan);
    setPlans((prev) =>
      prev.map((p) => (p.id === diffReview.plan.id ? { ...p, status: diffReview.plan.status } : p)),
    );
    notifyRef.current('Changes kept — the plan needs your approval again.', 'info');
    setDiffReview(null);
  };

  const handlePause = async () => {
    if (!selectedPlan) return;
    setMutating(true);
    try {
      const updated = await pausePlan(token, selectedPlan.id);
      setSelectedPlan(updated);
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

  // ── Tasks tab: composer + list ────────────────────────────────────────
  const renderTasks = () => (
    <Stack spacing={1.25}>
      {/* New-plan composer */}
      <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', mb: 0.75 }}>
          Plan a task
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.75 }}>
          Describe the outcome — the assistant plans the steps first. Nothing executes until you approve the plan and run it.
        </Typography>
        <TextField
          multiline
          minRows={2}
          maxRows={4}
          fullWidth
          size="small"
          placeholder="e.g. Audit the emissions dataset for duplicates and create a rule to prevent them."
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          inputProps={{ 'aria-label': 'Task brief' }}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        <Button
          size="small"
          variant="contained"
          startIcon={<AddOutlinedIcon sx={{ fontSize: 14 }} />}
          disabled={creating || !brief.trim()}
          onClick={handleCreate}
          sx={{ mt: 1, fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {creating ? 'Planning…' : 'Create plan'}
        </Button>
      </Paper>

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
            return (
              <Paper
                key={plan.id}
                variant="outlined"
                sx={{ p: 1, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                onClick={() => openPlan(plan.id)}
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
    return (
      <Stack spacing={1.25}>
        <AITaskPlanCard
          plan={selectedPlan}
          busy={creating || mutating}
          running={phase === 'working'}
          live={phase === 'working'}
          onApprove={handleApprove}
          onDecline={handleDecline}
          onRun={handleRun}
          onPause={handlePause}
          onFork={handleFork}
          onEditPlan={handleEditPlan}
          onEditStep={(step) => setEditStepTarget({ step })}
        />

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
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleInstantiateTemplate(tpl.id)}
                  sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
                >
                  Use
                </Button>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  );

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
          <Tab value="templates" label="Templates" />
        </Tabs>
      </Box>

      {/* Tab content */}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
        {tab === 'tasks' ? renderTasks() : tab === 'run' ? renderRun() : renderTemplates()}
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
    </Box>
  );
}

AITaskPanel.propTypes = {
  conversationId: PropTypes.string,
};

export default AITaskPanel;
