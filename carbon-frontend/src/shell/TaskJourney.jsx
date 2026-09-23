// How we got here — fold under Result, not a fourth tab.
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Collapse, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

function Chapter({ label, body }) {
  return (
    <Box
      sx={{
        flex: 1,
        minWidth: 0,
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        p: 1,
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="caption" sx={{ display: 'block', fontWeight: 700, fontSize: '0.6875rem' }}>
        {label}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem', mt: 0.5, whiteSpace: 'pre-wrap' }}>
        {body}
      </Typography>
    </Box>
  );
}

Chapter.propTypes = {
  label: PropTypes.string.isRequired,
  body: PropTypes.string.isRequired,
};

function chatBody(turns, brief) {
  const lines = [];
  (Array.isArray(turns) ? turns : []).forEach((turn) => {
    const reply = (turn?.reply || '').trim();
    const question = (turn?.question || '').trim();
    if (reply) lines.push(reply);
    if (question) lines.push(question);
  });
  if (!lines.length && (brief || '').trim()) lines.push(brief.trim());
  return lines.slice(0, 4).join('\n');
}

function planBody(steps) {
  return (Array.isArray(steps) ? steps : [])
    .map((step) => (step?.intent || '').trim())
    .filter(Boolean)
    .slice(0, 6)
    .join(' → ');
}

function pathBody(steps, t) {
  const rows = Array.isArray(steps) ? steps : [];
  if (!rows.length) return '';
  const done = rows.filter((s) => s.status === 'completed' || s.status === 'skipped').length;
  const failed = rows.find((s) => s.status === 'failed');
  const waiting = rows.find((s) => s.status === 'awaiting_approval');
  if (failed) return (failed.intent || t('journeyPathFailed')).trim();
  if (waiting) return (waiting.intent || t('journeyPathWaiting')).trim();
  return t('journeyPathProgress', { done, total: rows.length });
}

function TaskJourney({ plan, defaultOpen = false }) {
  const { t } = useTranslation('ai');
  const [open, setOpen] = useState(defaultOpen);
  if (!plan) return null;
  const turns = plan.agreement_turns || plan.discovery_turns || [];
  const steps = Array.isArray(plan.steps) ? plan.steps : [];
  const chat = chatBody(turns, plan.brief || '');
  const picture = planBody(steps);
  const path = pathBody(steps, t);
  const result = (plan.final_response || '').trim();
  return (
    <Stack spacing={1} data-testid="task-journey" sx={{ mb: 1.5 }}>
      <Typography
        component="button"
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        sx={{
          display: 'block',
          width: '100%',
          textAlign: 'start',
          border: 0,
          bgcolor: 'transparent',
          p: 0,
          cursor: 'pointer',
          fontSize: '0.75rem',
          fontWeight: 600,
          color: 'text.secondary',
        }}
      >
        {t('howWeGotHere')}
      </Typography>
      <Collapse in={open}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <Chapter label={t('journeyChat')} body={chat || t('journeyEmpty')} />
          <Chapter label={t('journeyPlan')} body={picture || t('journeyEmpty')} />
          <Chapter label={t('journeyPath')} body={path || t('journeyEmpty')} />
          <Chapter label={t('journeyResult')} body={result || t('journeyResultPending')} />
        </Stack>
      </Collapse>
    </Stack>
  );
}

TaskJourney.propTypes = {
  plan: PropTypes.object,
  defaultOpen: PropTypes.bool,
};

export default TaskJourney;
