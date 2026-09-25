// Shared Pulse footer prefs (Chat + Tasks). One provider per workspace so
// font / Think / model actually change the open surface, not just localStorage.

import React, { createContext, useCallback, useContext, useState } from 'react';
import { AI_MODEL_STORAGE_KEY } from './AIModelSelect';

export const CONTENT_ZOOM_KEY = 'ai.contentZoom';
export const DENSE_THINKING_KEY = 'pulse.denseThinking';

export function readContentZoom() {
  try {
    const saved = Number(window.localStorage.getItem(CONTENT_ZOOM_KEY));
    return saved >= 0.8 && saved <= 1.4 ? saved : 1;
  } catch {
    return 1;
  }
}

export function readDenseThinking() {
  try {
    return localStorage.getItem(DENSE_THINKING_KEY) === '1';
  } catch {
    return false;
  }
}

export function readSelectedModel() {
  try {
    return localStorage.getItem(AI_MODEL_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

function safeSet(key, value) {
  try {
    if (value == null || value === '') localStorage.removeItem(key);
    else localStorage.setItem(key, String(value));
  } catch {
    /* ignore quota / private mode */
  }
}

function usePulsePrefsState() {
  const [contentZoom, setZoomState] = useState(readContentZoom);
  const [denseThinking, setThinkState] = useState(readDenseThinking);
  const [selectedModel, setModelState] = useState(readSelectedModel);

  const setContentZoom = useCallback((next) => {
    setZoomState((prev) => {
      const raw = typeof next === 'function' ? next(prev) : next;
      const clamped = Math.min(1.4, Math.max(0.8, Number(raw) || 1));
      safeSet(CONTENT_ZOOM_KEY, String(clamped));
      return clamped;
    });
  }, []);

  const setDenseThinking = useCallback((on) => {
    const value = Boolean(on);
    setThinkState(value);
    safeSet(DENSE_THINKING_KEY, value ? '1' : '0');
  }, []);

  const setSelectedModel = useCallback((id) => {
    const value = id ? String(id) : '';
    setModelState(value);
    safeSet(AI_MODEL_STORAGE_KEY, value || null);
  }, []);

  const adjustZoom = useCallback((delta) => {
    setContentZoom((prev) => Math.round((prev + delta) * 10) / 10);
  }, [setContentZoom]);

  const resetZoom = useCallback(() => {
    setContentZoom(1);
  }, [setContentZoom]);

  return {
    contentZoom,
    setContentZoom,
    adjustZoom,
    resetZoom,
    denseThinking,
    setDenseThinking,
    selectedModel,
    setSelectedModel,
  };
}

const PulsePrefsContext = createContext(null);

export function PulsePrefsProvider({ children }) {
  const value = usePulsePrefsState();
  return (
    <PulsePrefsContext.Provider value={value}>
      {children}
    </PulsePrefsContext.Provider>
  );
}

export function usePulsePrefs() {
  const ctx = useContext(PulsePrefsContext);
  const local = usePulsePrefsState();
  return ctx || local;
}
