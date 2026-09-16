// src/shell/AgentStage.jsx
// Chat-first Agent remake — one stage body driven by plan.status.
// Parent owns all handlers; this is pure layout routing (RULE_2).
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import { effectivePlanStatus } from './aiTaskStatus';

/** Just-settled session phases (not completed status) keep run banners. */
const SETTLING_PHASES = new Set(['finished', 'stopped', 'error']);

export function stageForStatus(status, phase) {
  // Live execution always on Run.
  if (phase === 'working' || phase === 'paused') return 'run';
  // Terminal success → Done / Output (picker open or post-refresh).
  if (status === 'completed' || status === 'completed_with_gaps') return 'done';
  // Consent still open → stay on Run even if the row lagged to completed.
  if (status === 'paused') return 'run';
  // In-session settle banners before status catches up.
  if (phase && SETTLING_PHASES.has(phase)) return 'run';
  if (!status) return 'idle';
  if (status === 'discovering') return 'clarify';
  if (status === 'pending_approval' || status === 'cancelled') return 'review';
  if (
    status === 'approved'
    || status === 'running'
    || status === 'paused'
    || status === 'failed'
  ) return 'run';
  return 'idle';
}

/**
 * @param {object} props
 * @param {object|null} props.plan
 * @param {string} [props.phase]
 * @param {boolean} props.detailLoading
 * @param {React.ReactNode} props.clarify
 * @param {React.ReactNode} props.review
 * @param {React.ReactNode} props.run
 * @param {React.ReactNode} props.done
 * @param {React.ReactNode} [props.idleHint]
 */
function AgentStage({
  plan,
  phase,
  detailLoading,
  clarify,
  review,
  run,
  done,
  idleHint,
}) {
  const stage = stageForStatus(effectivePlanStatus(plan) || plan?.status, phase);

  if (detailLoading) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
        Loading task…
      </Typography>
    );
  }

  let body = null;
  switch (stage) {
    case 'clarify':
      body = clarify || (
        <Typography variant="body2" color="text.secondary" sx={{ py: 1, fontSize: '0.75rem' }}>
          Answer Pulse above, or click Plan now to build the reviewable plan.
        </Typography>
      );
      break;
    case 'review':
      body = review;
      break;
    case 'run':
      body = run;
      break;
    case 'done':
      body = done;
      break;
    default:
      body = (
        <Box>
          {idleHint || (
            <Typography variant="body2" color="text.secondary" sx={{ py: 1, fontSize: '0.75rem' }}>
              Describe an outcome above. Pulse will clarify if needed, then show a plan to approve.
            </Typography>
          )}
          {clarify}
        </Box>
      );
  }

  return (
    <Box data-testid="agent-stage" data-stage={stage} sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
      {body}
    </Box>
  );
}

AgentStage.propTypes = {
  plan: PropTypes.object,
  phase: PropTypes.string,
  detailLoading: PropTypes.bool,
  clarify: PropTypes.node,
  review: PropTypes.node,
  run: PropTypes.node,
  done: PropTypes.node,
  idleHint: PropTypes.node,
};

export default AgentStage;
