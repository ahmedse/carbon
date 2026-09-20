// ConsentHeroCard — pinned Approve/Decline for awaiting_approval (RULE_21).
// Operator-facing consequence copy only (RULE_23). Used on Run (above the fold)
// and Output (lifecycle-truthful paused state).
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Stack, Typography } from '@mui/material';
import { stripEngineJargon } from './humanizeOperatorCopy';

/**
 * @param {object} props
 * @param {object} props.step — RunStep with status awaiting_approval
 * @param {boolean} [props.confirming]
 * @param {function} props.onConfirm — (stepId) => void
 * @param {function} props.onDecline — (stepId) => void
 * @param {string} [props.completedLabel] — e.g. "8 steps completed, 2 to go"
 * @param {function} [props.onReviewStep] — optional jump to Run list
 */
export default function ConsentHeroCard({
  step,
  confirming = false,
  onConfirm,
  onDecline,
  completedLabel = null,
  onReviewStep = null,
}) {
  if (!step || step.status !== 'awaiting_approval') return null;

  const intent = stripEngineJargon(step.intent || `Step ${step.step_id}`);
  const consequence = intent
    ? `This will: ${intent}`
    : 'This action writes to your data. Approve to continue, or decline to skip it.';

  return (
    <Box
      data-testid="consent-hero-card"
      sx={{
        p: 1.25,
        borderRadius: 1,
        border: 1,
        borderColor: 'warning.main',
        bgcolor: 'warning.soft',
      }}
    >
      {completedLabel && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.5 }}
        >
          Paused — {completedLabel}
        </Typography>
      )}
      <Typography
        variant="body2"
        sx={{ fontWeight: 600, fontSize: '0.8125rem', mb: 0.5 }}
      >
        Needs your approval
      </Typography>
      <Typography
        variant="caption"
        sx={{ display: 'block', fontSize: '0.75rem', mb: 1, color: 'text.primary' }}
      >
        {consequence}
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', fontSize: '0.6875rem', mb: 1 }}
      >
        Approve to run this step, or decline to skip it. Nothing else continues until you choose.
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Button
          size="small"
          variant="contained"
          color="warning"
          disabled={confirming}
          onClick={() => onConfirm(step.step_id)}
          sx={{ fontSize: '0.75rem', textTransform: 'none', fontWeight: 600 }}
        >
          {confirming ? 'Approving…' : 'Approve'}
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="inherit"
          disabled={confirming}
          onClick={() => onDecline(step.step_id)}
          sx={{ fontSize: '0.75rem', textTransform: 'none' }}
        >
          Decline
        </Button>
        {onReviewStep && (
          <Button
            size="small"
            variant="text"
            onClick={onReviewStep}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            Review step
          </Button>
        )}
      </Stack>
    </Box>
  );
}

ConsentHeroCard.propTypes = {
  step: PropTypes.object,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func.isRequired,
  onDecline: PropTypes.func.isRequired,
  completedLabel: PropTypes.string,
  onReviewStep: PropTypes.func,
};
