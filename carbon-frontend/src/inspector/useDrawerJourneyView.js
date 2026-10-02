// src/inspector/useDrawerJourneyView.js
// Persisted view state for the Journey surface: which station and lesson the
// user last selected, plus its last scroll offset. It is the ONE store shared by
// the main Journey page (JourneyPage) and the drawer Journey tab
// (journeyTabs.JourneyTabBody) so both surfaces read and write the same value
// and cannot drift apart.
//
// This is VIEW STATE, not a data store. It reuses the drawer's existing
// localStorage convention — the same `carbon-*` key family as `carbon-notes-open`
// / `carbon-notes-tab` — and is scoped per user and per app so it survives reload
// exactly like the drawer's open/pin/tab preferences. There is no parallel
// context, backend, or notes store.
//
// Storage shape (`carbon-journey-view:<user>:<app>`):
//   { stationKey: string|null, stationN: number|null, lessonId: string|null, scrollTop: number }
// `stationKey` is the stable station id (stage.key), so a pack/track reorder can
// never point at the wrong station. `stationN` is kept for backward compatibility
// with views written before stable ids existed, and old values that only carry
// `stationN` still resolve. This is one key, not a second store.

import { useCallback, useEffect, useRef, useState } from 'react';

const PREFIX = 'carbon-journey-view';

const keyFor = (userId, appId) =>
  `${PREFIX}:${userId || 'anonymous'}:${appId || 'none'}`;

const userOf = (key) => key.split(':')[1] || 'anonymous';
const appOf = (key) => key.split(':')[2] || 'none';

function readKey(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

// Session-wide pub/sub over the ONE key, so a selection made on the main page
// lands in the drawer (and the reverse) without waiting for a storage event
// (which never fires in the same tab) and without a second store.
const listeners = new Map();

function emit(key, value) {
  const set = listeners.get(key);
  if (!set) return;
  set.forEach((listener) => listener(value));
}

function writeKey(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore storage errors */
  }
  emit(key, value);
}

function subscribe(key, listener) {
  let set = listeners.get(key);
  if (!set) {
    set = new Set();
    listeners.set(key, set);
  }
  set.add(listener);
  return () => {
    set.delete(listener);
    if (set.size === 0) listeners.delete(key);
  };
}

/**
 * @returns {[object, (patch: object) => void]} the persisted view state
 *   (`{ stationKey?, stationN?, lessonId?, scrollTop? }`) and a patch updater.
 *   Every mounted hook for the same user + app sees the same value.
 */
export function useDrawerJourneyView(userId, appId) {
  const key = keyFor(userId, appId);
  const keyRef = useRef(key);
  const [view, setView] = useState(() => readKey(key));

  useEffect(() => {
    const prevKey = keyRef.current;
    keyRef.current = key;
    const stored = readKey(key);

    // The auth user resolves a frame after mount, so an early selection can be
    // written under the `anonymous` fallback. When the real user id arrives,
    // migrate that value to the scoped key (same app only) instead of letting
    // the empty scoped key overwrite it in memory.
    if (
      Object.keys(stored).length === 0
      && prevKey !== key
      && appOf(prevKey) === appOf(key)
      && userOf(prevKey) === 'anonymous'
      && userOf(key) !== 'anonymous'
    ) {
      const inherited = readKey(prevKey);
      if (Object.keys(inherited).length > 0) {
        writeKey(key, inherited);
        try { localStorage.removeItem(prevKey); } catch { /* ignore */ }
        setView(inherited);
        return subscribe(key, setView);
      }
    }

    setView(stored);
    return subscribe(key, setView);
  }, [key]);

  const update = useCallback((patch) => {
    const activeKey = keyRef.current;
    const prev = readKey(activeKey);
    writeKey(activeKey, { ...prev, ...patch });
  }, []);

  return [view, update];
}

export default useDrawerJourneyView;
