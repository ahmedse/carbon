// src/shell/AgentPlanToolbar.jsx
// ADR-0043 V6 — Plan toolbar under cockpit tabs (actions only).
// Keep it simple: Approve / Cancel / Discuss. Plan changes go through
// Discuss in Chat — no Fork / Replan chrome on this surface for now.
import React from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import { useTranslation } from 'react-i18next';
import { humanTaskTitle } from './taskWorkspace';

/** Short employee-facing plan label from brief (first sentence / line). */
export function planDisplayLabel(plan, fallback = 'Untitled plan') {
  return humanTaskTitle(plan, fallback, 0);
}

/**
 * @param {object} props
 * @param {object} props.plan
 * @param {'review'|'inspect'} [props.mode]
 * @param {boolean} [props.busy]
 * @param {function} props.onApprove
 * @param {function} props.onDecline
 * @param {function} [props.onDiscuss]
 */
export default function AgentPlanToolbar({
  plan,
  mode = 'review',
  busy = false,
  onApprove,
  onDecline,
  onDiscuss,
}) {
  const { t } = useTranslation('ai');
  const cancelled = plan?.status === 'cancelled';
  const inspect = mode === 'inspect';
  const fullBrief = humanTaskTitle(plan, t('untitledPlan'), 0);

  return (
    <Toolbar
      disableGutters
      variant="dense"
      data-testid="agent-plan-toolbar"
      sx={{
        width: '100%',
        minHeight: 32,
        gap: 1,
        px: 0,
        flexWrap: 'wrap',
        alignItems: 'center',
        py: 0.25,
      }}
    >
      <Typography
        data-testid="agent-plan-label"
        title={String(plan?.brief || '').trim() || fullBrief}
        sx={{
          position: 'absolute',
          width: 1,
          height: 1,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
        }}
      >
        {fullBrief}
      </Typography>

      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
        {cancelled ? (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {t('planCancelledNothingRan')}
          </Typography>
        ) : inspect ? (
          <Stack direction="row" spacing={0.75} alignItems="center" data-testid="agent-review-inspect">
            {onDiscuss && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<ChatBubbleOutlineIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onDiscuss}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                {t('discussInChat')}
              </Button>
            )}
          </Stack>
        ) : (
          <Stack direction="row" spacing={0.75} alignItems="center" data-testid="agent-review-consent">
            <Button
              size="small"
              variant="contained"
              disabled={busy}
              onClick={onApprove}
              aria-label={t('approvePlan')}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {busy ? t('approvingPlan') : t('approvePlan')}
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              disabled={busy}
              onClick={onDecline}
              aria-label={t('cancelPlan')}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {t('cancelPlan')}
            </Button>
            {onDiscuss && (
              <Button
                size="small"
                variant="text"
                startIcon={<ChatBubbleOutlineIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onDiscuss}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                {t('discussInChat')}
              </Button>
            )}
          </Stack>
        )}
      </Stack>
    </Toolbar>
  );
}

AgentPlanToolbar.propTypes = {
  plan: PropTypes.object.isRequired,
  mode: PropTypes.oneOf(['review', 'inspect']),
  busy: PropTypes.bool,
  onApprove: PropTypes.func.isRequired,
  onDecline: PropTypes.func.isRequired,
  onDiscuss: PropTypes.func,
};
