/**
 * Shared beat / step detail body — used by docked Run pane (and dialog wrapper).
 * Operator surface: no Approve/Decline (timeline owns consent) and no raw JSON dumps.
 */
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { FONT } from '../theme/themeTokens';
import { stepStatusMeta, toolLabel } from './aiTaskStatus';
import { stripEngineJargon } from './humanizeOperatorCopy';

function formatDuration(ms) {
  if (ms == null || !Number.isFinite(ms)) return null;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatWhen(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  try {
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function humanAction(step) {
  const args = step?.tool_args;
  const api = args && typeof args === 'object' ? args.api_name : '';
  if (api) return toolLabel(api) || String(api).replace(/_/g, ' ');
  return stripEngineJargon(step?.intent || `Step ${step?.step_id}`);
}

/**
 * @param {object} props
 * @param {object} props.step
 * @param {object|null} [props.event]
 * @param {boolean} [props.busy]
 */
export default function BeatDetailContent({
  step,
  event = null,
  busy = false, // kept for call-site compatibility
}) {
  const { t } = useTranslation('ai');
  if (!step) return null;

  const meta = stepStatusMeta(step.status);
  const intent = humanAction(step) || stripEngineJargon(event?.title || `Step ${step.step_id}`);
  const needsYou = step.status === 'awaiting_approval';
  const failed = step.status === 'failed';
  const skipped = step.status === 'skipped';
  const started = formatWhen(step.started_at || step.created_at);
  const finished = formatWhen(step.finished_at || step.completed_at || step.updated_at);
  const latency = formatDuration(
    typeof step.latency_ms === 'number' ? step.latency_ms : event?.latencyMs,
  );

  const rows = [
    { label: t('beatStatus'), value: meta.label },
    toolLabel(step.tool_name) ? { label: t('beatTool'), value: toolLabel(step.tool_name) } : null,
    started ? { label: t('beatStarted'), value: started } : null,
    finished ? { label: t('beatFinished'), value: finished } : null,
    latency ? { label: t('beatDuration'), value: latency } : null,
    step.consent_granted ? { label: t('beatConsent'), value: t('beatConsentYes') } : null,
  ].filter(Boolean);

  return (
    <Stack spacing={1.25} data-testid="beat-detail-body" data-busy={busy ? 'true' : undefined}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Typography variant="body1" sx={{ fontSize: '0.875rem', fontWeight: 600, flex: 1, lineHeight: 1.35 }}>
          {intent}
        </Typography>
        <Chip
          size="small"
          label={meta.label}
          color={meta.color === 'default' ? undefined : meta.color}
          sx={{ height: 22, ...FONT.chip }}
        />
      </Stack>

      {needsYou && (
        <Box
          sx={{
            p: 1.25,
            borderRadius: 1,
            border: 1,
            borderColor: 'warning.main',
            bgcolor: 'warning.soft',
          }}
        >
          <Typography variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>
            {t('beatNeedsYou')}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {event?.detail || t('beatNeedsYouHint')}
            {' '}
            Approve or decline on the timeline step.
          </Typography>
        </Box>
      )}

      {failed && (
        <Box
          sx={{
            p: 1.25,
            borderRadius: 1,
            border: 1,
            borderColor: 'error.main',
            bgcolor: 'error.soft',
          }}
        >
          <Typography variant="body2" color="error.main" sx={{ fontSize: '0.8125rem' }}>
            {String(step.error || step.error_message || t('beatFailed')).slice(0, 280)}
          </Typography>
        </Box>
      )}

      {skipped && (
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem' }}>
          {t('beatSkippedBranch')}
        </Typography>
      )}

      <Stack spacing={1}>
        {rows.map((row) => (
          <Stack key={row.label} direction="row" spacing={1.5} alignItems="baseline">
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ width: 72, flexShrink: 0, fontSize: '0.6875rem', fontWeight: 600 }}
            >
              {row.label}
            </Typography>
            <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
              {row.value}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Stack>
  );
}

BeatDetailContent.propTypes = {
  step: PropTypes.object,
  event: PropTypes.object,
  onApprove: PropTypes.func,
  onDecline: PropTypes.func,
  busy: PropTypes.bool,
};
