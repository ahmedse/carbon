// src/shell/AITaskPlanCard.jsx
// Sprint 23 W3-B — reviewable plan card for a user-initiated agentic task:
// brief + pattern/source chips + a step list with tool args previews.
// The plan-level consent gate (RULE_21) is explicit: Approve/Decline before
// anything executes; once approved a Run button appears. Outcome copy only
// (RULE_23); theme tokens only (RULE_8).
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import PlayArrowOutlinedIcon from '@mui/icons-material/PlayArrowOutlined';
import { PLAN_STATUS, STEP_STATUS } from './aiTaskStatus';

function JsonPreview({ title, value }) {
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
}

JsonPreview.propTypes = { title: PropTypes.string, value: PropTypes.any };

/**
 * Reviewable plan card.
 * @param {object} props
 * @param {object} props.plan - plan payload (createPlan/getPlan shape)
 * @param {boolean} [props.busy] - an async action is in flight
 * @param {function} [props.onApprove] - () => void, plan-level consent (RULE_21)
 * @param {function} [props.onDecline] - () => void
 * @param {function} [props.onRun] - () => void, start/resume the streamed run
 * @param {boolean} [props.running] - stream is active
 */
function AITaskPlanCard({ plan, busy, running, onApprove, onDecline, onRun }) {
  if (!plan) return null;

  const statusMeta = PLAN_STATUS[plan.status] || PLAN_STATUS.pending_approval;
  const steps = Array.isArray(plan.steps) ? plan.steps : [];
  const reviewable = plan.status === 'pending_approval';
  const runnable = plan.status === 'approved' || plan.status === 'paused';
  const showRun = runnable && !running;

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
          <Typography variant="body2" sx={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
            {plan.brief}
          </Typography>
          <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
            {plan.pattern && <Chip size="small" variant="outlined" label={plan.pattern} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.source && <Chip size="small" variant="outlined" label={`Source · ${plan.source}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.skill_name && <Chip size="small" variant="outlined" label={`Skill · ${plan.skill_name}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {plan.needs_confirmation && (
              <Chip size="small" color="warning" variant="outlined" label="Requires approval" sx={{ height: 18, fontSize: '0.625rem' }} />
            )}
          </Stack>
        </Box>

        <Divider sx={{ my: 0.25 }} />

        {/* Step list with dry-run previews */}
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Steps ({steps.length})
        </Typography>
        <Stack spacing={0.75}>
          {steps.map((step) => {
            const stepMeta = STEP_STATUS[step.status] || STEP_STATUS.pending;
            return (
              <Paper key={step.step_id} variant="outlined" sx={{ borderRadius: 1 }}>
                <Stack direction="row" alignItems="center" spacing={0.75} sx={{ px: 0.875, py: 0.5 }}>
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {step.intent || `Step ${step.step_id}`}
                  </Typography>
                  {step.tool_name && (
                    <Chip size="small" variant="outlined" label={step.tool_name} sx={{ height: 16, fontSize: '0.5625rem' }} />
                  )}
                  <Chip size="small" variant="outlined" label={stepMeta.label} color={stepMeta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
                </Stack>
                {step.tool_args !== null && step.tool_args !== undefined && Object.keys(step.tool_args).length > 0 && (
                  <Box sx={{ px: 1.25, pb: 0.75 }}>
                    <JsonPreview title="Inputs (dry-run preview)" value={step.tool_args} />
                  </Box>
                )}
                {step.status === 'awaiting_approval' && (
                  <Typography variant="caption" color="warning.main" sx={{ display: 'block', px: 1.25, pb: 0.75, fontSize: '0.6875rem' }}>
                    This step writes to Carbon — it is waiting for your approval.
                  </Typography>
                )}
                {step.status === 'failed' && step.error && (
                  <Typography variant="caption" color="error.main" sx={{ display: 'block', px: 1.25, pb: 0.75, fontSize: '0.6875rem' }}>
                    {step.error}
                  </Typography>
                )}
              </Paper>
            );
          })}
        </Stack>

        {steps.length === 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            No steps were planned.
          </Typography>
        )}

        {/* Plan-level consent gate (RULE_21) — nothing executes before approve */}
        {reviewable && (
          <Stack direction="row" spacing={1} sx={{ mt: 0.25 }}>
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
          </Stack>
        )}

        {showRun && (
          <Stack direction="row" spacing={1} sx={{ mt: 0.25 }}>
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
  onApprove: PropTypes.func,
  onDecline: PropTypes.func,
  onRun: PropTypes.func,
};

export default AITaskPlanCard;
