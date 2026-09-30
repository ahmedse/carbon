import { createContext, useContext } from 'react';

/** Set when Moodle (or another host) is showing the real Pulse pane. */
export const PulseHostContext = createContext(null);

export function usePulseHost() {
  return useContext(PulseHostContext);
}

/** Course id from the signed page block. Empty when no course is open. */
export function moodleCourseId(pageContext) {
  const match = String(pageContext || '').match(/^Open course .+ id=(\d+)/m);
  return match ? match[1] : '';
}

export function moodleThreadKey(courseId) {
  return courseId ? `pulse-moodle-thread:${courseId}` : '';
}

/** Activity id from the signed page block. Empty on the course home. */
export function moodleActivityId(pageContext) {
  const match = String(pageContext || '').match(/^Open activity .+ cmid=(\d+)/m);
  return match ? match[1] : '';
}

/**
 * The Ask thread for this course. An activity page uses the same id as the
 * course home. Empty when nothing was stored, or the stored id is not in the
 * loaded list — a missing id stays missing.
 */
export function courseThreadId(pageContext, visibleIds, read) {
  const key = moodleThreadKey(moodleCourseId(pageContext));
  if (!key || typeof read !== 'function') return '';
  let stored = '';
  try {
    stored = String(read(key) || '');
  } catch {
    return '';
  }
  if (!stored || !(visibleIds || []).includes(stored)) return '';
  return stored;
}
