import { describe, it, expect } from 'vitest';
import { receiptStateFromPlan } from '../resultOutcome';

describe('receiptStateFromPlan', () => {
  it('keeps durable completed over a stale error phase after Approve', () => {
    const state = receiptStateFromPlan(
      { status: 'completed', steps: [{ status: 'completed' }] },
      'error',
    );
    expect(state.labelKey).toBeUndefined();
    expect(state.color).toBe('success');
    expect(String(state.label || '').toLowerCase()).toMatch(/complete|done/);
  });

  it('still marks true failures', () => {
    const state = receiptStateFromPlan(
      { status: 'failed', steps: [{ status: 'failed' }] },
      'error',
    );
    expect(state.labelKey).toBe('boardChipFailed');
    expect(state.color).toBe('error');
  });
});
