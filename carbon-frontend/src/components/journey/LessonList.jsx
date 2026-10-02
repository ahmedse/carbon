import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';

/**
 * The station's lessons as a plain list of rows: title, the one-line outcome it
 * proves, its step count and a small done indicator. Selecting a row opens the
 * dedicated lesson reader; nothing expands inline, so one lesson is visible at
 * a time by construction. There is no lock state.
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
    <Box data-testid="lesson-list" sx={{ display: 'grid', gap: 0.75 }}>
      {rows.map((lesson) => {
        const done = lesson.state === 'done';
        const steps = Array.isArray(lesson.steps) ? lesson.steps.length : 0;
        const outcome = outcomeByLesson ? outcomeByLesson[lesson.id] : null;
        return (
          <Box
            key={lesson.id}
            component="button"
            type="button"
            data-testid={`journey-lesson-${lesson.id}`}
            data-state={lesson.state}
            onClick={() => onOpen(lesson.id)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              width: '100%',
              textAlign: 'start',
              cursor: 'pointer',
              font: 'inherit',
              color: 'inherit',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              bgcolor: 'background.paper',
              p: 1,
              '&:hover': { bgcolor: 'action.hover' },
              '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: -2 },
            }}
          >
            {done ? (
              <CheckCircleIcon sx={{ fontSize: '1rem', color: 'success.main', flexShrink: 0 }} aria-hidden="true" />
            ) : (
              <RadioButtonUncheckedIcon sx={{ fontSize: '1rem', color: 'text.disabled', flexShrink: 0 }} aria-hidden="true" />
            )}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <MixedText text={lesson.title} glossary={glossary} component="div" sx={FONT.body2} />
              {outcome && (
                <MixedText
                  text={outcome}
                  glossary={glossary}
                  component="div"
                  sx={{ ...FONT.caption, color: 'text.secondary', mt: 0.25 }}
                />
              )}
            </Box>
            <Typography sx={{ ...FONT.caption, color: 'text.secondary', flexShrink: 0 }} data-testid={`journey-lesson-steps-${lesson.id}`}>
              {t('lesson.stepCount', { steps })}
            </Typography>
            {done && (
              <Typography sx={{ ...FONT.caption, color: 'success.main', flexShrink: 0 }}>
                {t('completion.done')}
              </Typography>
            )}
            <ChevronRightIcon sx={{ fontSize: 16, color: 'text.secondary', flexShrink: 0 }} aria-hidden="true" />
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
