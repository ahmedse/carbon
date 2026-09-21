import { describe, it, expect } from 'vitest';
import { buildDiscussDraft, buildDiscussHandoff } from '../shell/buildDiscussDraft';

describe('buildDiscussHandoff', () => {
  it('includes draft + plan metadata for the continuity chip', () => {
    const plan = { id: 'abc', brief: 'Apply for leave' };
    const handoff = buildDiscussHandoff(plan, 'Done.', { refine: true });
    expect(handoff.planId).toBe('abc');
    expect(handoff.planBrief).toBe('Apply for leave');
    expect(handoff.draft).toBe(buildDiscussDraft(plan, 'Done.', { refine: true }));
    expect(handoff.draft).toMatch(/DISCUSSION ONLY/);
  });
});
