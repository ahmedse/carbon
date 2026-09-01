// src/hooks/usePresence.js
//
// Passive presence hook. It reads the heartbeat timestamp from the EXISTING
// insight SSE store (no new stream, no polling, no network). Online/offline is
// derived from `navigator.onLine` plus a staleness threshold — a heartbeat
// older than 45s means the stream has gone quiet.

import { useEffect, useState } from 'react';
import { getLastBeatAt } from './useInsightStream';

const STALE_AFTER_MS = 45000;
const PRESENCE_CHECK_INTERVAL_MS = 5000;

function computePresence(lastBeatAt) {
  const navigatorOnline =
    typeof navigator === 'undefined' || navigator.onLine !== false;
  const age = lastBeatAt == null ? Number.POSITIVE_INFINITY : Date.now() - lastBeatAt;

  return {
    lastBeatAt,
    online: navigatorOnline && age < STALE_AFTER_MS,
    stale: navigatorOnline && lastBeatAt != null && age >= STALE_AFTER_MS,
  };
}

/**
 * @returns {{ online: boolean, stale: boolean, lastBeatAt: number | null }}
 */
export function usePresence() {
  const [presence, setPresence] = useState(() =>
    computePresence(getLastBeatAt())
  );

  useEffect(() => {
    const recompute = () => setPresence(computePresence(getLastBeatAt()));

    window.addEventListener('online', recompute);
    window.addEventListener('offline', recompute);
    // Recompute-only timer: re-reads the shared store to refresh staleness.
    // No network calls happen here.
    const interval = setInterval(recompute, PRESENCE_CHECK_INTERVAL_MS);

    return () => {
      window.removeEventListener('online', recompute);
      window.removeEventListener('offline', recompute);
      clearInterval(interval);
    };
  }, []);

  return presence;
}

export default usePresence;
