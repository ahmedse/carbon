/**
 * Pure momentum helpers for the Journey surfaces.
 *
 * Everything here is derived from the engine's own station/outcome state. A
 * station is `done` only when the pack's declared outcome is proven by the host
 * probe, and an outcome is proven only when its lesson is `done`. Nothing adds
 * points for clicks, and an absent signal stays absent — no invented progress.
 */

/** Overall arc: completed stations, proven outcomes, and whether work started. */
export function overallProgress(journey) {
  const stations = Array.isArray(journey?.stages) ? journey.stages : [];
  const total = stations.length;
  const done = stations.filter((station) => station.done).length;
  const outcomesTotal = stations.reduce((sum, station) => sum + (station.outcomesTotal || 0), 0);
  const outcomesProven = stations.reduce((sum, station) => sum + (station.outcomesProven || 0), 0);
  return {
    done,
    total,
    pct: total > 0 ? Math.round((done / total) * 100) : 0,
    outcomesProven,
    outcomesTotal,
    started: done > 0 || outcomesProven > 0,
    complete: total > 0 && done === total,
  };
}

/** Consecutive complete stations from the start — momentum, never points. */
export function momentum(journey) {
  const stations = Array.isArray(journey?.stages) ? journey.stages : [];
  let streak = 0;
  for (const station of stations) {
    if (!station.done) break;
    streak += 1;
  }
  return streak;
}

/** The station the person is on: the engine's current stage, else the first open. */
export function hereStation(journey) {
  const stations = Array.isArray(journey?.stages) ? journey.stages : [];
  return journey?.currentStage
    || stations.find((station) => station.state === 'current')
    || stations.find((station) => !station.done)
    || stations[0]
    || null;
}

/** The one next lesson the engine offers, or null when nothing is next. */
export function nextLesson(listing) {
  const lessons = Array.isArray(listing?.lessons) ? listing.lessons : [];
  const engineNext = lessons.find((lesson) => lesson.is_next);
  if (engineNext) return engineNext;
  const resumeId = listing?.resume?.id;
  if (resumeId) return lessons.find((lesson) => lesson.id === resumeId) || null;
  return null;
}

/** The station that owns a lesson id, or null. */
export function stationForLesson(journey, lessonId) {
  const stations = Array.isArray(journey?.stages) ? journey.stages : [];
  return stations.find(
    (station) => (station.lessons || []).some((lesson) => lesson.id === lessonId),
  ) || null;
}

/** One station's progress over its checkable outcomes, falling back to lessons. */
export function stationProgress(station) {
  const total = station?.outcomesTotal > 0 ? station.outcomesTotal : (station?.lessonsTotal || 0);
  const done = station?.outcomesTotal > 0 ? station.outcomesProven : (station?.lessonsDone || 0);
  return { done, total, pct: total > 0 ? Math.round((done / total) * 100) : 0 };
}
