import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Stack, TextField, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

// A draft Pulse holds for this conversation. Nothing exists until the user
// chooses Create task (their consent). Approving and running stay in Tasks
// (ADR-0046 — Chat proposes, Agent applies).
function PlanProposalStep({ step, index }) {
  const { t } = useTranslation('ai');
  const args = Array.isArray(step.args) ? step.args : [];
  return (
    <Box
      component="li"
      sx={{
        display: 'flex',
        gap: 1,
        alignItems: 'baseline',
        py: 0.5,
        opacity: step.blocked ? 0.75 : 1,
      }}
    >
      <Typography variant="caption" sx={{ minWidth: 16, color: 'text.secondary' }}>
        {index + 1}.
      </Typography>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" component="span">
          {step.intent}
        </Typography>
        {args.length > 0 && (
          <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
            {args.map((arg) => `${arg.name}: ${arg.value}`).join(' · ')}
          </Typography>
        )}
        {step.blocked && (
          <Chip
            size="small"
            color="warning"
            variant="outlined"
            sx={{ mt: 0.5 }}
            label={
              (step.reason || step.gap)
                ? t('plan.blockedWith', { gap: step.reason || step.gap })
                : t('plan.blocked')
            }
          />
        )}
      </Box>
    </Box>
  );
}

PlanProposalStep.propTypes = {
  step: PropTypes.shape({
    intent: PropTypes.string,
    blocked: PropTypes.bool,
    gap: PropTypes.string,
    reason: PropTypes.string,
    args: PropTypes.array,
  }).isRequired,
  index: PropTypes.number.isRequired,
};

function PlanProposalForm({ proposal, onCreate, onChange, onOpenTasks }) {
  const { t } = useTranslation('ai');
  const steps = Array.isArray(proposal.steps) ? proposal.steps : [];
  const blocked = Number(proposal.blocked_count || 0);
  const refuseCreate = Boolean(proposal.blocks_create);
  const [change, setChange] = useState('');
  const [state, setState] = useState('draft');
  const [error, setError] = useState('');

  const create = async () => {
    if (!onCreate) return;
    setState('saving');
    setError('');
    try {
      await onCreate();
      setState('created');
    } catch (exc) {
      setError(exc?.message || t('plan.createFailed'));
      setState('draft');
    }
  };

  const sendChange = () => {
    const text = change.trim();
    if (!text || !onChange) return;
    setState('revising');
    onChange(text);
  };

  const locked = state !== 'draft';
  return (
    <Box
      sx={{
        mt: 1.25,
        p: 1.25,
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="subtitle2">
        {t('plan.title', { count: steps.length })}
      </Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {state === 'created' ? t('plan.created') : t('plan.notCreated')}
      </Typography>
      <Box component="ol" sx={{ listStyle: 'none', p: 0, m: 0, mt: 1 }}>
        {steps.map((step, index) => (
          <PlanProposalStep key={step.step_id ?? index} step={step} index={index} />
        ))}
      </Box>
      {blocked > 0 && (
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'warning.main' }}>
          {t('plan.blockedSummary', { count: blocked })}
        </Typography>
      )}
      {refuseCreate && (
        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'warning.main' }}>
          {t('plan.createBlocked')}
        </Typography>
      )}
      {error && (
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'error.main' }}>
          {error}
        </Typography>
      )}
      {state === 'created' ? (
        onOpenTasks && (
          <Button size="small" variant="outlined" sx={{ mt: 1 }} onClick={onOpenTasks}>
            {t('plan.open')}
          </Button>
        )
      ) : (
        <Stack spacing={1} sx={{ mt: 1.25 }}>
          <TextField
            size="small"
            fullWidth
            disabled={locked}
            placeholder={t('plan.changePlaceholder')}
            value={change}
            onChange={(event) => setChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendChange();
              }
            }}
          />
          <Stack direction="row" spacing={1}>
            <Button
              size="small"
              variant="contained"
              disabled={locked || !onCreate || refuseCreate}
              onClick={create}
            >
              {t('plan.create')}
            </Button>
            <Button
              size="small"
              variant="outlined"
              disabled={locked || !change.trim()}
              onClick={sendChange}
            >
              {t('plan.change')}
            </Button>
          </Stack>
        </Stack>
      )}
    </Box>
  );
}

PlanProposalForm.propTypes = {
  proposal: PropTypes.shape({
    steps: PropTypes.array,
    blocked_count: PropTypes.number,
    blocks_create: PropTypes.bool,
  }).isRequired,
  onCreate: PropTypes.func,
  onChange: PropTypes.func,
  onOpenTasks: PropTypes.func,
};

export default PlanProposalForm;
