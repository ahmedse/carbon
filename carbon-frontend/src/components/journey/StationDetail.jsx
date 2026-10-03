import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlaylistPlayIcon from '@mui/icons-material/PlaylistPlay';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import EmptyState from '../Page/EmptyState';
import MixedText from './MixedText';
import CompetencyOutcome from './CompetencyOutcome';
import LessonList from './LessonList';
import CampDrama from './CampDrama';
import JourneyRecall from './JourneyRecall';
import { provenOutcomes } from './journeyVoice';

/**
 * One camp's detail panel — the lessons first, the checkable outcomes last.
 *
 * The camp title and its one-line "what" live in the camp hero above, so this
 * panel never repeats them. What it owes the reader, in order, is:
 *   1. the camp's lessons as a clean timeline you can open with one click,
 *   2. then the outcomes the engine can actually prove.
 *
 * The field hazards and the field notebook are gone from the journey: their
 * full detail lives in the Lead guide and the Field guide under Help. Nothing
 * here is a lock or a score.
 *
 * When the camp is genuinely done it says in warm, specific terms what is now
 * true — one line per outcome the engine proved, never a click.
 */
export default function StationDetail({
  station, glossary, onOpenLesson, onNavigate, appId, recallLesson, onScenarioAnswer,
}) {
  const { t } = useTranslation('journey');

  // The lesson row's one-line outcome: the camp outcome that lesson proves.
  const outcomeByLesson = useMemo(() => {
    const map = {};
    (station?.competencies || []).forEach((competency) => {
      if (competency.lessonId) map[competency.lessonId] = competency.title;
    });
    return map;
  }, [station]);

  if (!station) return null;

  const empty = station.lessons.length === 0 && station.competencies.length === 0;

  return (
    <Box
      role="tabpanel"
      id={`journey-station-panel-${station.n}`}
      aria-labelledby={`journey-station-tab-${station.n}`}
      tabIndex={0}
      data-testid={`journey-station-panel-${station.n}`}
      data-state={station.state}
      sx={{ mt: 2, outline: 'none' }}
    >
      {onScenarioAnswer && (
        <CampDrama
          station={station}
          glossary={glossary}
          onAnswer={(index, choice) => onScenarioAnswer(station.key, { beat: index, choice })}
        />
      )}

      {station.done && !empty && (
        <Box
          data-testid="journey-station-done"
          sx={{
            mt: 1.5,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1,
            p: 1.25,
            borderRadius: 1.5,
            border: '1px solid',
            borderColor: 'success.main',
            bgcolor: 'action.hover',
          }}
        >
          <CheckCircleIcon sx={{ fontSize: 18, color: 'success.main', flexShrink: 0, mt: '1px' }} aria-hidden="true" />
          <Box sx={{ minWidth: 0 }}>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'baseline' }}>
              <Typography component="span" sx={FONT.cardTitle}>{t('stationDone.title')}</Typography>
              <MixedText text={station.title} glossary={glossary} component="span" sx={{ ...FONT.cardTitle, color: 'success.main' }} />
            </Box>
            <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>
              {t('stationDone.body', { proven: station.outcomesProven, total: station.outcomesTotal })}
            </Typography>
            {provenOutcomes(station).length > 0 && (
              <Box sx={{ mt: 0.5 }} data-testid="journey-station-true-now">
                <Typography sx={FONT.sectionTitle} color="text.secondary">{t('stationDone.trueNow')}</Typography>
                <Box component="ul" sx={{ m: 0, mt: 0.25, p: 0, listStyle: 'none' }}>
                  {provenOutcomes(station).map((outcome) => (
                    <Box component="li" key={outcome.key} sx={{ display: 'flex', gap: 0.75, alignItems: 'flex-start', mt: 0.25 }}>
                      <CheckCircleIcon sx={{ fontSize: 12, color: 'success.main', flexShrink: 0, mt: '3px' }} aria-hidden="true" />
                      <MixedText
                        text={outcome.good || outcome.title}
                        glossary={glossary}
                        component="span"
                        sx={{ ...FONT.caption, color: 'text.secondary' }}
                      />
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        </Box>
      )}

      {empty ? (
        <Box sx={{ mt: 1.5 }}>
          <EmptyState title={t('empty.nothingOwed.title')} description={t('empty.nothingOwed.body')} />
        </Box>
      ) : (
        <>
          {station.lessons.length > 0 && (
            <Box sx={{ mt: 1.5 }} data-testid="journey-lessons">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                <PlaylistPlayIcon sx={{ fontSize: 18, color: 'primary.main' }} aria-hidden="true" />
                <Typography sx={FONT.sectionTitle} color="text.secondary">
                  {t('sections.missions', { n: station.lessons.length })}
                </Typography>
              </Box>
              <LessonList
                lessons={station.lessons}
                glossary={glossary}
                outcomeByLesson={outcomeByLesson}
                onOpen={onOpenLesson}
              />
            </Box>
          )}

          {station.competencies.length > 0 && (
            <Box sx={{ mt: 2 }} data-testid="journey-outcomes">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.25 }}>
                <FactCheckIcon sx={{ fontSize: 18, color: 'success.main' }} aria-hidden="true" />
                <Typography sx={FONT.sectionTitle} color="text.secondary">
                  {t('sections.outcomesTitle')}
                </Typography>
              </Box>
              {station.competencies.map((competency) => (
                <CompetencyOutcome
                  key={competency.key}
                  competency={competency}
                  glossary={glossary}
                  onGo={onNavigate}
                />
              ))}
            </Box>
          )}
        </>
      )}

      {!empty && appId && recallLesson && (
        <JourneyRecall appId={appId} lesson={recallLesson} glossary={glossary} />
      )}
    </Box>
  );
}

StationDetail.propTypes = {
  station: PropTypes.shape({}),
  glossary: PropTypes.arrayOf(PropTypes.string),
  onOpenLesson: PropTypes.func.isRequired,
  onNavigate: PropTypes.func.isRequired,
  appId: PropTypes.string,
  recallLesson: PropTypes.shape({}),
  onScenarioAnswer: PropTypes.func,
};

StationDetail.defaultProps = {
  station: null, glossary: [], appId: '', recallLesson: null, onScenarioAnswer: undefined,
};
