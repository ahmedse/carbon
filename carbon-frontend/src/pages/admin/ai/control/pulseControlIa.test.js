// Unit: pulseControlIa — ADR-0036 redirect matrix integrity
import { describe, expect, it } from 'vitest';
import {
  CONTROL_DESTINATIONS,
  LEGACY_REDIRECTS,
  legacyRedirectTo,
} from './pulseControlIa';

describe('pulseControlIa', () => {
  it('exposes exactly six control destinations', () => {
    expect(CONTROL_DESTINATIONS).toHaveLength(6);
    expect(CONTROL_DESTINATIONS.map((d) => d.id)).toEqual([
      'command',
      'domain',
      'assets',
      'evidence',
      'learning',
      'platform',
    ]);
  });

  it('maps every legacy path to a known destination + tab', () => {
    const destPaths = new Set(CONTROL_DESTINATIONS.map((d) => d.path));
    Object.entries(LEGACY_REDIRECTS).forEach(([from, entry]) => {
      expect(from.startsWith('/admin/ai/')).toBe(true);
      expect(destPaths.has(entry.path)).toBe(true);
      expect(entry.tab).toBeTruthy();
      expect(legacyRedirectTo(entry)).toBe(`${entry.path}?tab=${entry.tab}`);
    });
  });

  it('does not redirect engage surfaces', () => {
    expect(LEGACY_REDIRECTS['/admin/ai/workspace']).toBeUndefined();
    expect(LEGACY_REDIRECTS['/admin/ai/conversations']).toBeUndefined();
  });
});
