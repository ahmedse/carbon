// src/shell/AgentReviewSurface.jsx
// ADR-0043 V6 Plan hero body — live status DAG + docked step pane.
// Chrome (renameable label · Approve/Cancel/Discuss) lives in AgentPlanToolbar
// mounted by AgentCockpit under the segment tabs. Plain-language activity log
// lives on Now only (AgentRunSurface).
import React from 'react';
import PropTypes from 'prop-types';
import { Box } from '@mui/material';
import PlanDagGraph from '../components/graph/PlanDagGraph';

/**
 * @param {object} props
 * @param {object} props.plan — preferably merged with live runSteps
 * @param {boolean} [props.live] — show Live badge while the run is active
 * @param {number|string|null} [props.confirmingId]
 * @param {function} [props.onConfirmStep]
 * @param {function} [props.onDeclineStep]
 */
function AgentReviewSurface({
  plan,
  live = false,
  confirmingId = null,
  onConfirmStep,
  onDeclineStep,
}) {
  return (
    <Box
      data-testid="agent-review-surface"
      sx={{
        minHeight: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box
        data-testid="plan-dag-graph-wrap"
        sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
      >
        <PlanDagGraph
          plan={plan}
          mode="execution"
          height={420}
          fill
          live={Boolean(live)}
          onConfirmStep={onConfirmStep}
          onDeclineStep={onDeclineStep}
          confirmingId={confirmingId}
        />
      </Box>
    </Box>
  );
}

AgentReviewSurface.propTypes = {
  plan: PropTypes.object.isRequired,
  live: PropTypes.bool,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
};

export default AgentReviewSurface;
