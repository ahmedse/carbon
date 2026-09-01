// src/__tests__/useDraftPersistence.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDraftPersistence } from '../hooks/useDraftPersistence';

const KEY = 'carbon.ai.draft.conv-1';

describe('useDraftPersistence', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it('restores an existing draft on mount', () => {
    localStorage.setItem(KEY, 'half-typed prompt');
    const { result } = renderHook(() => useDraftPersistence('conv-1'));
    expect(result.current.draft).toBe('half-typed prompt');
  });

  it('persists and restores a round-trip', () => {
    const { result } = renderHook(() => useDraftPersistence('conv-1'));
    act(() => {
      result.current.persist('hello world');
    });
    expect(localStorage.getItem(KEY)).toBeNull(); // still debounced
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(localStorage.getItem(KEY)).toBe('hello world');

    let restored;
    act(() => {
      restored = result.current.restore();
    });
    expect(restored).toBe('hello world');
    expect(result.current.draft).toBe('hello world');
  });

  it('debounces and coalesces rapid writes', () => {
    const { result } = renderHook(() => useDraftPersistence('conv-1'));
    act(() => {
      result.current.persist('a');
      result.current.persist('ab');
      result.current.persist('abc');
    });
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(localStorage.getItem(KEY)).toBeNull();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(localStorage.getItem(KEY)).toBe('abc');
  });

  it('clear removes the stored draft', () => {
    localStorage.setItem(KEY, 'stale');
    const { result } = renderHook(() => useDraftPersistence('conv-1'));
    expect(result.current.draft).toBe('stale');
    act(() => {
      result.current.clear();
    });
    expect(localStorage.getItem(KEY)).toBeNull();
    expect(result.current.draft).toBe('');
  });

  it('falls back to a stable default key when no key is given', () => {
    const { result } = renderHook(() => useDraftPersistence());
    act(() => {
      result.current.persist('untitled');
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(localStorage.getItem('carbon.ai.draft.default')).toBe('untitled');
  });
});
