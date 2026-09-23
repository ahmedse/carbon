// src/shell/AgentRunToolbar.jsx
// Now view — words only. Pause / Stop while working. No media deck.
import React from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  Stack,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { isRerunnableStatus } from './aiTaskStatus';

/**
 * @param {object} props
 */
export default function AgentRunToolbar({
  plan,
  phase = 'idle',
  effectiveStatus = '',
  busy = false,
  awaitingConsent = false,
  onRun,
  onPause,
  onStop,
  onRerun,
  onRetry,
}) {
  const { t } = useTranslation('ai');
  const running = phase === 'working';
  const consentBlocksPlay = awaitingConsent;
  const runnable = effectiveStatus === 'approved' || effectiveStatus === 'paused';
  const paused = effectiveStatus === 'paused' || phase === 'paused';
  const failed = effectiveStatus === 'failed';
  const rerunnable = isRerunnableStatus(effectiveStatus);
  const showStart = runnable && !running && !consentBlocksPlay;
  const startLabel = paused ? t('resumeRun') : t('startWork');
  const startAria = paused ? t('resumeRun') : t('runPlan');

  const actions = [];
  if (showStart && onRun) {
    actions.push({
      key: 'start',
      testId: 'agent-run-play',
      label: startLabel,
      aria: startAria,
      onClick: onRun,
      variant: 'contained',
    });
  }
  if (running && onPause) {
    actions.push({
      key: 'pause',
      testId: 'agent-run-pause',
      label: t('pauseWord'),
      aria: t('pauseRun'),
      onClick: onPause,
      disabled: busy || consentBlocksPlay,
      variant: 'text',
    });
  }
  if ((running || consentBlocksPlay) && onStop) {
    actions.push({
      key: 'stop',
      testId: 'agent-run-stop',
      label: t('stopWord'),
      aria: 'Stop run',
      onClick: onStop,
      color: 'error',
      variant: 'text',
    });
  }
  if (rerunnable && onRerun && !running) {
    actions.push({
      key: 'rerun',
      testId: 'agent-run-rerun',
      label: t('rerunPlanShort'),
      aria: t('rerunPlan'),
      onClick: onRerun,
      variant: 'outlined',
    });
  }
  if (failed && onRetry) {
    actions.push({
      key: 'retry',
      testId: 'agent-run-retry',
      label: t('retry'),
      aria: t('retryFailedSteps'),
      onClick: onRetry,
      variant: 'outlined',
    });
  }

  if (!actions.length) return null;

  return (
    <Stack
      direction="row"
      spacing={0.75}
      alignItems="center"
      data-testid="agent-run-toolbar"
      sx={{ minHeight: 28, flexWrap: 'wrap' }}
    >
      {actions.map((item) => (
        <Button
          key={item.key}
          size="small"
          variant={item.variant || 'text'}
          color={item.color || 'primary'}
          disabled={busy || item.disabled}
          onClick={item.onClick}
          data-testid={item.testId}
          aria-label={item.aria || item.label}
          sx={{ fontSize: '0.75rem', textTransform: 'none', minHeight: 28, py: 0.25 }}
        >
          {item.label}
        </Button>
      ))}
      {plan?.id ? (
        <span data-testid="agent-run-label" hidden>
          {plan.brief || ''}
        </span>
      ) : null}
    </Stack>
  );
}

AgentRunToolbar.propTypes = {
  plan: PropTypes.object,
  phase: PropTypes.string,
  effectiveStatus: PropTypes.string,
  busy: PropTypes.bool,
  awaitingConsent: PropTypes.bool,
  onRun: PropTypes.func,
  onPause: PropTypes.func,
  onStop: PropTypes.func,
  onRerun: PropTypes.func,
  onRetry: PropTypes.func,
  onFork: PropTypes.func,
  onOpenPlan: PropTypes.func,
  onOpenOutput: PropTypes.func,
};
