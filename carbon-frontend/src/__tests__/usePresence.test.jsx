// src/__tests__/usePresence.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { usePresence } from '../hooks/usePresence';
import { getLastBeatAt, useInsightStream } from '../hooks/useInsightStream';
import { apiFetchStream } from '../api/api';

vi.mock('../hooks/useInsightStream', () => ({
  getLastBeatAt: vi.fn(),
  useInsightStream: vi.fn(),
}));

vi.mock('../api/api', () => ({
  apiFetchStream: vi.fn(),
}));

describe('usePresence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
  });

  afterEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
  });

  it('reports online for a fresh lastBeatAt', () => {
    getLastBeatAt.mockReturnValue(Date.now());
    const { result } = renderHook(() => usePresence());
    expect(result.current.online).toBe(true);
    expect(result.current.stale).toBe(false);
  });

  it('reports stale for an old lastBeatAt', () => {
    getLastBeatAt.mockReturnValue(Date.now() - 60000);
    const { result } = renderHook(() => usePresence());
    expect(result.current.online).toBe(false);
    expect(result.current.stale).toBe(true);
  });

  it('reports offline when navigator.onLine is false', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
    getLastBeatAt.mockReturnValue(Date.now());
    const { result } = renderHook(() => usePresence());
    expect(result.current.online).toBe(false);
    expect(result.current.stale).toBe(false);
  });

  it('reads the shared store and never opens its own SSE', () => {
    getLastBeatAt.mockReturnValue(Date.now());
    renderHook(() => usePresence());
    expect(getLastBeatAt).toHaveBeenCalled();
    expect(useInsightStream).not.toHaveBeenCalled();
    expect(apiFetchStream).not.toHaveBeenCalled();
  });
});
