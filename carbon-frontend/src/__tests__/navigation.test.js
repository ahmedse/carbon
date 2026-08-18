// src/__tests__/navigation.test.js
// Sprint "fly to rule detail" — safe internal-route validation used to gate
// AI-driven navigate actions before they render as Links.
import { describe, it, expect } from 'vitest';
import { isSafeInternalRoute } from '../utils/navigation';

describe('isSafeInternalRoute', () => {
  it('accepts plain in-app paths', () => {
    expect(isSafeInternalRoute('/dq/rules/abc-123')).toBe(true);
    expect(isSafeInternalRoute('/dq')).toBe(true);
    expect(isSafeInternalRoute('/dq/rules/42/results')).toBe(true);
    expect(isSafeInternalRoute('/dq/rules/abc?tab=results')).toBe(true);
  });

  it('rejects non-strings and empty values', () => {
    expect(isSafeInternalRoute(null)).toBe(false);
    expect(isSafeInternalRoute(undefined)).toBe(false);
    expect(isSafeInternalRoute('')).toBe(false);
    expect(isSafeInternalRoute(42)).toBe(false);
    expect(isSafeInternalRoute({})).toBe(false);
  });

  it('rejects external/absolute URLs', () => {
    expect(isSafeInternalRoute('https://evil.example')).toBe(false);
    expect(isSafeInternalRoute('http://evil.example')).toBe(false);
    expect(isSafeInternalRoute('javascript:alert(1)')).toBe(false);
    expect(isSafeInternalRoute('//evil.example')).toBe(false);
  });

  it('rejects traversal and backslashes', () => {
    expect(isSafeInternalRoute('/dq/../admin')).toBe(false);
    expect(isSafeInternalRoute('/dq/rules/..')).toBe(false);
    expect(isSafeInternalRoute('/dq\\rules')).toBe(false);
    expect(isSafeInternalRoute('/dq/rules/..\\..\\etc')).toBe(false);
  });

  it('rejects control characters and spaces', () => {
    expect(isSafeInternalRoute('/dq/rules/\n')).toBe(false);
    expect(isSafeInternalRoute('/dq/rule name')).toBe(false);
  });
});
