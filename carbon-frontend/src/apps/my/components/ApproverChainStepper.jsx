// src/apps/my/components/ApproverChainStepper.jsx
// Presentational — vertical approver chain from `approver_chain`, ordered by
// `order`. Each step shows localized role + intent + approver count. The
// active step (order === current_step) is highlighted; earlier steps complete;
// later steps pending; skipped steps (decision === 'skip') are greyed out.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { useTranslation } from 'react-i18next';
import { SectionTitle } from './myRequestsCommon';
import { codeLabel, ROLE_SUFFIX, INTENT_SUFFIX } from './myRequestsLabels';
import { FONT } from '../../../theme/themeTokens';

const STATE_COLOR = {
  active: 'primary.main',
  complete: 'success.main',
  pending: 'text.disabled',
  skipped: 'text.disabled',
};

export default function ApproverChainStepper({ chain, currentStep }) {
  const { t } = useTranslation('my');

  const steps = useMemo(() => {
    const list = Array.isArray(chain) ? chain : [];
    return [...list].sort((a, b) => Number(a.order ?? 0) - Number(b.order ?? 0));
  }, [chain]);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AccountTreeIcon} title={t('stepperTitle')} />
        {steps.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('stepperEmpty')}
          </Typography>
        ) : (
          <Stack component="ol" spacing={0} sx={{ listStyle: 'none', m: 0, p: 0 }}>
            {steps.map((step, index) => {
              const order = Number(step.order ?? 0);
              const isSkipped = step.decision === 'skip';
              let state;
              if (isSkipped) state = 'skipped';
              else if (currentStep != null && order === currentStep) state = 'active';
              else if (currentStep != null && order < currentStep) state = 'complete';
              else state = 'pending';

              const stateLabel = {
                active: t('stepperActive'),
                complete: t('stepperComplete'),
                pending: t('stepperPending'),
                skipped: t('stepperSkipped'),
              }[state];

              const role = codeLabel(t, 'role', ROLE_SUFFIX, step.role);
              const intent = codeLabel(t, 'intent', INTENT_SUFFIX, step.intent);
              const approverCount = Array.isArray(step.user_ids) ? step.user_ids.length : 0;

              return (
                <Box
                  component="li"
                  key={`${step.order ?? index}-${index}`}
                  aria-label={`${role} — ${intent} — ${stateLabel}`}
                  aria-current={state === 'active' ? 'step' : undefined}
                  sx={{
                    display: 'flex',
                    gap: 1,
                    pb: index === steps.length - 1 ? 0 : 1.25,
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
                          sx={{
                            ...FONT.bodySmall,
                            lineHeight: 1,
                            color: state === 'active' ? 'primary.contrastText' : STATE_COLOR[state],
                          }}
                        >
                          {order + 1}
                        </Typography>
                      )}
                    </Box>
                    {index < steps.length - 1 && (
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
                        sx={{
                          ...FONT.body2,
                          fontWeight: state === 'active' ? 700 : 500,
                          color: isSkipped ? 'text.disabled' : 'text.primary',
                        }}
                      >
                        {role}
                      </Typography>
                      <Typography
                        sx={{ ...FONT.body, color: isSkipped ? 'text.disabled' : 'text.secondary' }}
                      >
                        {intent}
                      </Typography>
                      <Typography
                        sx={{
                          ...FONT.bodySmall,
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
                        {stateLabel}
                      </Typography>
                    </Stack>
                    <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
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
};

ApproverChainStepper.defaultProps = {
  currentStep: null,
};
