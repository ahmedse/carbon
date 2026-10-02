import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import { routeLabel } from './journeyStages';
import {
  hereStation, momentum, nextLesson, overallProgress, stationForLesson,
} from './journeyProgress';
import useReducedMotion from './useReducedMotion';

/**
 * The journey's momentum panel: an honest overall arc, the "you are here" /
 * "what's next" nudge, and a friendly start framing.
 *
 * Every number is engine-derived — completed stations and proven outcomes only.
 * The nudge points at the real host page; when there is no next lesson with a
 * route it renders no button rather than a fabricated action. `compact` renders
 * the same content for the docked drawer tab.
 */
export default function JourneyArc({
  journey, listing, role, onGo, compact,
}) {
  const { t } = useTranslation('journey');
  const reduced = useReducedMotion();
  const progress = overallProgress(journey);
  const streak = momentum(journey);
  const here = hereStation(journey);
  const next = nextLesson(listing);
  const nextStation = next ? stationForLesson(journey, next.id) : null;
  const route = next?.route;
  const showNext = Boolean(next && route && next.state !== 'done');

  return (
    <Box
      data-testid="journey-arc"
      data-motion={reduced ? 'reduced' : 'full'}
      sx={{
        mb: 1.5,
        ...(compact
          ? { p: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }
          : {}),
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="baseline" flexWrap="wrap">
        <Typography sx={FONT.sectionTitle} color="text.secondary">{t('progress.title')}</Typography>
        <Typography sx={{ ...FONT.caption, color: 'text.secondary' }} data-testid="journey-arc-count">
          {t('progress.stations', { done: progress.done, total: progress.total })}
        </Typography>
      </Stack>

      <LinearProgress
        variant="determinate"
        value={progress.pct}
        aria-label={t('progress.label')}
        sx={{
          mt: 0.5,
          height: 6,
          borderRadius: 3,
          transition: reduced ? 'none' : 'width 240ms ease',
        }}
      />

      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" sx={{ mt: 0.75 }}>
        <Typography sx={{ ...FONT.caption, color: 'text.secondary' }} data-testid="journey-arc-outcomes">
          {t('progress.outcomes', { done: progress.outcomesProven, total: progress.outcomesTotal })}
        </Typography>
        {streak >= 2 && (
          <Chip
            size="small"
            color="success"
            variant="outlined"
            icon={<TaskAltIcon sx={{ fontSize: 14 }} />}
            data-testid="journey-streak"
            label={t('progress.streak', { n: streak })}
            sx={FONT.chip}
          />
        )}
      </Stack>

      {!progress.started && (
        <Box sx={{ mt: 0.75 }}>
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }} data-testid="journey-start">
            {t('start.body')}
          </Typography>
          {role && (
            <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.25 }} data-testid="journey-scenario">
              {t(`scenario.${role}`)}
            </Typography>
          )}
        </Box>
      )}

      {progress.started && here && (
        <Typography
          sx={{ ...FONT.caption, color: 'primary.main', mt: 0.75 }}
          data-testid="journey-here"
        >
          {t('progress.youAreHere', { station: here.title })}
        </Typography>
      )}

      {showNext && (
        <Box
          data-testid="journey-next"
          sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}
        >
          <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>
            {nextStation
              ? t('next.whatsNextWhere', { title: next.title, station: nextStation.title })
              : t('next.whatsNext', { title: next.title })}
          </Typography>
          <Button
            size="small"
            variant="contained"
            endIcon={<ArrowForwardIcon sx={{ fontSize: 14 }} />}
            onClick={() => onGo(route)}
            sx={{ textTransform: 'none' }}
          >
            {t('step.goTo', { page: routeLabel(route) })}
          </Button>
        </Box>
      )}
    </Box>
  );
}

JourneyArc.propTypes = {
  journey: PropTypes.shape({ stages: PropTypes.arrayOf(PropTypes.shape({})) }),
  listing: PropTypes.shape({ lessons: PropTypes.arrayOf(PropTypes.shape({})) }),
  role: PropTypes.string,
  onGo: PropTypes.func.isRequired,
  compact: PropTypes.bool,
};

JourneyArc.defaultProps = {
  journey: null,
  listing: null,
  role: '',
  compact: false,
};
