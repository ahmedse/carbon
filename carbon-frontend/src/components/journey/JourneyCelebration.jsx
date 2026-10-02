import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Typography } from '@mui/material';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import CloseIcon from '@mui/icons-material/Close';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import useReducedMotion from './useReducedMotion';
import useJourneyCelebration from './useJourneyCelebration';
import { provenOutcomes } from './journeyVoice';

const AUTO_DISMISS_MS = 7000;

/**
 * A brief, non-blocking success moment when a station genuinely turns done.
 *
 * It is inline (never an overlay, never over a form), it names the outcome the
 * engine actually proved, and it auto-dismisses. It is derived from real state
 * only — see useJourneyCelebration — so it can never fire for a click.
 */
export default function JourneyCelebration({ journey, userKey, appId }) {
  const { t } = useTranslation('journey');
  const reduced = useReducedMotion();
  const { justDone, dismiss } = useJourneyCelebration(journey, userKey, appId);

  useEffect(() => {
    if (!justDone) return undefined;
    const timer = window.setTimeout(dismiss, AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [justDone, dismiss]);

  if (!justDone) return null;

  const outcome = provenOutcomes(justDone)[0];

  return (
    <Box
      role="status"
      aria-live="polite"
      data-testid="journey-celebration"
      data-motion={reduced ? 'reduced' : 'full'}
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1,
        mb: 1.5,
        p: 1,
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'success.main',
        bgcolor: 'action.hover',
        transition: reduced ? 'none' : 'background-color 200ms ease',
      }}
    >
      <TaskAltIcon sx={{ fontSize: 18, color: 'success.main', flexShrink: 0, mt: '1px' }} aria-hidden="true" />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography sx={FONT.cardTitle} component="p">
          {t('celebrate.title', { station: justDone.title })}
        </Typography>
        <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>
          {outcome
            ? t('celebrate.body', { outcome: outcome.title })
            : t('celebrate.bodyPlain')}
        </Typography>
      </Box>
      <IconButton
        size="small"
        onClick={dismiss}
        aria-label={t('celebrate.dismiss')}
        data-testid="journey-celebration-dismiss"
      >
        <CloseIcon sx={{ fontSize: 16 }} />
      </IconButton>
    </Box>
  );
}

JourneyCelebration.propTypes = {
  journey: PropTypes.shape({ stages: PropTypes.arrayOf(PropTypes.shape({})) }),
  userKey: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  appId: PropTypes.string,
};

JourneyCelebration.defaultProps = { journey: null, userKey: null, appId: '' };
