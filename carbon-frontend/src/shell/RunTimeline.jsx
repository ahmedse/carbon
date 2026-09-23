/**
 * Operator Run timeline — visual rail + beats (ADR-0043 V5).
 * Consent Approve/Decline + field form live in the step detail drawer
 * (not expanded inline on the beat).
 */
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import { FONT } from '../theme/themeTokens';
import { chronicleTone } from '../utils/runChronicle';
import { useTranslation } from 'react-i18next';
import { toolLabel } from './aiTaskStatus';
import { stripEngineJargon } from './humanizeOperatorCopy';
import { presentToolLabel } from './presentationPlane';
import { beatSituation } from './beatReport';

function formatDuration(ms) {
  if (ms == null || !Number.isFinite(ms)) return null;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function nodeColors(kind) {
  switch (kind) {
    case 'done':
      return { fill: 'success.main', ring: 'success.light' };
    case 'failed':
      return { fill: 'error.main', ring: 'error.light' };
    case 'consent':
    case 'paused':
      return { fill: 'warning.main', ring: 'warning.light' };
    case 'running':
      return { fill: 'primary.main', ring: 'primary.light' };
    default:
      return { fill: 'action.disabled', ring: 'divider' };
  }
}

function humanTitle(event, step) {
  const args = step?.tool_args;
  const api = args && typeof args === 'object' ? args.api_name : '';
  if (api) {
    return (
      presentToolLabel('call_host_api', { audience: 'operator', apiName: api })
      || toolLabel(api)
      || String(api).replace(/_/g, ' ')
    );
  }
  return stripEngineJargon(event?.title || step?.intent || `Step ${event?.stepId}`);
}

function TimelineBeat({
  event,
  step,
  isLast,
  selected,
  onSelect,
}) {
  const { t } = useTranslation('ai');
  const tone = chronicleTone(event.kind);
  const chipColor = tone === 'default' ? undefined : tone;
  const focused = event.kind === 'consent' || event.kind === 'running' || event.kind === 'paused';
  const colors = nodeColors(event.kind);
  const title = humanTitle(event, step);
  const situation = beatSituation(step);
  const toolPresented = step?.tool_name && step.tool_name !== 'call_host_api'
    ? (presentToolLabel(step.tool_name, { audience: 'operator' }) || toolLabel(step.tool_name))
    : '';
  const showTool = Boolean(toolPresented) && toolPresented !== title;
  const tipBits = [
    t('beatTooltipOpen'),
    event.clockFull || event.clock || null,
    event.statusLabel,
    event.detail,
    event.latencyMs != null ? formatDuration(event.latencyMs) : null,
  ].filter(Boolean);

  const select = (e) => {
    e?.stopPropagation?.();
    onSelect?.(event.stepId);
  };

  return (
    <Stack
      direction="row"
      spacing={1.25}
      alignItems="stretch"
      data-testid={`run-chronicle-row-${event.stepId}`}
      data-focused={focused ? 'true' : undefined}
      data-selected={selected ? 'true' : undefined}
      sx={{ minHeight: 52 }}
    >
      <Box
        sx={{
          width: 40,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          position: 'relative',
        }}
      >
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            fontSize: '0.5625rem',
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.2,
            mb: 0.35,
            letterSpacing: '0.02em',
          }}
        >
          {event.beatLabel}
        </Typography>
        <Tooltip
          title={(
            <Box sx={{ p: 0.25 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                {title}
              </Typography>
              {tipBits.map((line) => (
                <Typography key={line} variant="caption" sx={{ display: 'block', opacity: 0.9 }}>
                  {line}
                </Typography>
              ))}
            </Box>
          )}
          arrow
          enterDelay={200}
        >
          <Box
            role="button"
            tabIndex={0}
            aria-label={`${event.beatLabel}: ${title}. Click for details.`}
            data-testid={`run-timeline-node-${event.stepId}`}
            onClick={(e) => select(e)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                select(e);
              }
            }}
            sx={{
              width: focused || selected ? 14 : 10,
              height: focused || selected ? 14 : 10,
              borderRadius: '50%',
              bgcolor: colors.fill,
              border: 2,
              borderColor: selected ? 'primary.main' : (focused ? colors.ring : 'background.paper'),
              boxSizing: 'border-box',
              zIndex: 1,
              flexShrink: 0,
              cursor: 'pointer',
              ...(focused && event.kind === 'running' ? {
                animation: 'pulse-run-node 1.4s ease-in-out infinite',
                '@keyframes pulse-run-node': {
                  '0%, 100%': { transform: 'scale(1)', opacity: 1 },
                  '50%': { transform: 'scale(1.15)', opacity: 0.85 },
                },
              } : {}),
            }}
          />
        </Tooltip>
        {!isLast && (
          <Box
            aria-hidden
            sx={{
              flex: 1,
              width: 2,
              minHeight: 28,
              mt: 0.35,
              bgcolor: event.settled || focused ? 'primary.light' : 'divider',
              borderRadius: 1,
              opacity: event.settled || focused ? 0.7 : 1,
            }}
          />
        )}
      </Box>

      <Box
        onClick={(e) => select(e)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            select(e);
          }
        }}
        role="button"
        tabIndex={0}
        sx={{
          flex: 1,
          minWidth: 0,
          mb: isLast ? 0 : 0.75,
          px: 1,
          py: 0.75,
          borderRadius: 1,
          border: 1,
          borderColor: selected ? 'primary.main' : (focused ? 'warning.main' : 'divider'),
          bgcolor: focused ? 'warning.soft' : (selected ? 'action.hover' : 'background.paper'),
          cursor: 'pointer',
          textAlign: 'left',
          '&:hover': { borderColor: 'primary.light' },
        }}
      >
        <Stack direction="row" spacing={0.75} alignItems="flex-start">
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontSize: '0.75rem', fontWeight: focused || selected ? 600 : 500 }}>
              {title}
            </Typography>
            {event.detail && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: '0.625rem', display: 'block', mt: 0.25 }}
              >
                {event.detail}
              </Typography>
            )}
            {situation.healed && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', display: 'block', mt: 0.25 }}>
                {t('beatHealRead')}
              </Typography>
            )}
            {showTool && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.5625rem', display: 'block', mt: 0.25 }}>
                {t('beatToolClosed', { tool: toolPresented })}
              </Typography>
            )}
            {event.clock && (
              <Typography
                variant="caption"
                color="text.disabled"
                sx={{ fontSize: '0.5625rem', display: 'block', mt: 0.25, fontVariantNumeric: 'tabular-nums' }}
              >
                {event.clock}
                {event.latencyMs != null ? ` · ${formatDuration(event.latencyMs)}` : ''}
              </Typography>
            )}
          </Box>
          <Tooltip title={event.statusLabel}>
            <Chip
              size="small"
              label={event.statusLabel}
              color={chipColor}
              sx={{ height: 18, fontSize: '0.5625rem', ...FONT.chip }}
            />
          </Tooltip>
          <Tooltip title={t('beatOpenDetails')}>
            <IconButton
              size="small"
              aria-label={t('beatOpenDetails')}
              data-testid={`run-timeline-open-${event.stepId}`}
              onClick={(e) => select(e)}
              sx={{ p: 0.25, color: 'text.secondary' }}
            >
              <OpenInFullIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>
    </Stack>
  );
}

TimelineBeat.propTypes = {
  event: PropTypes.object.isRequired,
  step: PropTypes.object,
  isLast: PropTypes.bool,
  index: PropTypes.number,
  selected: PropTypes.bool,
  onSelect: PropTypes.func,
};

/**
 * @param {{ events: Array, stepsById?: object, title?: string, selectedStepId?: *, onSelectStep?: function }} props
 */
export default function RunTimeline({
  events,
  stepsById = null,
  title,
  selectedStepId = null,
  onSelectStep,
}) {
  if (!Array.isArray(events) || events.length === 0) return null;

  return (
    <Box
      data-testid="agent-run-chronicle"
      data-timeline="visual"
      sx={{
        bgcolor: 'transparent',
        overflow: 'hidden',
        px: 0.5,
        pt: 0.5,
        pb: 0.25,
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          display: 'block',
          mb: 0.75,
          fontSize: '0.625rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {title}
      </Typography>
      <Stack spacing={0}>
        {events.map((evt, i) => {
          const step = stepsById?.[evt.stepId] || null;
          return (
            <TimelineBeat
              key={evt.id}
              event={evt}
              step={step}
              index={i}
              isLast={i === events.length - 1}
              selected={selectedStepId != null && selectedStepId === evt.stepId}
              onSelect={onSelectStep}
            />
          );
        })}
      </Stack>
    </Box>
  );
}

RunTimeline.propTypes = {
  events: PropTypes.arrayOf(PropTypes.object).isRequired,
  stepsById: PropTypes.object,
  title: PropTypes.string,
  selectedStepId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onSelectStep: PropTypes.func,
};
