import React from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';
import { lessonTone } from './journeyArt';

// Per-row hues so the camp's lesson rail reads as a bright sequence of beads.
const TONES = ['primary', 'info', 'secondary', 'success', 'warning'];

/**
 * The camp's lessons as one clean vertical timeline: a coloured node per lesson,
 * its title, the one-line outcome it proves, its step count and real minutes,
 * and an eye button that opens the dedicated lesson reader.
 *
 * The list is always visible — the eye is the affordance, and the whole row is
 * clickable too. Nothing expands inline, so one lesson is visible at a time by
 * construction. There is no lock state and no invented number: the minutes are
 * the engine's own, the steps are the pack's own.
 */
export default function LessonList({
  lessons, glossary, outcomeByLesson, onOpen,
}) {
  const { t } = useTranslation('journey');
  const rows = Array.isArray(lessons) ? lessons : [];
  if (rows.length === 0) {
    return (
      <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>
        {t('lesson.none')}
      </Typography>
    );
  }

  return (
    <Box data-testid="lesson-list" sx={{ position: 'relative' }}>
      {rows.map((lesson, index) => {
        const done = lesson.state === 'done';
        const next = !done && (lesson.is_next || lesson.state === 'started');
        const steps = Array.isArray(lesson.steps) ? lesson.steps.length : 0;
        const minutes = Number(lesson.minutes) || 0;
        const outcome = outcomeByLesson ? outcomeByLesson[lesson.id] : null;
        const tone = lessonTone(lesson);
        const last = index === rows.length - 1;
        const bead = done || next ? (done ? 'success' : 'primary') : TONES[index % TONES.length];
        const nextBead = TONES[(index + 1) % TONES.length];

        return (
          <Box
            key={lesson.id}
            data-testid={`journey-lesson-${lesson.id}`}
            data-state={lesson.state}
            onClick={() => onOpen(lesson.id)}
            sx={{
              display: 'flex',
              gap: 1.25,
              position: 'relative',
              cursor: 'pointer',
              borderRadius: 1.5,
              p: 1,
              '&:hover': { bgcolor: 'action.hover' },
            }}
          >
            {/* The timeline rail: one node plus the connector down to the next. */}
            <Box sx={{ position: 'relative', flexShrink: 0, width: 26, display: 'flex', justifyContent: 'center' }}>
              <Box
                aria-hidden="true"
                sx={{
                  zIndex: 1,
                  mt: '2px',
                  width: 26,
                  height: 26,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: done || next ? `${bead}.main` : 'background.paper',
                  color: done || next ? 'common.white' : `${bead}.main`,
                  border: '2px solid',
                  borderColor: `${bead}.main`,
                  boxShadow: (theme) => `0 0 0 3px ${alpha(theme.palette[bead].main, done || next ? 0.2 : 0.1)}`,
                }}
              >
                {done
                  ? <CheckRoundedIcon sx={{ fontSize: 15 }} />
                  : <PlayArrowRoundedIcon sx={{ fontSize: 15 }} />}
              </Box>
              {!last && (
                <Box
                  aria-hidden="true"
                  sx={{
                    position: 'absolute',
                    top: 28,
                    bottom: -8,
                    width: 3,
                    borderRadius: 3,
                    opacity: 0.55,
                    background: (theme) => `linear-gradient(180deg, ${theme.palette[bead].main} 0%, ${theme.palette[nextBead].main} 100%)`,
                  }}
                />
              )}
            </Box>

            <Box sx={{ flex: 1, minWidth: 0, pb: last ? 0 : 0.25 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                <MixedText
                  text={lesson.title}
                  glossary={glossary}
                  component="div"
                  sx={{ ...FONT.cardTitle, color: next ? 'primary.main' : 'text.primary' }}
                />
                {next && (
                  <Typography
                    component="span"
                    sx={{
                      ...FONT.caption,
                      fontWeight: 700,
                      color: 'primary.main',
                      bgcolor: (theme) => alpha(theme.palette.primary.main, 0.12),
                      borderRadius: 999,
                      px: 0.875,
                      py: 0.125,
                    }}
                  >
                    {t('lesson.nextUp')}
                  </Typography>
                )}
                {done && (
                  <Typography component="span" sx={{ ...FONT.caption, color: 'success.main' }}>
                    {t('completion.done')}
                  </Typography>
                )}
              </Box>

              {outcome && (
                <MixedText
                  text={outcome}
                  glossary={glossary}
                  component="div"
                  sx={{ ...FONT.caption, color: 'text.secondary', mt: 0.125 }}
                />
              )}

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.25, color: 'text.secondary' }}>
                <Typography sx={{ ...FONT.caption }} data-testid={`journey-lesson-steps-${lesson.id}`}>
                  {t('lesson.stepCount', { steps })}
                </Typography>
                {minutes > 0 && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                    <ScheduleRoundedIcon sx={{ fontSize: 12 }} aria-hidden="true" />
                    <Typography sx={FONT.caption}>
                      {t('scenario.aboutMinutes', { minutes })}
                    </Typography>
                  </Box>
                )}
              </Box>
            </Box>

            <Tooltip title={t('lesson.open')}>
              <IconButton
                size="small"
                onClick={(event) => { event.stopPropagation(); onOpen(lesson.id); }}
                data-testid={`journey-lesson-open-${lesson.id}`}
                aria-label={t('lesson.open')}
                sx={{
                  alignSelf: 'center',
                  flexShrink: 0,
                  color: `${tone === 'default' ? 'text.secondary' : `${tone}.main`}`,
                  border: '1px solid',
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
                }}
              >
                <VisibilityRoundedIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          </Box>
        );
      })}
    </Box>
  );
}

LessonList.propTypes = {
  lessons: PropTypes.arrayOf(PropTypes.shape({})),
  glossary: PropTypes.arrayOf(PropTypes.string),
  outcomeByLesson: PropTypes.objectOf(PropTypes.string),
  onOpen: PropTypes.func.isRequired,
};

LessonList.defaultProps = { lessons: [], glossary: [], outcomeByLesson: {} };
