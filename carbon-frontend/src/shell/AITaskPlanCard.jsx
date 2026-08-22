// src/shell/AITaskPlanCard.jsx
// Sprint 23 W3-B + W3-F — reviewable plan card for a user-initiated agentic
// task: brief + pattern/source chips + a step list with tool args previews,
// a plan preview (live d3 DAG + static Mermaid diagram), and lifecycle
// controls (edit / pause / resume / fork) wired to the W3-C endpoints.
//
// The plan-level consent gate (RULE_21) is explicit: Approve/Decline before
// anything executes; once approved a Run button appears. Every edit opens the
// diff-review gate in the parent BEFORE the revised plan is re-approved.
// Outcome copy only (RULE_23); theme tokens only (RULE_8).
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowOutlinedIcon from '@mui/icons-material/PlayArrowOutlined';
import { PLAN_STATUS, STEP_STATUS, agentRoleLabel, toolLabel } from './aiTaskStatus';
import PlanDagGraph from '../components/graph/PlanDagGraph';
import PlanMermaidPreview from '../components/graph/PlanMermaidPreview';
import { buildPlanPhases } from '../utils/planGraph';

// W3-G — human-readable key→value input rows (not raw JSON). Flattens a
// top-level object into labelled rows so `{ dataset: 'emissions' }` reads as
// "Dataset · emissions" instead of a JSON blob.
function KeyValuePreview({ title, value }) {
  if (value === null || value === undefined) return null;
  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const entries = isObject ? Object.entries(value) : null;
  if (entries && entries.length === 0) return null;
  if (!entries && String(value).length === 0) return null;

  return (
    <Box sx={{ mt: 0.5 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title}
      </Typography>
      {entries ? (
        <Stack spacing={0.25} sx={{ mt: 0.25 }}>
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
        <Typography sx={{ fontSize: '0.6875rem', mt: 0.25, wordBreak: 'break-word' }}>
          {String(value)}
        </Typography>
      )}
    </Box>
  );
}

KeyValuePreview.propTypes = { title: PropTypes.string, value: PropTypes.any };

/**
 * Reviewable plan card with lifecycle controls + live plan DAG.
 * @param {object} props
 * @param {object} props.plan - plan payload (createPlan/getPlan shape)
 * @param {boolean} [props.busy] - an async action is in flight
 * @param {function} [props.onApprove] - () => void, plan-level consent (RULE_21)
 * @param {function} [props.onDecline] - () => void
 * @param {function} [props.onRun] - () => void, start/resume the streamed run
 * @param {function} [props.onPause] - () => void, pause a running plan
 * @param {function} [props.onFork] - () => void, fork into a reviewable copy
 * @param {function} [props.onEditPlan] - (newBrief) => void
 * @param {function} [props.onEditStep] - (step) => void
 * @param {function} [props.onConfirmStep] - (stepId) => void, per-step consent
 * @param {function} [props.onDeclineStep] - (stepId) => void, per-step skip
 * @param {number|string|null} [props.confirmingId] - step currently consenting
 * @param {boolean} [props.running] - stream is active
 * @param {boolean} [props.live] - run is live (DAG shows the Live badge)
 */
function AITaskPlanCard({
  plan,
  busy,
  running,
  live = false,
  onApprove,
  onDecline,
  onRun,
  onPause,
  onFork,
  onEditPlan,
  onEditStep,
  onConfirmStep,
  onDeclineStep,
  confirmingId = null,
}) {
  const [editBriefOpen, setEditBriefOpen] = useState(false);
  const [editBriefValue, setEditBriefValue] = useState('');
  const [previewMode, setPreviewMode] = useState('graph');

  if (!plan) return null;

  const statusMeta = PLAN_STATUS[plan.status] || PLAN_STATUS.pending_approval;
  const steps = Array.isArray(plan.steps) ? plan.steps : [];
  const { phases } = buildPlanPhases(plan);
  const reviewable = plan.status === 'pending_approval';
  const runnable = plan.status === 'approved' || plan.status === 'paused';
  const showRun = runnable && !running;
  const editable = plan.status !== 'running' && !running;
  // W5-E: while a run is live the graph is promoted ABOVE the step stream at a
  // taller fixed height (progress at a glance); when reviewing a non-live plan
  // it stays compact below the step list.
  const graphHeight = live ? 420 : 300;
  const renderPlanPreview = (sx = {}) =>
    steps.length > 0 && (
      <Box sx={{ mt: 0.25, ...sx }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1, fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Plan preview
          </Typography>
          <ToggleButtonGroup
            value={previewMode}
            exclusive
            size="small"
            onChange={(_e, next) => {
              if (next !== null) setPreviewMode(next);
            }}
            aria-label="Plan preview view"
          >
            <ToggleButton value="graph" sx={{ fontSize: '0.625rem', py: 0.125, px: 0.75 }}>Graph</ToggleButton>
            <ToggleButton value="diagram" sx={{ fontSize: '0.625rem', py: 0.125, px: 0.75 }}>Diagram</ToggleButton>
          </ToggleButtonGroup>
        </Stack>
        <Box sx={{ mt: 0.75 }}>
          {previewMode === 'graph' ? (
            <PlanDagGraph plan={plan} height={graphHeight} live={live} fill={false} />
          ) : (
            <PlanMermaidPreview plan={plan} />
          )}
        </Box>
      </Box>
    );

  const openEditBrief = () => {
    setEditBriefValue(plan.brief || '');
    setEditBriefOpen(true);
  };

  const saveEditBrief = () => {
    const next = editBriefValue.trim();
    if (!next || !onEditPlan) return;
    onEditPlan(next);
    setEditBriefOpen(false);
  };

  return (
    <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875, borderBottom: 1, borderColor: 'divider' }}>
        <AssignmentOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          Task plan
        </Typography>
        {running ? (
          <CircularProgress size={14} thickness={6} sx={{ color: 'primary.main' }} />
        ) : (
          <Chip size="small" label={statusMeta.label} color={statusMeta.color} variant="outlined" sx={{ height: 18, fontSize: '0.625rem' }} />
        )}
      </Stack>

      <Stack spacing={1.25} sx={{ p: 1.25 }}>
        {/* Brief + provenance chips */}
        <Box>
          {editBriefOpen ? (
            <Stack spacing={0.75}>
              <TextField
                multiline
                minRows={2}
                maxRows={4}
                fullWidth
                size="small"
                value={editBriefValue}
                onChange={(e) => setEditBriefValue(e.target.value)}
                inputProps={{ 'aria-label': 'Plan brief' }}
                sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
              />
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="contained"
                  disabled={busy || !editBriefValue.trim()}
                  onClick={saveEditBrief}
                  sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                >
                  {busy ? 'Updating…' : 'Apply changes'}
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={busy}
                  onClick={() => setEditBriefOpen(false)}
                  sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                >
                  Cancel
                </Button>
              </Stack>
            </Stack>
          ) : (
            <>
              <Typography variant="body2" sx={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                {plan.brief}
              </Typography>
              {editable && onEditPlan && (
                <Tooltip title="Edit the plan brief">
                  <IconButton
                    size="small"
                    onClick={openEditBrief}
                    aria-label="Edit plan"
                    sx={{ p: 0.25, mt: 0.25 }}
                  >
                    <EditOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                  </IconButton>
                </Tooltip>
              )}
            </>
          )}
          <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
            {plan.pattern && <Chip size="small" variant="outlined" label={plan.pattern} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.source && <Chip size="small" variant="outlined" label={`Source · ${plan.source}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.skill_name && <Chip size="small" variant="outlined" label={`Skill · ${plan.skill_name}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.forked_from && <Chip size="small" variant="outlined" label="Forked copy" sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.needs_confirmation && (
              <Chip size="small" color="warning" variant="outlined" label="Requires approval" sx={{ height: 18, fontSize: '0.625rem' }} />
            )}
          </Stack>
        </Box>

        <Divider sx={{ my: 0.25 }} />

        {/* Live run — graph FIRST, above the step stream (W5-E prominence). */}
        {live && renderPlanPreview({ mb: 0.5 })}

        {/* Workflow stages (phases) with steps + agent assignments */}
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1, fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Workflow · {steps.length} step{steps.length === 1 ? '' : 's'}
          </Typography>
          {phases.length > 1 && (
            <Chip
              size="small"
              variant="outlined"
              label={`${phases.length} stages`}
              sx={{ height: 16, fontSize: '0.5625rem' }}
            />
          )}
        </Stack>
        <Stack spacing={0.75}>
          {phases.map((phase) => (
            <Box key={phase.phase_id}>
              <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 0.375 }}>
                <Typography variant="caption" sx={{ flex: 1, fontSize: '0.6875rem', fontWeight: 600, color: 'text.primary' }}>
                  {phase.name}
                </Typography>
                <Chip
                  size="small"
                  variant="outlined"
                  color={phase.strategy === 'parallel' ? 'primary' : 'default'}
                  label={phase.strategy === 'parallel' ? 'Parallel' : 'Sequential'}
                  sx={{ height: 15, fontSize: '0.5625rem' }}
                />
              </Stack>
              {phase.goal && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.375, fontSize: '0.625rem' }}>
                  {phase.goal}
                </Typography>
              )}
              <Stack spacing={0.5}>
                {phase.steps.map((step) => {
                  const stepMeta = STEP_STATUS[step.status] || STEP_STATUS.pending;
                  return (
                    <Paper key={step.step_id} variant="outlined" sx={{ borderRadius: 1 }}>
                      <Stack direction="row" alignItems="center" spacing={0.75} sx={{ px: 0.875, py: 0.5 }}>
                        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {step.intent || `Step ${step.step_id}`}
                        </Typography>
                        {step.agent_role && (
                          <Chip
                            size="small"
                            variant="outlined"
                            color="secondary"
                            label={`Agent ${step.step_id + 1} · ${agentRoleLabel(step.agent_role)}`}
                            sx={{ height: 16, fontSize: '0.5625rem' }}
                          />
                        )}
                        {step.tool_name && (
                          <Chip size="small" variant="outlined" label={toolLabel(step.tool_name)} sx={{ height: 16, fontSize: '0.5625rem' }} />
                        )}
                        <Chip size="small" variant="outlined" label={stepMeta.label} color={stepMeta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
                        {editable && onEditStep && (
                          <Tooltip title="Edit this step">
                            <IconButton
                              size="small"
                              onClick={() => onEditStep(step)}
                              aria-label={`Edit step ${step.step_id}`}
                              sx={{ p: 0.125 }}
                            >
                              <EditOutlinedIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Stack>
                      {step.tool_args !== null && step.tool_args !== undefined && Object.keys(step.tool_args).length > 0 && (
                        <Box sx={{ px: 1.25, pb: 0.75 }}>
                          <KeyValuePreview title="Input" value={step.tool_args} />
                        </Box>
                      )}
                      {step.status === 'awaiting_approval' && (
                        <Box sx={{ px: 1.25, pb: 0.75 }}>
                          <Box sx={{ p: 1, borderRadius: 1, bgcolor: 'warning.soft' }}>
                            <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.5 }}>
                              This step writes to Carbon — approve it to run, or decline to skip it.
                            </Typography>
                            <Stack direction="row" spacing={1}>
                              <Button
                                size="small"
                                variant="contained"
                                disabled={busy || confirmingId === step.step_id}
                                onClick={() => onConfirmStep && onConfirmStep(step.step_id)}
                                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                              >
                                {confirmingId === step.step_id ? 'Approving…' : 'Approve'}
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={busy || confirmingId === step.step_id}
                                onClick={() => onDeclineStep && onDeclineStep(step.step_id)}
                                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
                              >
                                Decline
                              </Button>
                            </Stack>
                          </Box>
                        </Box>
                      )}
                      {step.status === 'failed' && step.error && (
                        <Typography variant="caption" color="error.main" sx={{ display: 'block', px: 1.25, pb: 0.75, fontSize: '0.6875rem' }}>
                          {step.error}
                        </Typography>
                      )}
                    </Paper>
                  );
                })}
                {phase.steps.length === 0 && (
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                    No steps in this stage.
                  </Typography>
                )}
              </Stack>
            </Box>
          ))}
        </Stack>

        {steps.length === 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            No steps were planned.
          </Typography>
        )}

        {/* Plan preview — below the step list for non-live review. */}
        {!live && renderPlanPreview()}

        {/* Plan-level consent gate (RULE_21) — nothing executes before approve */}
        {reviewable && (
          <Stack direction="row" spacing={1} sx={{ mt: 0.25, flexWrap: 'wrap', rowGap: 0.5 }}>
            <Button
              size="small"
              variant="contained"
              disabled={busy}
              onClick={onApprove}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {busy ? 'Approving…' : 'Approve plan'}
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              disabled={busy}
              onClick={onDecline}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Decline
            </Button>
            {onFork && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<CallSplitIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onFork}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                Fork
              </Button>
            )}
          </Stack>
        )}

        {showRun && (
          <Stack direction="row" spacing={1} sx={{ mt: 0.25, flexWrap: 'wrap', rowGap: 0.5 }}>
            <Button
              size="small"
              variant="contained"
              startIcon={<PlayArrowOutlinedIcon sx={{ fontSize: 14 }} />}
              disabled={busy}
              onClick={onRun}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {plan.status === 'paused' ? 'Resume run' : 'Run plan'}
            </Button>
            {onFork && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<CallSplitIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onFork}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                Fork
              </Button>
            )}
          </Stack>
        )}

        {running && onPause && (
          <Stack direction="row" spacing={1} sx={{ mt: 0.25 }}>
            <Button
              size="small"
              variant="outlined"
              color="warning"
              startIcon={<PauseIcon sx={{ fontSize: 14 }} />}
              disabled={busy}
              onClick={onPause}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Pause run
            </Button>
          </Stack>
        )}

        {!reviewable && !showRun && !running && (
          <Stack direction="row" spacing={1} sx={{ mt: 0.25, flexWrap: 'wrap', rowGap: 0.5 }}>
            {onFork && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<CallSplitIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onFork}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                Fork
              </Button>
            )}
          </Stack>
        )}

        {plan.status === 'completed' && plan.final_response && (
          <Tooltip title={plan.final_response}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem' }}>
              Completed — see the audit ledger for the outcome.
            </Typography>
          </Tooltip>
        )}
        {plan.status === 'cancelled' && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            This plan was cancelled — nothing was executed.
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

AITaskPlanCard.propTypes = {
  plan: PropTypes.object,
  busy: PropTypes.bool,
  running: PropTypes.bool,
  live: PropTypes.bool,
  onApprove: PropTypes.func,
  onDecline: PropTypes.func,
  onRun: PropTypes.func,
  onPause: PropTypes.func,
  onFork: PropTypes.func,
  onEditPlan: PropTypes.func,
  onEditStep: PropTypes.func,
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

export default AITaskPlanCard;
