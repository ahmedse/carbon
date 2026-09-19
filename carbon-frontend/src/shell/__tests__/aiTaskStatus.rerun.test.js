// src/shell/__tests__/aiTaskStatus.rerun.test.js
import { describe, it, expect } from 'vitest';
import {
  isRerunnableStatus,
  isSettledPhase,
  RERUNNABLE_STATUSES,
} from '../aiTaskStatus';

describe('isRerunnableStatus / isSettledPhase', () => {
  it('includes completed_with_gaps alongside completed/failed/cancelled', () => {
    expect(RERUNNABLE_STATUSES).toContain('completed_with_gaps');
    expect(isRerunnableStatus('completed')).toBe(true);
    expect(isRerunnableStatus('completed_with_gaps')).toBe(true);
    expect(isRerunnableStatus('failed')).toBe(true);
    expect(isRerunnableStatus('cancelled')).toBe(true);
    expect(isRerunnableStatus('running')).toBe(false);
    expect(isRerunnableStatus('approved')).toBe(false);
  });

  it('marks finished/stopped/error as settled UI phases', () => {
    expect(isSettledPhase('finished')).toBe(true);
    expect(isSettledPhase('stopped')).toBe(true);
    expect(isSettledPhase('error')).toBe(true);
    expect(isSettledPhase('working')).toBe(false);
    expect(isSettledPhase('idle')).toBe(false);
  });
});
