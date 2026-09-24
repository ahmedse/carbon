// Per-step controls (W-7) + next-move guidance for the Now step drawer.
// State-driven: which buttons show comes from the step status the API returned.
import React from 'react';
import PropTypes from 'prop-types';
import { IconButton, Stack, Tooltip } from '@mui/material';
import ReplayIcon from '@mui/icons-material/Replay';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CloseIcon from '@mui/icons-material/Close';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import { useTranslation } from 'react-i18next';

export default function StepActionBar({
  step,
  busy = false,
  onRetry = null,
  onSkip = null,
  onPause = null,
  onResume = null,
  onCancel = null,
  onEditInPlan = null,
  onDiscussInPlan = null,
}) {
  const { t } = useTranslation('ai');
  if (!step) return null;
  const s = step.status;
  const id = step.step_id;

  const primary = [];
  const secondary = [];

  if (onRetry) primary.push({ key: 'retry', label: t('stepRetry'), icon: <ReplayIcon />, onClick: () => onRetry(id), variant: 'contained' });
  if (onPause) primary.push({ key: 'pause', label: t('stepPause'), icon: <PauseIcon />, onClick: () => onPause(id) });
  if (onResume) primary.push({ key: 'resume', label: t('stepResume'), icon: <PlayArrowIcon />, onClick: () => onResume(id) });
  if (s === 'failed' || s === 'paused' || s === 'pending') {
    if (onSkip) primary.push({ key: 'skip', label: t('stepSkip'), icon: <SkipNextIcon />, onClick: () => onSkip(id) });
  }
  if (s === 'running' || s === 'pending') {
    if (onCancel) primary.push({ key: 'cancel', label: t('stepCancel'), icon: <CloseIcon />, onClick: () => onCancel(id), color: 'error' });
  }

  if (s !== 'completed' && s !== 'skipped') {
    if (onEditInPlan) secondary.push({ key: 'edit', label: t('stepEditInPlan'), icon: <EditOutlinedIcon />, onClick: onEditInPlan });
    if (onDiscussInPlan) secondary.push({ key: 'discuss', label: t('stepDiscussInPlan'), icon: <ChatBubbleOutlineIcon />, onClick: () => onDiscussInPlan(step) });
  }

  if (!primary.length && !secondary.length) return null;

  const renderBtn = (b) => (
    <Tooltip key={b.key} title={b.label}>
      <span>
        <IconButton
          size="small"
          color={b.color || 'default'}
          disabled={busy}
          aria-label={b.label}
          onClick={b.onClick}
          data-testid={`step-action-${b.key}`}
          sx={{ p: 0.25 }}
        >
          {React.cloneElement(b.icon, { sx: { fontSize: 16 } })}
        </IconButton>
      </span>
    </Tooltip>
  );

  return (
    <Stack
      direction="row"
      spacing={0.25}
      alignItems="center"
      data-testid="step-action-bar"
      sx={{ mt: 1 }}
    >
      {primary.map(renderBtn)}
      {secondary.map(renderBtn)}
    </Stack>
  );
}

StepActionBar.propTypes = {
  step: PropTypes.object,
  busy: PropTypes.bool,
  onRetry: PropTypes.func,
  onSkip: PropTypes.func,
  onPause: PropTypes.func,
  onResume: PropTypes.func,
  onCancel: PropTypes.func,
  onEditInPlan: PropTypes.func,
  onDiscussInPlan: PropTypes.func,
};
