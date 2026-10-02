/**
 * Journey model — a thin, domain-free adapter over the engine payload.
 *
 * The server (backend/guide) returns `listing.journey` for any pack: stages,
 * competencies, glossary and copy, already localized. Nothing here knows a
 * carbon term or a lesson id. This module only joins the engine payload with
 * the caller's lesson states and the pack's declared role split.
 *
 * There is NO lock state. A station is always reachable. A station is done
 * only when the pack's declared outcomes are proven by the engine.
 */

/** Map a UI track to the pack's declared role bucket. Unknown -> all lessons. */
export function pathForTrack(track) {
  if (track === 'L') return 'lead';
  if (track === 'D') return 'owner';
  return 'observer';
}

/** Default role track: the server's recommendation, else the first present. */
export function defaultTrack(listing) {
  const recommended = listing?.recommended_track;
  if (recommended === 'L' || recommended === 'D') return recommended;
  const present = new Set((listing?.lessons || []).map((lesson) => lesson.track));
  if (present.has('D')) return 'D';
  if (present.has('L')) return 'L';
  return 'C';
}

/** Open-period state from a reporting-period read: exactly one, none, or many. */
export function periodState(periods) {
  const list = Array.isArray(periods) ? periods : [];
  const open = list.filter((row) => row && row.status === 'open');
  if (open.length === 1) return { status: 'open', period: open[0], openCount: 1 };
  if (open.length > 1) return { status: 'many', period: null, openCount: open.length };
  return { status: 'none', period: null, openCount: 0 };
}

/** Closed periods stay readable and are never summed into the open period. */
export function closedPeriods(periods) {
  return (Array.isArray(periods) ? periods : []).filter(
    (row) => row && row.status && row.status !== 'open',
  );
}

/** Map a lesson state to a plain outcome status. No host jargon leaks out. */
function competencyStatus(lesson) {
  if (!lesson) return 'todo';
  if (lesson.state === 'done') return 'done';
  if (lesson.state === 'started') return 'inProgress';
  return 'todo';
}

/**
 * The lesson ids this pack puts on one role path for a stage.
 *
 * A wildcard caller (`allTracks`, from the engine's `all_tracks`) is a reader of
 * every track, so the union list wins over any single role split. Everyone else
 * gets their role's split, falling back to the union when the pack declares none.
 */
function stageLessonIds(stage, path, allTracks) {
  if (allTracks) return Array.isArray(stage.lessons) ? stage.lessons : [];
  const split = Array.isArray(stage[path]) ? stage[path] : [];
  if (split.length > 0) return split;
  return Array.isArray(stage.lessons) ? stage.lessons : [];
}

function buildStage(stage, index, path, lessonMap, compDefs, allTracks) {
  const ids = stageLessonIds(stage, path, allTracks);
  const lessons = ids.map((id) => lessonMap[id]).filter(Boolean);
  const onPath = new Set(lessons.map((lesson) => lesson.id));

  const competencies = (Array.isArray(stage.competencies) ? stage.competencies : [])
    .map((key) => {
      const def = compDefs[key] || { key, title: key, good: '' };
      const lesson = def.lesson ? lessonMap[def.lesson] : null;
      return { ...def, lessonId: def.lesson || '', lesson, status: competencyStatus(lesson) };
    })
    // An outcome is shown only when its lesson is actually available to this
    // caller. A stage with no work must show no outcomes, never a phantom one.
    .filter((row) => {
      if (row.lessonId) return allTracks ? Boolean(row.lesson) : onPath.has(row.lessonId);
      return onPath.size > 0;
    });

  const lessonsDone = lessons.filter((lesson) => lesson.state === 'done').length;
  const proven = competencies.filter((row) => row.status === 'done').length;
  const doneLessons = lessons.length > 0 && lessonsDone === lessons.length;
  const doneOutcomes = competencies.length > 0 && proven === competencies.length;
  const hasWork = lessons.length > 0 || competencies.length > 0;
  const done = !stage.pending && hasWork && (competencies.length > 0 ? doneOutcomes : doneLessons);

  return {
    n: stage.n != null ? stage.n : index + 1,
    key: stage.key || String(index + 1),
    title: stage.title || stage.key || '',
    what: stage.what || '',
    pending: Boolean(stage.pending),
    lessons,
    competencies,
    done,
    ownsNext: lessons.some((lesson) => lesson.is_next),
    lessonsDone,
    lessonsTotal: lessons.length,
    outcomesProven: proven,
    outcomesTotal: competencies.length,
    state: done ? 'done' : 'open',
  };
}

/** Derive the journey spine for one path from any pack's engine payload. */
export function deriveJourney(listing, track) {
  const lessons = Array.isArray(listing?.lessons) ? listing.lessons : [];
  const lessonMap = Object.fromEntries(lessons.map((lesson) => [lesson.id, lesson]));
  const payload = listing?.journey && typeof listing.journey === 'object' ? listing.journey : {};
  const compDefs = Object.fromEntries(
    (payload.competencies || []).map((row) => [row.key, row]),
  );
  const path = pathForTrack(track);
  // The engine marks a wildcard capability ("*") as all_tracks: it reads every
  // role split, so the station shows the union of lessons, not one role's slice.
  const allTracks = listing?.all_tracks === true;

  const stages = (payload.stages || []).map(
    (stage, index) => buildStage(stage, index, path, lessonMap, compDefs, allTracks),
  );

  const currentStage = stages.find((stage) => stage.ownsNext && !stage.done)
    || stages.find((stage) => !stage.done && (stage.lessons.length > 0 || stage.competencies.length > 0))
    || null;

  stages.forEach((stage) => {
    if (stage.done) stage.state = 'done';
    else if (currentStage && stage.n === currentStage.n) stage.state = 'current';
    else stage.state = 'open';
  });

  const competenciesProven = stages.reduce((sum, stage) => sum + stage.outcomesProven, 0);
  const competenciesTotal = stages.reduce((sum, stage) => sum + stage.outcomesTotal, 0);
  // "No work" is about what this caller may actually do, never about whether the
  // pack ships a stage spine. A wildcard caller always has work to read.
  const hasWork = allTracks
    || stages.some((stage) => stage.lessons.length > 0 || stage.competencies.length > 0);

  return {
    title: payload.title || '',
    intro: payload.intro || '',
    glossary: Array.isArray(payload.glossary) ? payload.glossary : [],
    stages,
    currentStage,
    stagesDone: stages.filter((stage) => stage.done).length,
    stagesTotal: stages.length,
    competenciesProven,
    competenciesTotal,
    allTracks,
    hasWork,
    path,
    track,
  };
}

/**
 * The one next action: the engine's next lesson, else the lesson the person
 * last touched, else the first unfinished unblocked lesson on this path.
 */
export function nextAction(listing, stages) {
  const lessons = Array.isArray(listing?.lessons) ? listing.lessons : [];
  const byId = Object.fromEntries(lessons.map((lesson) => [lesson.id, lesson]));
  const engineNext = lessons.find((lesson) => lesson.is_next);
  if (engineNext) return engineNext;
  const resumeId = listing?.resume?.id;
  if (resumeId && byId[resumeId]) return byId[resumeId];
  const onPath = new Set();
  stages.forEach((stage) => stage.lessons.forEach((lesson) => onPath.add(lesson.id)));
  return lessons.find((lesson) => onPath.has(lesson.id) && lesson.state !== 'done' && !lesson.blocker) || null;
}

/** Human label for a host route, so a button names the page it opens. */
const ROUTE_LABELS = {
  '/carbon/onboarding/intake': 'Campus intake',
};

export function routeLabel(route) {
  const key = String(route || '').replace(/\/+$/, '');
  if (ROUTE_LABELS[key]) return ROUTE_LABELS[key];
  const parts = String(route || '').split('/').filter(Boolean);
  const last = parts[parts.length - 1] || '';
  if (!last) return route || '';
  return last.replace(/[-_]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

/** Route view for the carbon onboarding landing: Journey, or the O1 checklist. */
export function onboardingViewFromSearch(search) {
  const params = new URLSearchParams(search || '');
  return params.get('view') === 'readiness' ? 'readiness' : 'journey';
}

/**
 * The app id whose journey belongs on the current route, or null. Domain apps
 * are discovered from the first path segment; /journey/<appId> wins outright.
 */
export function appIdFromPath(pathname) {
  const context = journeyContextFromPath(pathname);
  return context ? context.appId : null;
}

/**
 * The journey launcher context for the current route: the app id plus the open
 * lesson id when the reader is showing (/journey/<appId>/<lessonId>), else null.
 * Lesson ids are never derived for the /<appId> studio routes: the dock only
 * opens a reader pane from an explicit /journey/<appId>/<lessonId> URL.
 */
export function journeyContextFromPath(pathname) {
  const parts = String(pathname || '').split('/').filter(Boolean);
  if (parts[0] === 'journey' && parts[1]) {
    return { appId: parts[1], lessonId: parts[2] || null };
  }
  const KNOWN = ['carbon'];
  return KNOWN.includes(parts[0]) ? { appId: parts[0], lessonId: null } : null;
}

/**
 * Resolve the station a persisted view points at, preferring the STABLE station
 * key over the numeric index so a pack/track reorder can never land on the wrong
 * or a missing station. When both the stored key and index are gone (renamed or
 * removed station), fall back to the caller's default (usually the current
 * stage) and finally the first station — never null-crash or a blank panel.
 */
export function pickStation(stages, view, fallback = null) {
  const list = Array.isArray(stages) ? stages : [];
  const wantedKey = view?.stationKey;
  if (wantedKey != null) {
    const byKey = list.find((station) => station.key === wantedKey);
    if (byKey) return byKey;
  }
  const wantedN = view?.stationN;
  if (wantedN != null) {
    const byN = list.find((station) => station.n === wantedN);
    if (byN) return byN;
  }
  return fallback || list[0] || null;
}

/**
 * Resolve a lesson id to the station that owns it, the lesson row, its position
 * in the station and the neighbouring lessons. One lesson is visible at a time,
 * so Prev/Next walk the station's lesson list and stop at its summary.
 */
export function findLessonContext(journey, lessonId) {
  if (!journey || !lessonId) return null;
  const stations = Array.isArray(journey.stages) ? journey.stages : [];
  for (const station of stations) {
    const lessons = Array.isArray(station.lessons) ? station.lessons : [];
    const index = lessons.findIndex((lesson) => lesson.id === lessonId);
    if (index < 0) continue;
    return {
      station,
      lesson: lessons[index],
      index,
      total: lessons.length,
      prev: lessons[index - 1] || null,
      next: lessons[index + 1] || null,
    };
  }
  return null;
}
