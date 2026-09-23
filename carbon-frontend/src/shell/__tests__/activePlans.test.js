import { describe, it, expect } from 'vitest';
import { inheritedContextItems, nextStepVerb, pickOpenActivePlan } from '../activePlans';

describe('pickOpenActivePlan', () => {
  it('prefers a non-terminal plan', () => {
    const open = pickOpenActivePlan([
      { plan_id: 'done', status: 'completed', title: 'old' },
      { plan_id: 'live', status: 'pending_approval', title: 'emergency loan' },
    ]);
    expect(open.plan_id).toBe('live');
  });

  it('returns the latest snapshot when only terminal rows exist', () => {
    const open = pickOpenActivePlan([
      { plan_id: 'done', status: 'completed', title: 'old' },
    ]);
    expect(open.plan_id).toBe('done');
  });
});

describe('nextStepVerb', () => {
  it('names the Agent action, not a Chat confirm on handoff', () => {
    expect(nextStepVerb('handoff_ready')).toBe('Submit');
    expect(nextStepVerb('pending_approval')).toBe('Approve');
    expect(nextStepVerb('paused')).toBe('Confirm');
    expect(nextStepVerb('approved')).toBe('Run');
    expect(nextStepVerb('completed')).toBe('');
  });
});

describe('inheritedContextItems', () => {
  it('keeps outcome items only', () => {
    expect(inheritedContextItems({
      inherited_context: [
        { key: 'amount', value: '3000' },
        { key: 'api', value: '' },
        null,
      ],
    })).toEqual([{ key: 'amount', value: '3000' }]);
  });
});
