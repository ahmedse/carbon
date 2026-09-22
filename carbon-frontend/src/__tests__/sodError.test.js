// Host SoD error helpers (ADR-0045 / NPS-1).
import { describe, it, expect } from 'vitest';
import { isSodError, sodErrorCode } from '../apps/people/utils';

describe('sodError helpers', () => {
  it('reads code from apiFetch err.data', () => {
    const err = Object.assign(new Error('SoD refused'), {
      data: { detail: 'SoD refused: preparer cannot commit', code: 'sod_same_actor' },
      status: 403,
    });
    expect(sodErrorCode(err)).toBe('sod_same_actor');
    expect(isSodError(err)).toBe(true);
  });

  it('ignores non-SoD errors', () => {
    const err = Object.assign(new Error('conflict'), {
      data: { detail: 'wrong status' },
      status: 409,
    });
    expect(sodErrorCode(err)).toBeNull();
    expect(isSodError(err)).toBe(false);
  });
});
