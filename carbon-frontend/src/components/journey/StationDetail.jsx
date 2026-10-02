import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import EmptyState from '../Page/EmptyState';
import MixedText from './MixedText';
import CompetencyOutcome from './CompetencyOutcome';
import LessonList from './LessonList';
import JourneyRecall from './JourneyRecall';
import { provenOutcomes } from './journeyVoice';

/**
 * One station panel: a plain-language description of the station, its checkable
 * outcomes with "what good looks like", and its lessons as a compact list that
 * opens the dedicated lesson reader. No lesson body is rendered inline.
 *
 * There is no lock reason and no hidden action. Every outcome and lesson row
 * navigates to the real host page or to the reader for that lesson.
 *
 * When the station is genuinely done, it says in warm, specific terms what is
 * now true — one line per outcome the engine proved, never a click. A read-only
 * spaced-review check-in resurfaces an earlier finished lesson's question.
 */
export default function StationDetail({
  station, glossary, onOpenLesson, onNavigate, appId, recallLesson,
}) {
  const { t } = useTranslation('journey');

  // The lesson row's one-line outcome: the station outcome that lesson proves.
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
      sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5, mt: 1.5, outline: 'none' }}
    >
      <MixedText text={station.title} glossary={glossary} component="h2" sx={FONT.pageTitle} />
      {station.what && (
        <MixedText
          text={station.what}
          glossary={glossary}
          component="p"
          sx={{ ...FONT.body2, color: 'text.secondary', mt: 0.5 }}
        />
      )}

      {station.done && !empty && (
        <Box
          data-testid="journey-station-done"
          sx={{
            mt: 1.25,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1,
            p: 1,
            borderRadius: 1,
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
          {station.competencies.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              <Typography sx={FONT.sectionTitle} color="text.secondary">
                {t('sections.outcomesTitle')}
              </Typography>
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

          {station.lessons.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              <Typography sx={{ ...FONT.sectionTitle, mb: 0.5 }} color="text.secondary">
                {t('sections.lessons')}
              </Typography>
              <LessonList
                lessons={station.lessons}
                glossary={glossary}
                outcomeByLesson={outcomeByLesson}
                onOpen={onOpenLesson}
              />
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
};

StationDetail.defaultProps = {
  station: null, glossary: [], appId: '', recallLesson: null,
};
