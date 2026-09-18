/**
 * PA-S0 mode-contract unit fixtures (Agent bank S0 slice).
 * Maps PA-001…005 header/lifecycle honesty via stageForStatus + planStatusMeta.
 * Full Playwright PA-001–007 remains journey-12 (mocked) + journey-14/15 (live).
 */
import { describe, it, expect } from 'vitest';
import { stageForStatus } from '../shell/AgentStage';
import { effectivePlanStatus, planStatusMeta } from '../shell/aiTaskStatus';

describe('PA-S0 — Agent mode lifecycle labels (PA-001…005)', () => {
  it('PA-001/002: clarifying and needs-review stages', () => {
    expect(stageForStatus('discovering')).toBe('clarify');
    expect(stageForStatus('pending_approval')).toBe('review');
    expect(planStatusMeta('pending_approval').label).toMatch(/Needs review/i);
  });

  it('PA-003: approved/running map to run stage', () => {
    expect(stageForStatus('approved')).toBe('run');
    expect(stageForStatus('running', 'working')).toBe('run');
    expect(planStatusMeta('running').label).toMatch(/Running/i);
  });

  it('PA-004: paused / awaiting approval is consent surface', () => {
    expect(stageForStatus('paused')).toBe('run');
    expect(planStatusMeta('paused').label).toMatch(/approval/i);
    expect(
      effectivePlanStatus({
        status: 'running',
        steps: [{ status: 'awaiting_approval' }, { status: 'pending' }],
      }),
    ).toBe('paused');
  });

  it('PA-005: completed lands on done', () => {
    expect(stageForStatus('completed', 'finished')).toBe('done');
    expect(planStatusMeta('completed').label).toMatch(/Completed/i);
    expect(
      effectivePlanStatus({
        status: 'running',
        steps: [{ status: 'completed' }, { status: 'completed' }],
      }),
    ).toBe('completed');
  });
});
