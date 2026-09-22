/**
 * Consent review — summary + Approve when the staged write is complete, one
 * short question when it is not.
 *
 * Fields and governed options come from the step's ``consent_slots``, so this
 * component is the same for leave, loans, attendance permissions and hires —
 * no per-API field tables, no client-side synonym or date guessing.
 */
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  bodySummary,
  consentFormValid,
  consentInputSpec,
  firstMissingField,
} from './consentInputSpec';

function isoDay(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function MissingSlotPrompt({ field, onPick }) {
  if (field.type === 'governed' && field.options.length) {
    return (
      <>
        <Typography variant="caption" sx={{ fontSize: '0.6875rem', fontWeight: 600 }}>
          {`Which ${field.label.toLowerCase()}?`}
        </Typography>
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
          {field.options.map((opt) => (
            <Button
              key={opt.value}
              size="small"
              variant="outlined"
              data-testid={`consent-ask-${field.key}-${opt.value}`}
              onClick={() => onPick({ [field.key]: opt.value })}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0 }}
            >
              {opt.label}
            </Button>
          ))}
        </Stack>
      </>
    );
  }

  if (field.type === 'date') {
    return (
      <>
        <Typography variant="caption" sx={{ fontSize: '0.6875rem', fontWeight: 600 }}>
          {`Which ${field.label.toLowerCase()}?`}
        </Typography>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Button
            size="small"
            variant="outlined"
            data-testid="consent-ask-date-tomorrow"
            onClick={() => onPick({ [field.key]: isoDay(1) })}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            Tomorrow
          </Button>
          <Button
            size="small"
            variant="outlined"
            data-testid="consent-ask-date-today"
            onClick={() => onPick({ [field.key]: isoDay(0) })}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            Today
          </Button>
          <TextField
            size="small"
            type="date"
            inputProps={{ 'data-testid': 'consent-ask-date-picker' }}
            onChange={(e) => {
              if (e.target.value) onPick({ [field.key]: e.target.value });
            }}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem', py: 0.5 }, maxWidth: 140 }}
          />
        </Stack>
      </>
    );
  }

  if (field.type === 'days') {
    return (
      <>
        <Typography variant="caption" sx={{ fontSize: '0.6875rem', fontWeight: 600 }}>
          How many days?
        </Typography>
        <Stack direction="row" spacing={0.5}>
          {[1, 2, 3].map((n) => (
            <Button
              key={n}
              size="small"
              variant="outlined"
              data-testid={`consent-ask-days-${n}`}
              onClick={() => onPick({ [field.key]: n })}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 36 }}
            >
              {n}
            </Button>
          ))}
        </Stack>
      </>
    );
  }

  return (
    <>
      <Typography variant="caption" sx={{ fontSize: '0.6875rem', fontWeight: 600 }}>
        {`${field.label}?`}
      </Typography>
      <TextField
        size="small"
        fullWidth
        type={field.type === 'number' ? 'number' : 'text'}
        label={field.label}
        onChange={(e) => onPick({ [field.key]: e.target.value })}
        inputProps={{ 'data-testid': `consent-field-${field.key}` }}
        sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
      />
    </>
  );
}

MissingSlotPrompt.propTypes = {
  field: PropTypes.object.isRequired,
  onPick: PropTypes.func.isRequired,
};

export default function TimelineConsentForm({
  step,
  confirming,
  onConfirm,
  onDecline,
}) {
  const spec = useMemo(() => consentInputSpec(step), [step]);
  const [values, setValues] = useState(() => ({ ...(spec?.values || {}) }));

  useEffect(() => {
    setValues({ ...(consentInputSpec(step)?.values || {}) });
  }, [step?.step_id, step?.status, step?.tool_args, step?.consent_slots]);

  if (!step || step.status !== 'awaiting_approval') return null;

  const fields = spec?.fields || [];
  const busy = Boolean(confirming);
  const ready = consentFormValid(fields, values);
  const missing = firstMissingField(fields, values);
  const summary = bodySummary(fields, values);

  const handleApprove = (e) => {
    e?.stopPropagation?.();
    if (!ready || !onConfirm) return;
    onConfirm(step.step_id, fields.length ? { body: values } : undefined);
  };

  const handleDecline = (e) => {
    e?.stopPropagation?.();
    onDecline?.(step.step_id);
  };

  return (
    <Box
      data-testid={`timeline-consent-${step.step_id}`}
      data-consent-mode={ready ? 'summary' : 'ask'}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
      sx={{ mt: 0.5 }}
    >
      {ready && summary ? (
        <Box
          data-testid={`timeline-consent-summary-${step.step_id}`}
          sx={{
            mb: 1,
            p: 1,
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
          }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontSize: '0.625rem', display: 'block', mb: 0.35 }}
          >
            From your request
          </Typography>
          <Typography variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>
            {summary}
          </Typography>
        </Box>
      ) : null}

      {!ready && missing ? (
        <Stack
          spacing={0.75}
          sx={{ mb: 1 }}
          data-testid={`timeline-consent-ask-${step.step_id}`}
        >
          <MissingSlotPrompt
            field={missing}
            onPick={(patch) => setValues((prev) => ({ ...prev, ...patch }))}
          />
          {summary ? (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
              So far: {summary}
            </Typography>
          ) : null}
        </Stack>
      ) : null}

      <Stack direction="row" spacing={1} alignItems="center">
        <Button
          size="small"
          variant="contained"
          color="warning"
          disabled={busy || !ready}
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
      {!ready ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 0.75, fontSize: '0.625rem' }}
        >
          Answer the question above to continue — no form to fill.
        </Typography>
      ) : null}
    </Box>
  );
}

TimelineConsentForm.propTypes = {
  step: PropTypes.object,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
};
