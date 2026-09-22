// ConsentHeroCard — status strip when a step awaits approval (RULE_21).
// Approve / Decline live in the step detail drawer (no duplicate buttons).
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Typography } from '@mui/material';
import { stripEngineJargon } from './humanizeOperatorCopy';
import { toolLabel } from './aiTaskStatus';
import { presentToolLabel } from './presentationPlane';

function actionLabel(step) {
  const args = step?.tool_args;
  const api = args && typeof args === 'object' ? args.api_name : '';
  if (api) {
    return (
      presentToolLabel('call_host_api', { audience: 'operator', apiName: api })
      || toolLabel(api)
      || String(api).replace(/_/g, ' ')
    );
  }
  const fromTool = presentToolLabel(step?.tool_name, { audience: 'operator', apiName: api });
  if (fromTool) return fromTool;
  return stripEngineJargon(step?.intent || `Step ${step?.step_id}`);
}

/**
 * @param {object} props
 * @param {object} props.step — RunStep with status awaiting_approval
 * @param {string} [props.completedLabel] — e.g. "8 steps completed, 2 to go"
 * @param {function} [props.onReviewStep] — open step detail drawer
 */
export default function ConsentHeroCard({
  step,
  completedLabel = null,
  onReviewStep = null,
  // Legacy props kept so callers stay compile-clean; buttons removed.
  confirming = false, // eslint-disable-line no-unused-vars
  onConfirm = null, // eslint-disable-line no-unused-vars
  onDecline = null, // eslint-disable-line no-unused-vars
}) {
  if (!step || step.status !== 'awaiting_approval') return null;

  const label = actionLabel(step);

  return (
    <Box
      data-testid="consent-hero-card"
      data-consent-mode="status-strip"
      sx={{
        px: 1.25,
        py: 0.75,
        borderRadius: 1,
        border: 1,
        borderColor: 'warning.main',
        bgcolor: 'warning.soft',
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        flexWrap: 'wrap',
      }}
    >
      <Typography
        variant="caption"
        sx={{ fontWeight: 600, fontSize: '0.75rem', flex: '1 1 160px', minWidth: 0 }}
      >
        Needs your approval
        {label ? ` — ${label}` : ''}
        {completedLabel ? ` · Paused — ${completedLabel}` : ''}
        {' · '}
        Approve or decline in the step details panel.
      </Typography>
      {onReviewStep && (
        <Button
          size="small"
          variant="text"
          onClick={onReviewStep}
          sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0 }}
        >
          Open step details
        </Button>
      )}
    </Box>
  );
}

ConsentHeroCard.propTypes = {
  step: PropTypes.object,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
  completedLabel: PropTypes.string,
  onReviewStep: PropTypes.func,
};
