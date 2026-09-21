import { describe, it, expect } from 'vitest';
import { formatDistanceToNow, formatDisplayDate } from './dateUtils';

describe('dateUtils locale', () => {
  it('formats relative time in English by default', () => {
    const d = new Date(Date.now() - 3_600_000 * 2);
    expect(formatDistanceToNow(d, 'en')).toMatch(/2h ago/);
  });

  it('formats relative time in Arabic when lang=ar', () => {
    const d = new Date(Date.now() - 60_000 * 5);
    expect(formatDistanceToNow(d, 'ar')).toMatch(/منذ 5 د/);
  });

  it('formats display date for ar locale', () => {
    const d = new Date('2026-03-15T12:00:00Z');
    const ar = formatDisplayDate(d, { lang: 'ar' });
    const en = formatDisplayDate(d, { lang: 'en' });
    expect(ar.length).toBeGreaterThan(0);
    expect(en.length).toBeGreaterThan(0);
  });
});
