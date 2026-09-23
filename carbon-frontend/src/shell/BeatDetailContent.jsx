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
import { actionLabelForApi } from './consentInputSpec';
import { presentToolLabel } from './presentationPlane';
import { beatSituation } from './beatReport';

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

function stepApiName(step) {
  const args = step?.tool_args;
  if (!args || typeof args !== 'object') return '';
  return String(args.api_name || '').trim();
}

function humanAction(step) {
  const api = stepApiName(step);
  if (api) return actionLabelForApi(api);
  return (
    presentToolLabel(step?.tool_name, { audience: 'operator' })
    || toolLabel(step?.tool_name)
    || stripEngineJargon(step?.intent || `Step ${step?.step_id}`)
  );
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
  hideConsentHint = false,
}) {
  const { t } = useTranslation('ai');
  if (!step) return null;

  const meta = stepStatusMeta(step.status);
  const intent = humanAction(step) || stripEngineJargon(event?.title || `Step ${step.step_id}`);
  const needsYou = step.status === 'awaiting_approval';
  const situation = beatSituation(step);
  const failed = situation.failed;
  const skipped = step.status === 'skipped';
  const started = formatWhen(step.started_at || step.created_at);
  const finished = formatWhen(step.finished_at || step.completed_at || step.updated_at);
  const latency = formatDuration(
    typeof step.latency_ms === 'number' ? step.latency_ms : event?.latencyMs,
  );

  const api = stepApiName(step);
  const toolPresented = toolLabel(step.tool_name, { apiName: api });
  // call_host_api title already carries the business action — never show the
  // thin "System check" (or a duplicate Submit leave…) tool row beside it.
  const showToolRow = Boolean(toolPresented)
    && step.tool_name !== 'call_host_api'
    && toolPresented !== intent;
  const rows = [
    { label: t('beatStatus'), value: meta.label },
    showToolRow ? { label: t('beatTool'), value: toolPresented } : null,
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

      {needsYou && !hideConsentHint && (
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
            Approve or decline in this panel.
          </Typography>
        </Box>
      )}

      {situation.healed && (
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem' }} data-testid="beat-healed">
          {t('beatHealRead')}
          {situation.heal ? ` ${situation.heal}` : ''}
        </Typography>
      )}

      {situation.writeStopped && (
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem' }} data-testid="beat-write-held">
          {t('beatHealWrite')}
        </Typography>
      )}

      {failed && (
        <Box
          data-testid="beat-failure-report"
          sx={{
            p: 1.25,
            borderRadius: 1,
            border: 1,
            borderColor: 'error.main',
            bgcolor: 'error.soft',
          }}
        >
          <Typography variant="body2" color="error.main" sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>
            {t('beatFailWhat')}
          </Typography>
          <Typography variant="body2" sx={{ fontSize: '0.8125rem', mb: 0.75 }}>
            {stripEngineJargon(situation.error || t('beatFailed')).slice(0, 280)}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.75rem' }}>
            {t('beatFailMeans')}: {t('beatFailMeansBody')}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.75rem' }}>
            {t('beatFailDid')}: {situation.mutation || situation.retries === 0 ? t('beatFailDidWrite') : t('beatFailDidRead')}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.75rem' }}>
            {t('beatFailYou')}: {t('beatFailYouBody')}
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
  hideConsentHint: PropTypes.bool,
};
