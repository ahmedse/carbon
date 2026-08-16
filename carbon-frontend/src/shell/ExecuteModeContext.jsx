// src/shell/ExecuteModeContext.jsx
// Shared Execute Mode toggle for the AI Workspace.
//
// When OFF (default), the AI may suggest actions but cannot apply them.
// When ON, the AI may propose data changes (create rules, fix data, run queries).
//
// The toggle is scoped to the current browser session (sessionStorage) so it
// resets to OFF when a new session starts, mirroring the safety-first posture
// of the data-trust platform.

import React, { useCallback, useMemo, useState } from 'react';
import { ExecuteModeContext } from './executeModeContext';

const STORAGE_KEY = 'carbon.executeMode';

function readStoredExecuteMode() {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function ExecuteModeProvider({ children }) {
  const [executeMode, setExecuteModeState] = useState(readStoredExecuteMode);

  const setExecuteMode = useCallback((value) => {
    const next = Boolean(value);
    setExecuteModeState(next);
    try {
      window.sessionStorage.setItem(STORAGE_KEY, next ? 'true' : 'false');
    } catch {
      // Session storage may be unavailable (e.g. private browsing) — ignore.
    }
  }, []);

  const value = useMemo(
    () => ({ executeMode, setExecuteMode }),
    [executeMode, setExecuteMode],
  );

  return (
    <ExecuteModeContext.Provider value={value}>{children}</ExecuteModeContext.Provider>
  );
}
