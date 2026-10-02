// src/inspector/tabs/journeyTabs.jsx
// The Journey inspector tab (ADR-0019 contribution point).
//
// Journey is a peer of Notes in the ONE standard system-wide drawer: same shell,
// same open/close control, same resize behavior, same tab strip, same persisted
// active tab. There is no separate Journey dock anywhere.
//
// The tab registers only while the route names an app journey (/journey/<appId>
// or an app studio route), so the drawer does not grow a dead tab on pages with
// no journey. The body reuses the journey UI that already exists — StationRail +
// LessonList for the station list, and the compact LessonReader on a lesson
// route. It carries no notes store: notes are the drawer's standard Notes tab
// right beside it (ADR-0046 read/teach + notes only, no host writes).
//
// NAVIGATION CONTRACT: everything the user does inside the tab (station tile,
// lesson row, Prev/Next, back-to-station) stays INSIDE the tab and never touches
// the main-area route, so the page the user is working on is never unmounted.
// The one deliberate exception is the labelled "Go to <page>" step button, which
// intentionally opens a real host page in the main area — an explicit button,
// never a row click.

import React, { useEffect, useMemo, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import RouteIcon from '@mui/icons-material/Route';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import { useAuth } from '../../auth/AuthContext';
import { registerInspectorTab } from '../InspectorTabRegistry';
import { useDrawerJourneyView } from '../useDrawerJourneyView';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useJourney from '../../components/journey/useJourney';
import {
  findLessonContext,
  journeyContextFromPath,
  pickStation,
} from '../../components/journey/journeyStages';
import StationRail from '../../components/journey/StationRail';
import LessonList from '../../components/journey/LessonList';
import LessonReader from '../../components/journey/LessonReader';
import JourneyArc from '../../components/journey/JourneyArc';
import JourneyScenario from '../../components/journey/JourneyScenario';
import JourneyCelebration from '../../components/journey/JourneyCelebration';
import useJourneyRole from '../../components/journey/useJourneyRole';

/** The Journey tab body: station list, or the compact lesson reader on a lesson route. */
export function JourneyTabBody() {
  const { t } = useTranslation('journey');
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const route = journeyContextFromPath(location.pathname);
  const appId = route?.appId || null;
  const routeLessonId = route?.lessonId || null;
  const userKey = user?.id ?? user?.username ?? null;
  const [role] = useJourneyRole(userKey, appId);
  const { phase, journey, reload, data } = useJourney(appId, role);

  // ONE shared, persisted, per user + per app view state. The main Journey page
  // writes the same key, so the two surfaces can never drift apart.
  const [view, updateView] = useDrawerJourneyView(user?.id ?? user?.username ?? null, appId);

  // An explicit main-route lesson (deep link or the main Journey reader) wins
  // for this load, then becomes the persisted selection, station included.
  useEffect(() => {
    if (!routeLessonId || !journey) return;
    const ctx = findLessonContext(journey, routeLessonId);
    if (!ctx) {
      updateView({ lessonId: routeLessonId });
      return;
    }
    updateView({
      lessonId: routeLessonId,
      stationKey: ctx.station.key,
      stationN: ctx.station.n,
    });
  }, [routeLessonId, journey, updateView]);

  const station = useMemo(
    () => pickStation(journey?.stages, view, journey?.currentStage || null),
    [journey, view],
  );

  const lessonId = view.lessonId || null;
  const lessonContext = useMemo(() => findLessonContext(journey, lessonId), [journey, lessonId]);
  // A persisted lesson that no longer exists in the pack falls back to the
  // station rail; only an explicit route lesson shows the missing-reader state.
  const showReader = Boolean(lessonId && (lessonContext || routeLessonId === lessonId));

  const outcomeByLesson = useMemo(() => {
    const map = {};
    (station?.competencies || []).forEach((row) => {
      if (row.lessonId) map[row.lessonId] = row.title;
    });
    return map;
  }, [station]);

  // Drawer scroll memory: the contextual tab body scrolls inside the drawer's
  // shared scroll container, so remember where the user was and restore it when
  // the tab is shown again (same persistence as the rest of the drawer).
  const rootRef = useRef(null);
  const initialScroll = useRef(view.scrollTop || 0);
  const updateRef = useRef(updateView);
  useEffect(() => { updateRef.current = updateView; }, [updateView]);
  useEffect(() => {
    const el = rootRef.current?.closest('[data-drawer-scroll]');
    if (!el) return undefined;
    if (initialScroll.current) el.scrollTop = initialScroll.current;
    let timer = 0;
    const onScroll = () => {
      if (timer) return;
      timer = window.setTimeout(() => {
        timer = 0;
        updateRef.current({ scrollTop: el.scrollTop });
      }, 400);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      el.removeEventListener('scroll', onScroll);
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  if (!appId) return null;

  if (phase === 'loading') {
    return <Box sx={{ p: 1 }}><LoadingSkeleton variant="card" /></Box>;
  }
  if (phase === 'error') {
    return <Box sx={{ p: 1 }}><ErrorAlert message={t('loadFailed')} onRetry={reload} /></Box>;
  }
  if (phase !== 'loaded' || !journey) return null;

  const selectStation = (n) => {
    const next = journey.stages.find((row) => row.n === n) || null;
    updateView({
      lessonId: null,
      stationKey: next?.key ?? null,
      stationN: next?.n ?? n ?? null,
    });
  };
  const openLesson = (id, owner) => updateView({
    lessonId: id,
    stationKey: owner?.key ?? null,
    stationN: owner?.n ?? null,
  });
  const closeLesson = (owner) => updateView({
    lessonId: null,
    stationKey: owner?.key ?? null,
    stationN: owner?.n ?? null,
  });

  if (showReader) {
    if (!lessonContext) {
      return (
        <Box sx={{ p: 1 }} data-testid="journey-tab" ref={rootRef}>
          <EmptyState
            title={t('reader.missing.title')}
            description={t('reader.missing.body')}
            actionLabel={t('reader.missing.action')}
            onAction={() => closeLesson(station)}
          />
        </Box>
      );
    }
    return (
      <Box sx={{ p: 1 }} data-testid="journey-tab" ref={rootRef}>
        <LessonReader
          compact
          station={lessonContext.station}
          lesson={lessonContext.lesson}
          glossary={journey.glossary}
          onGo={(target) => navigate(target)}
          onBackToStation={() => closeLesson(lessonContext.station)}
          prevLesson={lessonContext.prev}
          nextLesson={lessonContext.next}
          onNavigateLesson={(id) => openLesson(id, lessonContext.station)}
          onStationSummary={() => closeLesson(lessonContext.station)}
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 1 }} data-testid="journey-tab" ref={rootRef}>
      <JourneyArc
        compact
        journey={journey}
        listing={data}
        role={journey.path}
        onGo={(target) => navigate(target)}
      />
      <JourneyCelebration journey={journey} userKey={userKey} appId={appId} />
      <JourneyScenario
        compact
        journey={journey}
        station={station}
        role={journey.path}
        onOpenLesson={(id) => openLesson(id, station)}
      />
      <StationRail
        stations={journey.stages}
        selectedN={station?.n}
        onSelect={selectStation}
      />
      {station && station.lessons.length > 0 && (
        <>
          <Typography sx={{ ...FONT.sectionTitle, mt: 1, mb: 0.5 }} color="text.secondary">
            {t('sections.lessons')}
          </Typography>
          <LessonList
            lessons={station.lessons}
            glossary={journey.glossary}
            outcomeByLesson={outcomeByLesson}
            onOpen={(id) => openLesson(id, station)}
          />
        </>
      )}
    </Box>
  );
}

/**
 * Registers the Journey tab into the standard drawer for the current route's
 * app journey, and unregisters when the route leaves that app. Mount once in the
 * shell; renders nothing.
 */
export function JourneyInspectorTabRegistrar() {
  const location = useLocation();
  const appId = journeyContextFromPath(location.pathname)?.appId || null;

  useEffect(() => {
    if (!appId) return undefined;
    return registerInspectorTab({
      id: 'journey',
      label: (t) => t('tabs.journey'),
      icon: RouteIcon,
      order: 5,
      render: () => <JourneyTabBody />,
    });
  }, [appId]);

  return null;
}

export default JourneyInspectorTabRegistrar;
