// src/components/journey/useJourneyCelebration.js
// A restrained, honest success moment: when a station becomes done between two
// visits, show one short inline note. It is derived from the engine's real
// station state, persisted under its own key, and never fires on a first visit
// (that would celebrate work the person may have finished long ago). Session
// storage keeps it per tab so it cannot nag across days.
import { useCallback, useEffect, useState } from 'react';

const keyFor = (userKey, appId) => `carbon-journey-seen:${userKey || 'anon'}:${appId || ''}`;

function readSeen(userKey, appId) {
  try {
    const raw = window.sessionStorage.getItem(keyFor(userKey, appId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function writeSeen(userKey, appId, keys) {
  try {
    window.sessionStorage.setItem(keyFor(userKey, appId), JSON.stringify(keys));
  } catch {
    // Losing the record only means no celebration next time — never a fake one.
  }
}

/**
 * { justDone, dismiss } — `justDone` is the first station that turned done since
 * the last visit, or null. The very first visit on a device only records a
 * baseline, so nothing is celebrated that the person did not just finish.
 */
export default function useJourneyCelebration(journey, userKey, appId) {
  const [justDone, setJustDone] = useState(null);

  useEffect(() => {
    if (!journey || !Array.isArray(journey.stages)) return;
    const doneNow = journey.stages.filter((station) => station.done).map((station) => station.key);
    const seen = readSeen(userKey, appId);
    if (seen === null) {
      writeSeen(userKey, appId, doneNow);
      return;
    }
    const known = new Set(seen);
    const fresh = journey.stages.find((station) => station.done && !known.has(station.key));
    writeSeen(userKey, appId, doneNow);
    if (fresh) setJustDone(fresh);
  }, [journey, userKey, appId]);

  const dismiss = useCallback(() => setJustDone(null), []);
  return { justDone, dismiss };
}
