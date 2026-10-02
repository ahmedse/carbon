import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../../auth/AuthContext';
import useGuide from '../../hooks/useGuide';
import { fetchReportingPeriods } from '../../api/emissions-extended';
import { fetchGuideLesson } from '../../api/guide';
import {
  closedPeriods,
  defaultTrack,
  deriveJourney,
  nextAction,
  periodState,
} from './journeyStages';

/**
 * Journey state: wraps useGuide(appId) and derives the seven-stage spine, the
 * role path, the open-period chip and the one next action. Reads only; the
 * guide's own progress POST is the sole write, and it stays in useGuide.
 */
export default function useJourney(appId, track) {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('ar') ? 'ar' : 'en';
  const guide = useGuide(appId);

  const [periods, setPeriods] = useState([]);
  const [live, setLive] = useState(null);

  const reloadPeriods = useCallback(async () => {
    try {
      const body = await fetchReportingPeriods(token);
      const list = Array.isArray(body) ? body : (body?.results || []);
      setPeriods(list);
    } catch {
      // A period read that fails must never fake a period; the chip reads None.
      setPeriods([]);
    }
  }, [token]);

  useEffect(() => {
    reloadPeriods();
  }, [reloadPeriods]);

  const effectiveTrack = track || defaultTrack(guide.data);

  const journey = useMemo(
    () => (guide.phase === 'loaded' ? deriveJourney(guide.data, effectiveTrack) : null),
    [guide.phase, guide.data, effectiveTrack],
  );

  const period = useMemo(() => periodState(periods), [periods]);
  const closed = useMemo(() => closedPeriods(periods), [periods]);
  const next = useMemo(
    () => (journey ? nextAction(guide.data, journey.stages) : null),
    [journey, guide.data],
  );
  const activeLessonId = next?.id || guide.data?.resume?.id || guide.data?.next_id || null;

  useEffect(() => {
    let cancelled = false;
    if (!activeLessonId) {
      setLive(null);
      return () => { cancelled = true; };
    }
    fetchGuideLesson(appId, activeLessonId, { lang, token })
      .then((body) => { if (!cancelled) setLive(body?.live || null); })
      .catch(() => { if (!cancelled) setLive(null); });
    return () => { cancelled = true; };
  }, [appId, activeLessonId, lang, token]);

  const reload = useCallback(async () => {
    await Promise.all([guide.reload(), reloadPeriods()]);
  }, [guide, reloadPeriods]);

  return {
    phase: guide.phase,
    error: guide.error,
    data: guide.data,
    lang,
    token,
    journey,
    period,
    closed,
    live,
    next,
    activeLessonId,
    reload,
    send: guide.send,
    effectiveTrack,
  };
}
