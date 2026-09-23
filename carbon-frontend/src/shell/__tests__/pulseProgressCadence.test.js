// A6 — Progress reporting. Poll gap is a constant, not a hope.
import { describe, it, expect } from 'vitest';
import {
  A6_MAX_POLL_GAP_MS,
  LIVE_PLAN_POLL_MS,
  LIVE_CANVAS_POLL_MS,
  SUBAGENT_FAST_POLL_MS,
  SUBAGENT_SLOW_POLL_MS,
} from '../pulseProgressCadence';

describe('A6 progress cadence', () => {
  it('caps every live poll at the contract 2s gap', () => {
    expect(A6_MAX_POLL_GAP_MS).toBe(2000);
    expect(LIVE_PLAN_POLL_MS).toBeLessThanOrEqual(A6_MAX_POLL_GAP_MS);
    expect(LIVE_CANVAS_POLL_MS).toBeLessThanOrEqual(A6_MAX_POLL_GAP_MS);
    expect(SUBAGENT_FAST_POLL_MS).toBeLessThanOrEqual(A6_MAX_POLL_GAP_MS);
    expect(SUBAGENT_SLOW_POLL_MS).toBeLessThanOrEqual(A6_MAX_POLL_GAP_MS);
  });

  it('starts subagent polls faster than the gap so the first GET is not the 2s ceiling', () => {
    expect(SUBAGENT_FAST_POLL_MS).toBeLessThan(SUBAGENT_SLOW_POLL_MS);
    expect(SUBAGENT_FAST_POLL_MS).toBeLessThanOrEqual(1500);
  });
});
