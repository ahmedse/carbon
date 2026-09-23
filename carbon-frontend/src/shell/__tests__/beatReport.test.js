import { describe, it, expect } from 'vitest';
import { beatSituation } from '../beatReport';

describe('beatSituation', () => {
  it('treats a successful read retry as healed', () => {
    const situation = beatSituation({
      status: 'completed',
      retry_count: 1,
      is_mutation: false,
      heal_note: 'Read the loan list on the second try.',
    });
    expect(situation.healed).toBe(true);
    expect(situation.failed).toBe(false);
    expect(situation.heal).toMatch(/loan list/);
  });

  it('does not call a write retry a self-heal', () => {
    const situation = beatSituation({
      status: 'completed',
      retry_count: 1,
      is_mutation: true,
    });
    expect(situation.healed).toBe(false);
    expect(situation.writeStopped).toBe(true);
  });

  it('keeps the failure text for a stopped write', () => {
    const situation = beatSituation({
      status: 'failed',
      is_mutation: true,
      error: 'Balance does not cover the installment.',
    });
    expect(situation.failed).toBe(true);
    expect(situation.error).toMatch(/installment/);
  });
});
