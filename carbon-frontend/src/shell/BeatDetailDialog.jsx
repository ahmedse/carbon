/**
 * Beat details — SystemDialog wrapper around BeatDetailContent.
 * Prefer the docked Run pane; keep dialog for any non-dock callers.
 */
import React from 'react';
import PropTypes from 'prop-types';
import { Button, Stack } from '@mui/material';
import { useTranslation } from 'react-i18next';
import SystemDialog from '../components/SystemDialog';
import BeatDetailContent from './BeatDetailContent';

/**
 * @param {object} props
 * @param {boolean} props.open
 * @param {function} props.onClose
 * @param {object|null} props.step
 * @param {object|null} [props.event]
 * @param {function} [props.onApprove]
 * @param {function} [props.onDecline]
 * @param {boolean} [props.busy]
 */
export default function BeatDetailDialog({
  open,
  onClose,
  step,
  event = null,
  onApprove,
  onDecline,
  busy = false,
}) {
  const { t } = useTranslation('ai');
  if (!step) return null;

  const needsYou = step.status === 'awaiting_approval';
  const failed = step.status === 'failed';

  const primaryActions = needsYou ? (
    <Stack direction="row" spacing={1} alignItems="center">
      {onDecline && (
        <Button
          size="small"
          color="inherit"
          variant="outlined"
          disabled={busy}
          onClick={() => onDecline(step.step_id)}
          sx={{ textTransform: 'none', fontSize: '0.8125rem' }}
        >
          {t('declineStep')}
        </Button>
      )}
      {onApprove && (
        <Button
          size="small"
          variant="contained"
          color="warning"
          disabled={busy}
          onClick={() => onApprove(step.step_id)}
          sx={{ textTransform: 'none', fontSize: '0.8125rem', fontWeight: 600 }}
        >
          {busy ? t('approvingPlan') : t('approveStep')}
        </Button>
      )}
    </Stack>
  ) : null;

  return (
    <SystemDialog
      open={open}
      title={t('beatDetailTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('close')}
      showCancel
      width={480}
      height={needsYou || failed ? 440 : 380}
      minWidth={360}
      minHeight={280}
      data-testid="beat-detail-dialog"
      actions={primaryActions}
    >
      <BeatDetailContent
        step={step}
        event={event}
        busy={busy}
        // Actions live in dialog footer when modal
        onApprove={undefined}
        onDecline={undefined}
      />
    </SystemDialog>
  );
}

BeatDetailDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  step: PropTypes.object,
  event: PropTypes.object,
  onApprove: PropTypes.func,
  onDecline: PropTypes.func,
  busy: PropTypes.bool,
};
