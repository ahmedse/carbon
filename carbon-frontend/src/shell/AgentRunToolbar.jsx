// src/shell/AgentRunToolbar.jsx
// ADR-0043 — Run toolbar under cockpit tabs (actions only).
import React from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  IconButton,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import RefreshIcon from '@mui/icons-material/Refresh';
import ReplayIcon from '@mui/icons-material/Replay';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import { useTranslation } from 'react-i18next';
import { isRerunnableStatus } from './aiTaskStatus';
import { planDisplayLabel } from './AgentPlanToolbar';

/**
 * @param {object} props
 * @param {object|null} props.plan
 * @param {string} [props.phase]
 * @param {string} [props.effectiveStatus]
 * @param {boolean} [props.busy]
 * @param {boolean} [props.awaitingConsent]
 * @param {function} [props.onRun]
 * @param {function} [props.onPause]
 * @param {function} [props.onStop]
 * @param {function} [props.onRerun]
 * @param {function} [props.onRetry]
 * @param {function} [props.onFork]
 * @param {function} [props.onOpenPlan]
 * @param {function} [props.onOpenOutput]
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
  onFork,
  onOpenPlan,
  onOpenOutput,
}) {
  const { t } = useTranslation('ai');
  const running = phase === 'working';
  const consentBlocksPlay = awaitingConsent;
  const runnable = effectiveStatus === 'approved' || effectiveStatus === 'paused';
  const paused = effectiveStatus === 'paused' || phase === 'paused';
  const failed = effectiveStatus === 'failed';
  const rerunnable = isRerunnableStatus(effectiveStatus);
  const showRun = runnable && !running && !consentBlocksPlay;
  const settled = ['finished', 'stopped', 'error'].includes(phase)
    || ['completed', 'cancelled', 'completed_with_gaps', 'failed'].includes(effectiveStatus);
  const playTitle = consentBlocksPlay
    ? 'Continues after you approve or decline'
    : (paused ? t('resumeRun') : t('runPlan'));
  const pauseTitle = consentBlocksPlay
    ? t('pauseBlockedByConsent')
    : t('pauseRun');
  const label = planDisplayLabel(plan, t('untitledPlan'));

  const iconBtn = (title, disabled, onClick, Icon, color) => (
    <Tooltip title={title}>
      <span>
        <IconButton
          size="small"
          aria-label={title}
          disabled={disabled || !onClick}
          onClick={onClick}
          sx={{ p: 0.375 }}
        >
          <Icon sx={{ fontSize: 16, color: color && !disabled ? color : undefined }} />
        </IconButton>
      </span>
    </Tooltip>
  );

  return (
    <Toolbar
      disableGutters
      variant="dense"
      data-testid="agent-run-toolbar"
      sx={{
        width: '100%',
        minHeight: 40,
        gap: 1,
        px: 0,
        flexWrap: 'wrap',
      }}
    >
      <Typography
        data-testid="agent-run-label"
        sx={{
          flex: '1 1 140px',
          minWidth: 0,
          fontSize: '0.8125rem',
          fontWeight: 600,
          lineHeight: 1.3,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={plan?.brief || label}
      >
        {label}
      </Typography>

      <Stack direction="row" spacing={0.25} alignItems="center" flexWrap="wrap" useFlexGap>
        {iconBtn(playTitle, !showRun || busy, onRun, PlayArrowIcon, 'primary.main')}
        {iconBtn(pauseTitle, !running || busy || consentBlocksPlay, onPause, PauseIcon, consentBlocksPlay ? undefined : 'warning.main')}
        {iconBtn(t('stopRun'), (!running && !consentBlocksPlay) || busy, onStop, StopIcon, 'error.main')}
        {iconBtn(t('rerunPlan'), !rerunnable || busy || running, onRerun, RefreshIcon, 'primary.main')}
        {iconBtn(t('retryFailedSteps'), !failed || busy, onRetry, ReplayIcon, 'warning.main')}
        {iconBtn(t('forkReviewable'), !plan || busy, onFork, CallSplitIcon)}

        {settled && onOpenPlan && (
          <Button
            size="small"
            variant="outlined"
            disabled={busy}
            onClick={onOpenPlan}
            sx={{ fontSize: '0.6875rem', textTransform: 'none', ml: 0.5 }}
          >
            {t('editOnPlan')}
          </Button>
        )}
        {settled && onOpenOutput && (
          <Button
            size="small"
            variant="outlined"
            disabled={busy}
            onClick={onOpenOutput}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            {t('openOutput')}
          </Button>
        )}
      </Stack>
    </Toolbar>
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
