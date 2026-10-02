import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';
import LessonStepTimeline from './LessonStepTimeline';

/**
 * The master-detail lesson reader: one lesson at a time, its header naming the
 * station (which navigates back to the station detail), the lesson and the
 * active step, with Prev/Next walking the station's lessons. The body is the
 * existing LessonStepTimeline — the same vertical node timeline the station
 * used — so there is no second timeline component.
 *
 * `compact` renders the same content for the docked launcher: a narrow header
 * with the same controls, still reusing LessonStepTimeline. Deep-linked state
 * lives in the route, so a refresh or the back button lands on the same lesson.
 */
export default function LessonReader({
  station, lesson, glossary, onGo, onBackToStation,
  prevLesson, nextLesson, onNavigateLesson, onStationSummary, compact,
}) {
  const { t } = useTranslation('journey');
  const steps = Array.isArray(lesson.steps) ? lesson.steps : [];
  const [activeStep, setActiveStep] = useState(0);

  // A new lesson starts at its first step; the URL, not local state, owns which
  // lesson is open, so refresh/back/forward keep the same lesson on screen.
  useEffect(() => {
    setActiveStep(0);
  }, [lesson.id]);

  const clamped = steps.length > 0 ? Math.min(activeStep, steps.length - 1) : 0;
  const hasPrev = Boolean(prevLesson);
  const hasNext = Boolean(nextLesson);

  const stationButton = (
    <Button
      size="small"
      variant="text"
      startIcon={<ArrowBackIcon sx={{ fontSize: 14 }} />}
      onClick={onBackToStation}
      data-testid="lesson-reader-station"
      sx={{ textTransform: 'none', maxWidth: compact ? '100%' : 220, justifyContent: 'flex-start' }}
    >
      <MixedText text={station.title} glossary={glossary} />
    </Button>
  );

  const controls = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
      {stationButton}
      <Typography sx={{ ...FONT.caption, color: 'text.secondary' }} data-testid="lesson-reader-stepcount">
        {t('step.stepOf', { n: steps.length > 0 ? clamped + 1 : 0, total: steps.length })}
      </Typography>
      <Button
        size="small"
        variant="outlined"
        disabled={!hasPrev}
        onClick={() => hasPrev && onNavigateLesson(prevLesson.id)}
        data-testid="lesson-reader-prev"
        sx={{ textTransform: 'none' }}
      >
        {t('reader.prev')}
      </Button>
      <Button
        size="small"
        variant="contained"
        onClick={() => (hasNext ? onNavigateLesson(nextLesson.id) : onStationSummary())}
        data-testid="lesson-reader-next"
        sx={{ textTransform: 'none' }}
      >
        {hasNext ? t('reader.next') : t('reader.stationSummary')}
      </Button>
    </Box>
  );

  if (compact) {
    return (
      <Box data-testid="lesson-reader" data-compact="true">
        <MixedText text={lesson.title} glossary={glossary} component="h3" sx={FONT.cardTitle} />
        <Box sx={{ mt: 0.5 }}>{controls}</Box>
        <LessonStepTimeline
          steps={steps}
          glossary={glossary}
          onGo={onGo}
          activeIndex={clamped}
          onSelectStep={setActiveStep}
        />
      </Box>
    );
  }

  return (
    <Box data-testid="lesson-reader">
      <Box
        sx={{
          borderBottom: '1px solid',
          borderColor: 'divider',
          pb: 0.5,
          mb: 1,
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 0.75,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <MixedText text={lesson.title} glossary={glossary} component="h1" sx={FONT.cardTitle} />
          <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('reader.stationLabel')}</Typography>
        </Box>
        {controls}
      </Box>
      <LessonStepTimeline
        steps={steps}
        glossary={glossary}
        onGo={onGo}
        activeIndex={clamped}
        onSelectStep={setActiveStep}
      />
    </Box>
  );
}

LessonReader.propTypes = {
  station: PropTypes.shape({ title: PropTypes.string }).isRequired,
  lesson: PropTypes.shape({ id: PropTypes.string.isRequired, title: PropTypes.string, steps: PropTypes.array }).isRequired,
  glossary: PropTypes.arrayOf(PropTypes.string),
  onGo: PropTypes.func.isRequired,
  onBackToStation: PropTypes.func.isRequired,
  prevLesson: PropTypes.shape({ id: PropTypes.string.isRequired }),
  nextLesson: PropTypes.shape({ id: PropTypes.string.isRequired }),
  onNavigateLesson: PropTypes.func.isRequired,
  onStationSummary: PropTypes.func.isRequired,
  compact: PropTypes.bool,
};

LessonReader.defaultProps = {
  glossary: [], prevLesson: null, nextLesson: null, compact: false,
};
