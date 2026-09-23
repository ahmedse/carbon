import { describe, expect, it } from 'vitest';
import { dominantDir, dragPoint, finiteGeometry, scriptRuns } from '../components/graph/graphText';

describe('graph text', () => {
  it('keeps a Latin title left to right', () => {
    expect(dominantDir('Submitting')).toBe('ltr');
  });

  it('marks Arabic as right to left and isolates a date', () => {
    expect(dominantDir('تقديم الطلب')).toBe('rtl');
    const runs = scriptRuns('حتى 2026-07-01');
    expect(runs.map((r) => r.dir)).toEqual(['rtl', 'ltr']);
    expect(runs[1].text).toContain('2026-07-01');
  });

  it('does not slice a word into a fragment', () => {
    const runs = scriptRuns('Submitting');
    expect(runs.map((r) => r.text).join('')).toBe('Submitting');
  });
});

describe('graph drag', () => {
  it('follows the pointer when zoom is healthy', () => {
    expect(dragPoint(10, 40, 2)).toBe(30);
  });

  it('refuses a zero or non-finite zoom instead of emitting NaN', () => {
    expect(dragPoint(10, 40, 0)).toBe(50);
    expect(Number.isFinite(dragPoint(10, 40, Number.NaN))).toBe(true);
    expect(dragPoint(8, Number.NaN, 1)).toBe(8);
  });

  it('drops an override that would collapse the node', () => {
    const node = { id: 'a', x: 1, y: 2, w: 100, h: 40 };
    expect(finiteGeometry(node, { x: Number.NaN, y: 9 })).toEqual(node);
    expect(finiteGeometry(node, { x: 4, y: 5 }).x).toBe(4);
  });
});
