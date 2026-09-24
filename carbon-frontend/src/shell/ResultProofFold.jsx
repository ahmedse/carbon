// ResultProofFold — L1 proof on Result (who consented, when). No L2 cost/routing.
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  Collapse,
  Stack,
  Typography,
} from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';

function formatWhen(value) {
  if (!value) return '';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format('MMM D, YYYY · HH:mm') : String(value);
}

/**
 * @param {object} props
 * @param {object} props.ledger
 */
export default function ResultProofFold({ ledger }) {
  const { t } = useTranslation('ai');
  const [open, setOpen] = useState(false);
  if (!ledger) return null;

  const actor = ledger.actor || {};
  const confirmations = Array.isArray(ledger.confirmations) ? ledger.confirmations : [];
  const steps = Array.isArray(ledger.steps) ? ledger.steps : [];
  const consented = steps.filter((s) => s.confirmed || s.consent_granted);
  const finishedAt = ledger.provenance?.completed_at || ledger.completed_at || '';
  const count = Math.max(confirmations.length, consented.length);
  const actorName = actor.display_name || actor.user_id || t('resultUnknownActor');

  return (
    <Box data-testid="result-proof-fold">
      <Typography
        component="button"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          width: '100%',
          textAlign: 'start',
          border: 0,
          bgcolor: 'transparent',
          p: 0,
          cursor: 'pointer',
          typography: 'body2',
          fontWeight: 600,
          color: 'text.secondary',
        }}
      >
        {t('resultApprovalsTiming')}
        {count > 0 ? (
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
            · {count}
          </Typography>
        ) : null}
        {open
          ? <ExpandLessIcon sx={{ fontSize: 16, ml: 'auto' }} />
          : <ExpandMoreIcon sx={{ fontSize: 16, ml: 'auto' }} />}
      </Typography>
      <Collapse in={open}>
        <Stack spacing={1} sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {t('resultRequestedBy')} · {actorName}
            {finishedAt ? ` · ${formatWhen(finishedAt)}` : ''}
          </Typography>
          {confirmations.length > 0 ? (
            <Stack direction="row" spacing={0.5} useFlexGap flexWrap="wrap">
              {confirmations.map((c) => (
                <Chip
                  key={`${c.step_id}-${c.status}`}
                  size="small"
                  variant="outlined"
                  label={t('resultConfirmationChip', {
                    step: c.step_id,
                    status: c.status,
                  })}
                  sx={{ height: 20 }}
                />
              ))}
            </Stack>
          ) : consented.length > 0 ? (
            <Stack spacing={0.5}>
              {consented.map((step) => (
                <Typography key={step.step_id} variant="caption" color="text.secondary">
                  {step.intent || t('resultStepFallback', { id: step.step_id })}
                  {' · '}
                  {t('resultConsented')}
                </Typography>
              ))}
            </Stack>
          ) : (
            <Typography variant="caption" color="text.secondary">
              {t('resultNoConfirmations')}
            </Typography>
          )}
        </Stack>
      </Collapse>
    </Box>
  );
}

ResultProofFold.propTypes = {
  ledger: PropTypes.object,
};
