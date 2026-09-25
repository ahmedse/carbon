/**
 * Consent review — "What will change" summary + Approve when the staged write
 * is complete; one short question when a slot is still missing.
 *
 * Fields and governed options come from the step's ``consent_slots``, so this
 * component is the same for leave, loans, attendance permissions and hires —
 * no per-API field tables, no client-side synonym or date guessing.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
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
  bodySummaryRows,
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

function ChangePreviewPanel({
  stepId,
  actionLabel,
  consequence,
  rows,
  partial = false,
}) {
  return (
    <Box
      data-testid={`timeline-consent-summary-${stepId}`}
      data-consent-preview={partial ? 'partial' : 'ready'}
      sx={{
        mb: 1,
        p: 1.25,
        borderRadius: 1,
        border: 1,
        borderColor: partial ? 'divider' : 'warning.main',
        bgcolor: partial ? 'background.default' : 'warning.soft',
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          fontSize: '0.625rem',
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          display: 'block',
          mb: 0.5,
        }}
      >
        {partial ? 'So far' : 'What will change'}
      </Typography>
      {actionLabel ? (
        <Typography
          variant="body2"
          data-testid={`timeline-consent-action-${stepId}`}
          sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: rows.length ? 0.75 : 0 }}
        >
          {actionLabel}
        </Typography>
      ) : null}
      {rows.length ? (
        <Stack spacing={0.4} sx={{ mb: consequence && !partial ? 0.75 : 0 }}>
          {rows.map((row) => (
            <Stack
              key={row.label}
              direction="row"
              spacing={1}
              alignItems="baseline"
              data-testid={`timeline-consent-row-${stepId}-${row.label}`}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  width: 88,
                  flexShrink: 0,
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                }}
              >
                {row.label}
              </Typography>
              <Typography variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                {row.value}
              </Typography>
            </Stack>
          ))}
        </Stack>
      ) : null}
      {!partial && consequence ? (
        <Typography
          variant="caption"
          color="text.secondary"
          data-testid={`timeline-consent-consequence-${stepId}`}
          sx={{ display: 'block', fontSize: '0.6875rem', lineHeight: 1.4 }}
        >
          {consequence}
        </Typography>
      ) : null}
      {!partial ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 0.5, fontSize: '0.625rem' }}
        >
          Nothing is submitted until you Approve.
        </Typography>
      ) : null}
    </Box>
  );
}

ChangePreviewPanel.propTypes = {
  stepId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  actionLabel: PropTypes.string,
  consequence: PropTypes.string,
  rows: PropTypes.arrayOf(
    PropTypes.shape({ label: PropTypes.string, value: PropTypes.string }),
  ),
  partial: PropTypes.bool,
};

function serverConsentValues(step) {
  return { ...(consentInputSpec(step)?.values || {}) };
}

function mergeConsentValues(prev, server) {
  // Keep operator answers across plan polls. Polling rebuilds tool_args /
  // consent_slots as new object identities every few seconds; wiping local
  // state on those identity changes sent the chip picker back to "select again".
  const next = { ...server };
  Object.entries(prev || {}).forEach(([key, value]) => {
    if (value != null && String(value).trim() !== '') {
      next[key] = value;
    }
  });
  return next;
}

export default function TimelineConsentForm({
  step,
  confirming,
  onConfirm,
  onDecline,
}) {
  const spec = useMemo(() => consentInputSpec(step), [step]);
  const [values, setValues] = useState(() => serverConsentValues(step));
  const seedKeyRef = useRef(null);

  useEffect(() => {
    const seedKey = `${step?.step_id ?? ''}:${step?.status ?? ''}`;
    const server = serverConsentValues(step);
    if (seedKeyRef.current !== seedKey) {
      seedKeyRef.current = seedKey;
      setValues(server);
      return;
    }
    setValues((prev) => mergeConsentValues(prev, server));
  }, [step?.step_id, step?.status, step?.tool_args, step?.consent_slots]);

  if (!step || step.status !== 'awaiting_approval') return null;
  const evidence = Array.isArray(step.evidence) ? step.evidence : [];
  if (evidence.length && evidence.some((row) => !row.ok)) return null;
  const choice = step.choice;
  if (choice?.options?.length && choice.key) {
    return (
      <Stack
        spacing={0.75}
        data-testid={`timeline-choice-${step.step_id}`}
        onClick={(e) => e.stopPropagation()}
      >
        <Typography variant="caption" sx={{ fontSize: '0.6875rem', fontWeight: 600 }}>
          {`Which ${choice.key}?`}
        </Typography>
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
          {choice.options.map((opt) => (
            <Button
              key={String(opt.value)}
              size="small"
              variant="outlined"
              disabled={Boolean(confirming)}
              data-testid={`timeline-choice-${step.step_id}-${opt.value}`}
              onClick={() => onConfirm?.(step.step_id, { body: { [choice.key]: opt.value } })}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0 }}
            >
              {opt.label || String(opt.value)}
            </Button>
          ))}
        </Stack>
      </Stack>
    );
  }
  // Spec can be null only for non-write awaits; still allow Approve/Decline.
  const fields = spec?.fields || [];
  const busy = Boolean(confirming);
  const ready = !spec || consentFormValid(fields, values);
  const missing = fields.length ? firstMissingField(fields, values) : null;
  const rows = bodySummaryRows(fields, values);
  const summary = bodySummary(fields, values);
  const actionLabel = spec?.actionLabel || '';
  const consequence = spec?.consequence || '';

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
      {step.narration ? (
        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontSize: '0.6875rem' }} data-testid={`timeline-narration-${step.step_id}`}>
          {step.narration}
        </Typography>
      ) : null}
      {evidence.length ? (
        <Stack spacing={0.25} sx={{ mb: 0.75 }} data-testid={`timeline-evidence-${step.step_id}`}>
          {evidence.map((row) => (
            <Typography
              key={row.step_id}
              variant="caption"
              sx={{ fontSize: '0.625rem' }}
            >
              {`Step ${row.step_id}: ${row.ok ? 'completed' : row.status}`}
            </Typography>
          ))}
        </Stack>
      ) : null}

      {ready && (actionLabel || rows.length || consequence) ? (
        <ChangePreviewPanel
          stepId={step.step_id}
          actionLabel={actionLabel}
          consequence={consequence}
          rows={rows}
        />
      ) : null}

      {!ready && missing ? (
        <Stack
          spacing={0.75}
          sx={{ mb: 1 }}
          data-testid={`timeline-consent-ask-${step.step_id}`}
        >
          {(rows.length || actionLabel) ? (
            <ChangePreviewPanel
              stepId={step.step_id}
              actionLabel={actionLabel}
              consequence={consequence}
              rows={rows}
              partial
            />
          ) : null}
          <MissingSlotPrompt
            field={missing}
            onPick={(patch) => setValues((prev) => ({ ...prev, ...patch }))}
          />
          {!rows.length && summary ? (
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
