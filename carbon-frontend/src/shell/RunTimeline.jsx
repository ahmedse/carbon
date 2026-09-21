/**
 * Operator Run timeline — visual rail + beats (ADR-0043 V5).
 * Consent Approve/Decline + optional field form live only on the active node.
 */
import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import { FONT } from '../theme/themeTokens';
import { chronicleTone } from '../utils/runChronicle';
import { useTranslation } from 'react-i18next';
import { consentFormValid, consentInputSpec } from './consentInputSpec';
import { toolLabel } from './aiTaskStatus';
import { stripEngineJargon } from './humanizeOperatorCopy';

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
  if (api) return toolLabel(api) || String(api).replace(/_/g, ' ');
  return stripEngineJargon(event?.title || step?.intent || `Step ${event?.stepId}`);
}

function TimelineConsentForm({ step, confirming, onConfirm, onDecline }) {
  const spec = consentInputSpec(step);
  const [values, setValues] = useState(() => ({ ...(spec?.values || {}) }));

  useEffect(() => {
    const next = consentInputSpec(step);
    setValues({ ...(next?.values || {}) });
  }, [step?.step_id, step?.status, step?.tool_args]);

  if (!step || step.status !== 'awaiting_approval') return null;

  const fields = spec?.fields || [];
  const showForm = Boolean(spec?.requiresForm) || (fields.length > 0 && Object.keys(spec?.values || {}).length === 0);
  const valid = !showForm || consentFormValid(fields, values);
  const busy = Boolean(confirming);

  const setField = (key, raw) => {
    setValues((prev) => ({ ...prev, [key]: raw }));
  };

  const handleApprove = (e) => {
    e?.stopPropagation?.();
    if (!valid || !onConfirm) return;
    if (showForm || (spec && Object.keys(values).length > 0)) {
      const body = {};
      fields.forEach((f) => {
        let v = values[f.key];
        if (f.type === 'number' && v !== '' && v != null) v = Number(v);
        body[f.key] = v;
      });
      onConfirm(step.step_id, { body });
    } else {
      onConfirm(step.step_id);
    }
  };

  const handleDecline = (e) => {
    e?.stopPropagation?.();
    onDecline?.(step.step_id);
  };

  return (
    <Box
      data-testid={`timeline-consent-${step.step_id}`}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
      sx={{ mt: 1 }}
    >
      {showForm && (
        <Stack spacing={0.75} sx={{ mb: 1 }} data-testid={`timeline-consent-form-${step.step_id}`}>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
            Fill required fields, then approve.
          </Typography>
          {fields.map((f) => {
            if (f.type === 'select') {
              return (
                <FormControl key={f.key} size="small" fullWidth required={f.required}>
                  <InputLabel id={`${f.key}-label`} sx={{ fontSize: '0.75rem' }}>{f.label}</InputLabel>
                  <Select
                    labelId={`${f.key}-label`}
                    label={f.label}
                    value={values[f.key] ?? ''}
                    onChange={(e) => setField(f.key, e.target.value)}
                    sx={{ fontSize: '0.75rem' }}
                  >
                    {(f.options || []).map((opt) => (
                      <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: '0.75rem' }}>
                        {opt.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              );
            }
            return (
              <TextField
                key={f.key}
                size="small"
                fullWidth
                required={f.required}
                type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                label={f.label}
                value={values[f.key] ?? ''}
                onChange={(e) => setField(f.key, e.target.value)}
                InputLabelProps={f.type === 'date' ? { shrink: true } : undefined}
                inputProps={{ 'data-testid': `consent-field-${f.key}` }}
                sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
              />
            );
          })}
        </Stack>
      )}
      <Stack direction="row" spacing={1} alignItems="center">
        <Button
          size="small"
          variant="contained"
          color="warning"
          disabled={busy || !valid}
          onClick={handleApprove}
          data-testid={`timeline-approve-${step.step_id}`}
          sx={{ fontSize: '0.75rem', textTransform: 'none', fontWeight: 600 }}
        >
          {busy ? 'Approving…' : 'Approve'}
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="inherit"
          disabled={busy}
          onClick={handleDecline}
          data-testid={`timeline-decline-${step.step_id}`}
          sx={{ fontSize: '0.75rem', textTransform: 'none' }}
        >
          Decline
        </Button>
      </Stack>
    </Box>
  );
}

TimelineConsentForm.propTypes = {
  step: PropTypes.object,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
};

function TimelineBeat({
  event,
  step,
  isLast,
  selected,
  onSelect,
  activeConsent,
  confirming,
  onConfirm,
  onDecline,
}) {
  const { t } = useTranslation('ai');
  const tone = chronicleTone(event.kind);
  const chipColor = tone === 'default' ? undefined : tone;
  const focused = event.kind === 'consent' || event.kind === 'running' || event.kind === 'paused';
  const colors = nodeColors(event.kind);
  const title = humanTitle(event, step);
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
            {activeConsent && step && (
              <TimelineConsentForm
                step={step}
                confirming={confirming}
                onConfirm={onConfirm}
                onDecline={onDecline}
              />
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
  activeConsent: PropTypes.bool,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
};

/**
 * @param {{ events: Array, stepsById?: object, title?: string, selectedStepId?: *, onSelectStep?: function, onConfirmStep?: function, onDeclineStep?: function, confirmingId?: * }} props
 */
export default function RunTimeline({
  events,
  stepsById = null,
  title,
  selectedStepId = null,
  onSelectStep,
  onConfirmStep = null,
  onDeclineStep = null,
  confirmingId = null,
}) {
  if (!Array.isArray(events) || events.length === 0) return null;

  return (
    <Box
      data-testid="agent-run-chronicle"
      data-timeline="visual"
      sx={{
        bgcolor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
        px: 1,
        pt: 0.75,
        pb: 0.5,
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
          const isConsent = evt.kind === 'consent' || step?.status === 'awaiting_approval';
          return (
            <TimelineBeat
              key={evt.id}
              event={evt}
              step={step}
              index={i}
              isLast={i === events.length - 1}
              selected={selectedStepId != null && selectedStepId === evt.stepId}
              onSelect={onSelectStep}
              activeConsent={Boolean(isConsent && onConfirmStep)}
              confirming={confirmingId === evt.stepId}
              onConfirm={onConfirmStep}
              onDecline={onDeclineStep}
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
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};
