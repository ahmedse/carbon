// src/apps/my/components/ApproverChainStepper.jsx
// Presentational — vertical chain: Submitted (origin) → approver_chain steps.
// Ordered by `order`. Active step (order === current_step) highlighted;
// earlier complete; later pending; skipped (decision === 'skip') greyed.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { useTranslation } from 'react-i18next';
import { SectionTitle } from './myRequestsCommon';
import { codeLabel, ROLE_SUFFIX, INTENT_SUFFIX } from './myRequestsLabels';

const STATE_COLOR = {
  active: 'primary.main',
  complete: 'success.main',
  pending: 'text.disabled',
  skipped: 'text.disabled',
};

function StepMarker({ state, displayIndex }) {
  return (
    <Box
      sx={{
        width: 18,
        height: 18,
        borderRadius: '50%',
        border: '1px solid',
        borderColor: STATE_COLOR[state],
        bgcolor: state === 'active' ? 'primary.main' : 'background.paper',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      {state === 'complete' ? (
        <CheckIcon sx={{ fontSize: '0.75rem', color: 'success.main' }} />
      ) : (
        <Typography
          variant="caption"
          sx={{
            fontSize: '0.625rem',
            lineHeight: 1,
            color: state === 'active' ? 'primary.contrastText' : STATE_COLOR[state],
          }}
        >
          {displayIndex}
        </Typography>
      )}
    </Box>
  );
}

StepMarker.propTypes = {
  state: PropTypes.oneOf(['active', 'complete', 'pending', 'skipped']).isRequired,
  displayIndex: PropTypes.number.isRequired,
};

function StateChip({ state, label }) {
  return (
    <Typography
      variant="caption"
      component="span"
      sx={{
        fontSize: '0.625rem',
        textTransform: 'uppercase',
        letterSpacing: '0.03em',
        color: STATE_COLOR[state],
        border: '1px solid',
        borderColor: STATE_COLOR[state],
        borderRadius: 1,
        px: 0.5,
        py: 0.125,
        lineHeight: 1.2,
      }}
    >
      {label}
    </Typography>
  );
}

StateChip.propTypes = {
  state: PropTypes.oneOf(['active', 'complete', 'pending', 'skipped']).isRequired,
  label: PropTypes.string.isRequired,
};

export default function ApproverChainStepper({ chain, currentStep, status }) {
  const { t } = useTranslation('my');

  const steps = useMemo(() => {
    const list = Array.isArray(chain) ? chain : [];
    return [...list].sort((a, b) => Number(a.order ?? 0) - Number(b.order ?? 0));
  }, [chain]);

  const originComplete = Boolean(status && status !== 'draft');
  const originState = originComplete ? 'complete' : 'pending';

  const stateLabels = {
    active: t('stepperActive'),
    complete: t('stepperComplete'),
    pending: t('stepperPending'),
    skipped: t('stepperSkipped'),
  };

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AccountTreeIcon} title={t('stepperTitle')} />
        {steps.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t('stepperEmpty')}
          </Typography>
        ) : (
          <Stack component="ol" spacing={0} sx={{ listStyle: 'none', m: 0, p: 0 }}>
            <Box
              component="li"
              key="submitted"
              aria-label={`${t('graphNodeSubmitted')} — ${t('graphNodeRequester')} — ${stateLabels[originState]}`}
              sx={{ display: 'flex', gap: 1, pb: 1.25 }}
            >
              <Box
                sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}
                aria-hidden="true"
              >
                <StepMarker state={originState} displayIndex={1} />
                <Box sx={{ width: 1, flex: 1, minHeight: 12, bgcolor: 'divider' }} />
              </Box>
              <Box sx={{ minWidth: 0, pt: 0.125 }}>
                <Stack direction="row" alignItems="center" spacing={0.75} useFlexGap flexWrap="wrap">
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 500, color: 'text.primary' }}
                  >
                    {t('graphNodeSubmitted')}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t('graphNodeRequester')}
                  </Typography>
                  <StateChip state={originState} label={stateLabels[originState]} />
                </Stack>
              </Box>
            </Box>
            {steps.map((step, index) => {
              const order = Number(step.order ?? 0);
              const isSkipped = step.decision === 'skip';
              let state;
              if (isSkipped) state = 'skipped';
              else if (currentStep != null && order === currentStep) state = 'active';
              else if (currentStep != null && order < currentStep) state = 'complete';
              else state = 'pending';

              const stateLabel = stateLabels[state];
              // acting_role: HR (or another backup) standing in for a vacant role.
              const role = codeLabel(t, 'role', ROLE_SUFFIX, step.acting_role || step.role);
              const intent = codeLabel(t, 'intent', INTENT_SUFFIX, step.intent);
              const approverCount = Array.isArray(step.user_ids) ? step.user_ids.length : 0;
              const isLast = index === steps.length - 1;
              const displayIndex = index + 2; // after origin

              return (
                <Box
                  component="li"
                  key={`${step.order ?? index}-${index}`}
                  aria-label={`${role} — ${intent} — ${stateLabel}`}
                  aria-current={state === 'active' ? 'step' : undefined}
                  sx={{
                    display: 'flex',
                    gap: 1,
                    pb: isLast ? 0 : 1.25,
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                    }}
                    aria-hidden="true"
                  >
                    <StepMarker state={state} displayIndex={displayIndex} />
                    {!isLast && (
                      <Box sx={{ width: 1, flex: 1, minHeight: 12, bgcolor: 'divider' }} />
                    )}
                  </Box>
                  <Box sx={{ minWidth: 0, pt: 0.125 }}>
                    <Stack
                      direction="row"
                      alignItems="center"
                      spacing={0.75}
                      useFlexGap
                      flexWrap="wrap"
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: state === 'active' ? 700 : 500,
                          color: isSkipped ? 'text.disabled' : 'text.primary',
                        }}
                      >
                        {role}
                      </Typography>
                      <Typography
                        variant="body2"
                        color={isSkipped ? 'text.disabled' : 'text.secondary'}
                      >
                        {intent}
                      </Typography>
                      <StateChip state={state} label={stateLabel} />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {isSkipped ? '—' : t('stepperApprovers', { count: approverCount })}
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

ApproverChainStepper.propTypes = {
  chain: PropTypes.array.isRequired,
  currentStep: PropTypes.number,
  status: PropTypes.string,
};

ApproverChainStepper.defaultProps = {
  currentStep: null,
  status: null,
};
