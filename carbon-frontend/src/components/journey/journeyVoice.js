/**
 * Journey voice — pure, honest helpers for the storytelling surfaces.
 *
 * Everything here is derived from the engine payload already on screen: the
 * station spine, each lesson's real state and `minutes`, and each outcome's
 * proven status. Nothing invents a scene, a score or a number. A scene exists
 * only when the pack declares the station; a mission exists only when the pack
 * puts a lesson on the caller's path.
 */

/** The station's position on the spine and the total number of stations. */
export function sceneOf(journey, station) {
  const stages = Array.isArray(journey?.stages) ? journey.stages : [];
  const index = stages.findIndex((row) => row.n === station?.n);
  return {
    n: index >= 0 ? index + 1 : 1,
    total: stages.length,
  };
}

/**
 * The station's mission: the one lesson the engine marks next, else the first
 * lesson still open on the station, else the first lesson at all. Never a
 * lesson that is not on this caller's path.
 */
export function missionLesson(station) {
  const lessons = Array.isArray(station?.lessons) ? station.lessons : [];
  if (lessons.length === 0) return null;
  return lessons.find((lesson) => lesson.is_next)
    || lessons.find((lesson) => lesson.state !== 'done')
    || lessons[0];
}

/** The lesson's opening real action: its first step, when the pack declares one. */
export function missionFirstMove(lesson) {
  const steps = Array.isArray(lesson?.steps) ? lesson.steps : [];
  const first = steps[0];
  if (!first) return null;
  return { title: first.title || '', action: first.do || '', route: first.route || '' };
}

/** Real study time for a set of lessons, summed from the engine's own minutes. */
export function lessonsMinutes(lessons) {
  return (Array.isArray(lessons) ? lessons : [])
    .reduce((sum, lesson) => sum + (Number(lesson.minutes) || 0), 0);
}

/** The outcomes the engine actually proved on a station — never a click. */
export function provenOutcomes(station) {
  return (station?.competencies || []).filter((row) => row.status === 'done');
}

/** Stations the engine marks done, by their stable key. */
export function doneStationKeys(journey) {
  return (Array.isArray(journey?.stages) ? journey.stages : [])
    .filter((station) => station.done)
    .map((station) => station.key);
}

/**
 * A spaced-review candidate: the most recent lesson the caller has genuinely
 * finished on an EARLIER station, and only when the pack grades it by a choice
 * (`completion === 'answer'`) — a host-graded lesson has no question to revisit.
 * Returns null when no earlier finished lesson maps to a real question.
 */
export function recallLesson(journey, station) {
  const stages = Array.isArray(journey?.stages) ? journey.stages : [];
  const currentN = station?.n;
  const pool = [];
  stages.forEach((row) => {
    if (currentN != null && row.n >= currentN) return;
    (row.lessons || []).forEach((lesson) => {
      if (lesson.state === 'done' && lesson.completion === 'answer') pool.push(lesson);
    });
  });
  return pool.length > 0 ? pool[pool.length - 1] : null;
}
