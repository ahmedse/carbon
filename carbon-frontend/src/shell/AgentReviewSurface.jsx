// src/shell/AgentReviewSurface.jsx
// ADR-0043 V6 Plan hero body — structure graph + docked RichContent pane.
// Chrome (renameable label · Approve/Cancel/Discuss) lives in AgentPlanToolbar
// mounted by AgentCockpit under the segment tabs.
import React from 'react';
import PropTypes from 'prop-types';
import { Box } from '@mui/material';
import PlanDagGraph from '../components/graph/PlanDagGraph';

/**
 * @param {object} props
 * @param {object} props.plan
 * @param {boolean} [props.live] — ignored on Plan (status lives on Run)
 * @param {number|string|null} [props.confirmingId]
 * @param {function} [props.onConfirmStep]
 * @param {function} [props.onDeclineStep]
 */
function AgentReviewSurface({
  plan,
  live: _live = false,
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
        sx={{ flex: 1, minHeight: 520, display: 'flex', flexDirection: 'column' }}
      >
        <PlanDagGraph
          plan={plan}
          mode="structure"
          height={560}
          fill
          live={false}
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
