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

/** Short Operator-facing plan label from brief (first sentence / line). */
export function planDisplayLabel(plan, fallback = 'Untitled plan') {
  const b = String(plan?.brief || '').trim();
  if (!b) return fallback;
  const first = b.split(/\n/)[0].split(/(?<=[.!?])\s+/)[0].trim();
  if (!first) return fallback;
  return first.length > 56 ? `${first.slice(0, 55)}…` : first;
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
  const fullBrief = String(plan?.brief || '').trim() || t('untitledPlan');

  return (
    <Toolbar
      disableGutters
      variant="dense"
      data-testid="agent-plan-toolbar"
      sx={{
        width: '100%',
        minHeight: 40,
        gap: 1,
        px: 0,
        flexWrap: 'wrap',
        alignItems: 'flex-start',
        py: 0.5,
      }}
    >
      <Typography
        data-testid="agent-plan-label"
        title={fullBrief}
        sx={{
          flex: '1 1 140px',
          minWidth: 0,
          fontSize: '0.8125rem',
          fontWeight: 600,
          lineHeight: 1.35,
          maxHeight: '4.05em',
          overflowY: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          alignSelf: 'center',
        }}
      >
        {fullBrief}
      </Typography>

      <Stack direction="row" spacing={0.75} alignItems="flex-start" flexWrap="wrap" useFlexGap sx={{ pt: 0.125 }}>
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
