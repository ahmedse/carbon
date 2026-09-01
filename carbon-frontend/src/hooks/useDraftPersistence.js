// src/hooks/useDraftPersistence.js
//
// Best-effort localStorage persistence for in-progress composer drafts. Writes
// are debounced (trailing, flushed on unmount) so typing never thrashes
// storage. All storage access is guarded — privacy mode / quota errors degrade
// to an empty draft rather than throwing.

import { useCallback, useEffect, useRef, useState } from 'react';

const NAMESPACE = 'carbon.ai.draft';
const DEBOUNCE_MS = 300;

function storageKey(key) {
  return `${NAMESPACE}.${key || 'default'}`;
}

function safeRead(key) {
  try {
    return window.localStorage.getItem(key) ?? '';
  } catch {
    return '';
  }
}

function safeWrite(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Privacy mode / quota exceeded — persistence is best-effort.
  }
}

function safeRemove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Best-effort only.
  }
}

/**
 * @param {string} [key] Storage sub-key; defaults to `'default'`.
 * @returns {{ draft: string, restore: () => string, persist: (value: unknown) => void, clear: () => void }}
 */
export function useDraftPersistence(key) {
  const resolvedKey = storageKey(key);
  const [draft, setDraft] = useState(() => safeRead(resolvedKey));
  const timerRef = useRef(null);
  const latestRef = useRef(draft);

  const persist = useCallback(
    (value) => {
      const next = value == null ? '' : String(value);
      latestRef.current = next;
      setDraft(next);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        if (latestRef.current) safeWrite(resolvedKey, latestRef.current);
        else safeRemove(resolvedKey);
      }, DEBOUNCE_MS);
    },
    [resolvedKey]
  );

  const restore = useCallback(() => {
    const value = safeRead(resolvedKey);
    setDraft(value);
    return value;
  }, [resolvedKey]);

  const clear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    latestRef.current = '';
    safeRemove(resolvedKey);
    setDraft('');
  }, [resolvedKey]);

  // Flush any pending debounced write on unmount so no keystroke is lost.
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (latestRef.current) safeWrite(resolvedKey, latestRef.current);
    };
  }, [resolvedKey]);

  return { draft, restore, persist, clear };
}

export default useDraftPersistence;
