// Journey — the onboarding landing at /carbon/onboarding and the generic
// /journey/:appId. It frames the guide engine: one pack per app, read-only.
// ?view=readiness on carbon renders the moved O1 checklist rather than a 404.

import React, { useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, Typography,
} from '@mui/material';
import RouteIcon from '@mui/icons-material/Route';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { FONT } from '../../theme/themeTokens';
import { useAuth } from '../../auth/AuthContext';
import { useDrawerJourneyView } from '../../inspector/useDrawerJourneyView';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useJourney from '../../components/journey/useJourney';
import { findLessonContext, onboardingViewFromSearch, pickStation } from '../../components/journey/journeyStages';
import RoleSwitch from '../../components/journey/RoleSwitch';
import StationRail from '../../components/journey/StationRail';
import StationDetail from '../../components/journey/StationDetail';
import LessonReader from '../../components/journey/LessonReader';
import MixedText from '../../components/journey/MixedText';
import JourneyArc from '../../components/journey/JourneyArc';
import JourneyScenario from '../../components/journey/JourneyScenario';
import JourneyCelebration from '../../components/journey/JourneyCelebration';
import useJourneyRole from '../../components/journey/useJourneyRole';
import { recallLesson } from '../../components/journey/journeyVoice';
import OnboardingPage from './OnboardingPage';

function ClosedHistory({ closed }) {
  const { t } = useTranslation('journey');
  if (!closed || closed.length === 0) return null;
  return (
    <Accordion
      disableGutters
      elevation={0}
      data-testid="journey-closed-history"
      sx={{ mt: 1.5, border: 1, borderColor: 'divider', borderRadius: 1, bgcolor: 'transparent', '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography sx={FONT.sectionTitle}>{t('closedHistory.title')}</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Typography sx={{ ...FONT.body2, color: 'text.secondary', mb: 1 }}>{t('closedHistory.body')}</Typography>
        <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
          {closed.map((period) => (
            <Box component="li" key={period.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography sx={{ ...FONT.body2, flex: 1, minWidth: 120 }}>{period.name || period.id}</Typography>
              <Chip size="small" variant="outlined" label={period.status} sx={FONT.chip} />
              <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>
                {t('closedHistory.dates', { start: period.start_date, end: period.end_date })}
              </Typography>
            </Box>
          ))}
        </Box>
        <Typography sx={{ ...FONT.caption, color: 'text.secondary', mt: 1 }}>{t('closedHistory.note')}</Typography>
      </AccordionDetails>
    </Accordion>
  );
}

ClosedHistory.propTypes = { closed: PropTypes.arrayOf(PropTypes.shape({})) };
ClosedHistory.defaultProps = { closed: [] };

export function JourneyStationSurface({ appId }) {
  const { t } = useTranslation('journey');
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { user } = useAuth();
  const userKey = user?.id ?? user?.username ?? null;
  const [track, setTrack] = useJourneyRole(userKey, appId);

  const {
    phase, journey: model, period, closed, reload, effectiveTrack, data,
  } = useJourney(appId, track);

  // The SAME persisted view the drawer Journey tab reads and writes.
  const [view, updateView] = useDrawerJourneyView(user?.id ?? user?.username ?? null, appId);

  // A deep link /journey/<appId>?station=N wins for this load, then becomes the
  // persisted selection the drawer shows.
  const rawStation = params.get('station');
  useEffect(() => {
    if (rawStation == null || rawStation === '') return;
    const wantedN = Number(rawStation);
    if (!Number.isFinite(wantedN)) return;
    const wanted = model?.stages?.find((station) => station.n === wantedN);
    if (wanted) updateView({ lessonId: null, stationKey: wanted.key, stationN: wanted.n });
  }, [rawStation, model, updateView]);

  // Resolve the stored station by its STABLE key first (index as fallback), and
  // fall back to the current stage / first station when it no longer exists.
  const selectedStation = useMemo(
    () => (model ? pickStation(model.stages, view, model.currentStage) : null),
    [model, view],
  );

  const review = useMemo(
    () => (model ? recallLesson(model, selectedStation) : null),
    [model, selectedStation],
  );

  const periodLabel = period.status === 'open'
    ? `${period.period?.name || t('periodChip.open')} · ${t('periodChip.open')}`
    : (period.status === 'many' ? t('periodChip.many') : t('periodChip.none'));
  const periodTone = period.status === 'open' ? 'success' : (period.status === 'many' ? 'warning' : 'default');

  const onSelectStation = (n) => {
    const wanted = model?.stages?.find((station) => station.n === n);
    if (!wanted) return;
    updateView({ lessonId: null, stationKey: wanted.key, stationN: wanted.n });
  };

  const onRoleChange = (nextTrack) => {
    setTrack(nextTrack);
  };

  const complete = Boolean(model && model.stagesTotal > 0 && model.stagesDone === model.stagesTotal);
  const isCarbon = appId === 'carbon';

  useDocumentTitle(t('title'));

  return (
    <PageContainer>
      <PageHeader
        icon={RouteIcon}
        title={t('title')}
        titleComponent="h1"
        subtitle={t('subtitle', { role: t(`role.${model ? model.path : 'owner'}`) })}
        actions={(
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
            <RoleSwitch value={effectiveTrack} onChange={onRoleChange} disabled={phase !== 'loaded'} />
            <Chip size="small" color={periodTone} variant="outlined" label={periodLabel} />
            <Button variant="contained" size="small" onClick={reload}>{t('refresh')}</Button>
          </Box>
        )}
      />

      {phase === 'loading' && <LoadingSkeleton variant="card" />}

      {phase === 'error' && <ErrorAlert message={t('loadFailed')} onRetry={reload} />}

      {phase === 'loaded' && model && (
        <>
          {!model.hasWork ? (
            <EmptyState title={t('empty.noRole.title')} description={t('empty.noRole.body')} />
          ) : (
            <>
              <JourneyArc
                journey={model}
                listing={data}
                role={model.path}
                onGo={(route) => navigate(route)}
              />

              <JourneyCelebration journey={model} userKey={userKey} appId={appId} />

              <JourneyScenario
                journey={model}
                station={selectedStation}
                role={model.path}
                onOpenLesson={(id) => navigate(`/journey/${appId}/${id}`)}
                showRolePrompt={!track}
                onRoleChange={setTrack}
              />

              {model.intro && (
                <Box data-testid="journey-intro" sx={{ mb: 2 }}>
                  <Typography sx={{ ...FONT.sectionTitle, mb: 0.5 }} color="text.secondary">
                    {t('whatThisJourneyIs')}
                  </Typography>
                  <MixedText
                    text={model.intro}
                    glossary={model.glossary}
                    component="p"
                    sx={{ ...FONT.body2, color: 'text.secondary', m: 0 }}
                  />
                </Box>
              )}

              {complete && (
                <Alert
                  severity="success"
                  sx={{ mb: 2 }}
                  action={isCarbon ? <Button color="inherit" size="small" onClick={() => navigate('/carbon/reporting')}>{t('cta.viewReports')}</Button> : undefined}
                >
                  {t('pathComplete')}
                </Alert>
              )}

              <StationRail
                stations={model.stages}
                selectedN={selectedStation?.n ?? null}
                onSelect={onSelectStation}
              />

              <StationDetail
                station={selectedStation}
                glossary={model.glossary}
                appId={appId}
                recallLesson={review}
                onOpenLesson={(id) => navigate(`/journey/${appId}/${id}`)}
                onNavigate={(route) => navigate(route)}
              />

              {isCarbon && selectedStation && selectedStation.key === 'report' && <ClosedHistory closed={closed} />}

              {isCarbon && (
                <Box sx={{ mt: 1.5 }}>
                  <Button size="small" variant="text" onClick={() => navigate('/carbon/onboarding/readiness')}>
                    {t('readiness.link')}
                  </Button>
                </Box>
              )}
            </>
          )}
        </>
      )}
    </PageContainer>
  );
}

JourneyStationSurface.propTypes = { appId: PropTypes.string.isRequired };

/**
 * The dedicated lesson reader at /journey/<appId>/<lessonId>. It resolves the
 * lesson from the same journey payload, names its station (navigating back),
 * and walks the station's lessons with Prev/Next, ending on the station
 * summary. The lesson id lives in the URL, so a refresh, back or forward lands
 * on the same lesson; /carbon/onboarding is served by the station surface.
 */
export function JourneyReaderSurface({ appId, lessonId }) {
  const { t } = useTranslation('journey');
  const navigate = useNavigate();
  const { user } = useAuth();
  const {
    phase, journey: model, reload,
  } = useJourney(appId);
  const context = useMemo(() => findLessonContext(model, lessonId), [model, lessonId]);
  const [, updateView] = useDrawerJourneyView(user?.id ?? user?.username ?? null, appId);

  // The deep-linked lesson wins for this load, then becomes the persisted
  // selection (station included) the drawer and the main page share.
  useEffect(() => {
    if (!context) return;
    updateView({
      lessonId,
      stationKey: context.station.key,
      stationN: context.station.n,
    });
  }, [context, lessonId, updateView]);

  useDocumentTitle(t('reader.title'));

  const toStation = (station) => navigate(`/journey/${appId}?station=${station.n}`);

  return (
    <PageContainer>
      {phase === 'loading' && <LoadingSkeleton variant="card" />}
      {phase === 'error' && <ErrorAlert message={t('loadFailed')} onRetry={reload} />}
      {phase === 'loaded' && model && !context && (
        <EmptyState
          title={t('reader.missing.title')}
          description={t('reader.missing.body')}
          actionLabel={t('reader.missing.action')}
          onAction={() => navigate(`/journey/${appId}`)}
        />
      )}
      {phase === 'loaded' && model && context && (
        <LessonReader
          station={context.station}
          lesson={context.lesson}
          glossary={model.glossary}
          onGo={(route) => navigate(route)}
          onBackToStation={() => toStation(context.station)}
          prevLesson={context.prev}
          nextLesson={context.next}
          onNavigateLesson={(id) => navigate(`/journey/${appId}/${id}`)}
          onStationSummary={() => toStation(context.station)}
        />
      )}
    </PageContainer>
  );
}

JourneyReaderSurface.propTypes = { appId: PropTypes.string.isRequired, lessonId: PropTypes.string.isRequired };

/** The route component: the station surface, the lesson reader, or the moved O1 readiness checklist from ?view. */
export default function JourneyPage({ appId: appIdProp = 'carbon' }) {
  const { appId: appIdParam, lessonId } = useParams();
  const [params] = useSearchParams();
  const appId = appIdParam || appIdProp;
  if (appId === 'carbon' && onboardingViewFromSearch(params.toString()) === 'readiness') {
    return <OnboardingPage />;
  }
  if (lessonId) return <JourneyReaderSurface appId={appId} lessonId={lessonId} />;
  return <JourneyStationSurface appId={appId} />;
}

JourneyPage.propTypes = { appId: PropTypes.string };
JourneyPage.defaultProps = { appId: 'carbon' };
