// Persist the active stem context for Teach console navigation (ADR-0042).
// Set when opening a stem master-detail; cleared when returning to the stems list.

const STORAGE_KEY = 'teach.stemContext';

export function setTeachStemContext(ctx) {
  if (!ctx?.assignmentId) {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    return;
  }
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        assignmentId: String(ctx.assignmentId),
        title: ctx.title || '',
        courseCode: ctx.courseCode || '',
        mode: ctx.mode || '',
        status: ctx.status || '',
        setAt: Date.now(),
      }),
    );
  } catch {
    /* ignore */
  }
}

export function getTeachStemContext() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearTeachStemContext() {
  setTeachStemContext(null);
}
