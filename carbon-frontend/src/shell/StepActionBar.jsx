// Per-step controls (W-7) + next-move guidance for the Now step drawer.
// State-driven: which buttons show comes from the step status the API returned.
import React from 'react';
import PropTypes from 'prop-types';
import { Button, Stack, Typography } from '@mui/material';
import ReplayIcon from '@mui/icons-material/Replay';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CloseIcon from '@mui/icons-material/Close';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import { useTranslation } from 'react-i18next';

const BTN = { fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, px: 1 };

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

  if (s === 'failed') {
    if (onRetry) primary.push({ key: 'retry', label: t('stepRetry'), icon: <ReplayIcon />, onClick: () => onRetry(id), variant: 'contained' });
    if (onSkip) primary.push({ key: 'skip', label: t('stepSkip'), icon: <SkipNextIcon />, onClick: () => onSkip(id) });
  } else if (s === 'running') {
    if (onPause) primary.push({ key: 'pause', label: t('stepPause'), icon: <PauseIcon />, onClick: () => onPause(id) });
    if (onCancel) primary.push({ key: 'cancel', label: t('stepCancel'), icon: <CloseIcon />, onClick: () => onCancel(id), color: 'error' });
  } else if (s === 'paused') {
    if (onResume) primary.push({ key: 'resume', label: t('stepResume'), icon: <PlayArrowIcon />, onClick: () => onResume(id), variant: 'contained' });
    if (onSkip) primary.push({ key: 'skip', label: t('stepSkip'), icon: <SkipNextIcon />, onClick: () => onSkip(id) });
  } else if (s === 'pending') {
    if (onSkip) primary.push({ key: 'skip', label: t('stepSkip'), icon: <SkipNextIcon />, onClick: () => onSkip(id) });
  }

  if (s !== 'completed' && s !== 'skipped') {
    if (onEditInPlan) secondary.push({ key: 'edit', label: t('stepEditInPlan'), icon: <EditOutlinedIcon />, onClick: onEditInPlan });
    if (onDiscussInPlan) secondary.push({ key: 'discuss', label: t('stepDiscussInPlan'), icon: <ChatBubbleOutlineIcon />, onClick: () => onDiscussInPlan(step) });
  }

  if (!primary.length && !secondary.length) return null;

  const renderBtn = (b) => (
    <Button
      key={b.key}
      size="small"
      variant={b.variant || 'outlined'}
      color={b.color || 'primary'}
      disabled={busy}
      startIcon={React.cloneElement(b.icon, { sx: { fontSize: 14 } })}
      onClick={b.onClick}
      data-testid={`step-action-${b.key}`}
      sx={BTN}
    >
      {b.label}
    </Button>
  );

  return (
    <Stack spacing={0.75} data-testid="step-action-bar" sx={{ mt: 1.25 }}>
      <Typography variant="caption" sx={{ fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'text.secondary' }}>
        {t('stepNextTitle')}
      </Typography>
      {primary.length > 0 && (
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
          {primary.map(renderBtn)}
        </Stack>
      )}
      {secondary.length > 0 && (
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
          {secondary.map((b) => renderBtn({ ...b, variant: 'text' }))}
        </Stack>
      )}
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
