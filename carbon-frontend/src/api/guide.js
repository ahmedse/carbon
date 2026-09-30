// Guide API (pack-driven microlearning). One surface for every domain app:
// GET guide/<app>/, GET guide/<app>/lessons/<id>/, POST .../progress/.
// The server picks the lessons from the caller's capabilities and scope.
import { apiFetch } from './api';

const root = (appId) => `guide/${encodeURIComponent(appId)}/`;
const withLang = (path, lang) => (lang ? `${path}?lang=${encodeURIComponent(lang)}` : path);

/** Tracks, lessons, blockers and next lesson. Writes nothing. */
export async function fetchGuide(appId, { lang, token } = {}) {
  return apiFetch(withLang(root(appId), lang), { token });
}

/** One lesson: live object, question and text. Writes nothing. */
export async function fetchGuideLesson(appId, lessonId, { lang, token } = {}) {
  return apiFetch(withLang(`${root(appId)}lessons/${encodeURIComponent(lessonId)}/`, lang), { token });
}

/** event: started | answered (with choice) | check | snooze. Writes GuideProgress only. */
export async function postGuideEvent(appId, lessonId, body, token) {
  return apiFetch(`${root(appId)}lessons/${encodeURIComponent(lessonId)}/progress/`, {
    method: 'POST',
    body,
    token,
  });
}
