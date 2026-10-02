// src/components/journey/useJourneyRole.js
// First-run role personalization for the Journey. The chosen seat (Lead / Owner
// / Observer) is a VIEW preference: it picks the default path and the story
// tone. It never grants access — the server already decided what the caller may
// take. Stored under its own key, deliberately NOT the shared station/lesson
// view store (inspector/useDrawerJourneyView), so the two never collide.
import { useCallback, useEffect, useState } from 'react';

const TRACKS = new Set(['L', 'D', 'C']);
const keyFor = (userKey, appId) => `carbon-journey-role:${userKey || 'anon'}:${appId || ''}`;

/** Read the stored track, or null when this caller has never chosen one. */
export function readJourneyRole(userKey, appId) {
  try {
    const raw = window.localStorage.getItem(keyFor(userKey, appId));
    return TRACKS.has(raw) ? raw : null;
  } catch {
    return null;
  }
}

/** [track | null, setTrack]. setTrack(null) clears the choice. */
export default function useJourneyRole(userKey, appId) {
  const [role, setRoleState] = useState(() => readJourneyRole(userKey, appId));

  useEffect(() => {
    setRoleState(readJourneyRole(userKey, appId));
  }, [userKey, appId]);

  const setRole = useCallback((next) => {
    const value = TRACKS.has(next) ? next : null;
    setRoleState(value);
    try {
      if (value) window.localStorage.setItem(keyFor(userKey, appId), value);
      else window.localStorage.removeItem(keyFor(userKey, appId));
    } catch {
      // A storage failure only loses the preference; the view still changes.
    }
  }, [userKey, appId]);

  return [role, setRole];
}
