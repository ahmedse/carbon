import { describe, expect, it } from 'vitest';
import { buildDiscussDraft } from '../buildDiscussDraft';

const plan = {
  id: '74a5e6a6-942c-4185-a986-8f895601d5ca',
  brief: 'Count Nibras employees by employment status and list the top 3 statuses with counts. Keep the plan short.',
};

const noisyOutcome = [
  "The entity 'Nibras' was not found, so no employee count by employment status can be provided.",
  'To identify the top 3 employment statuses by count, I will analyze the employee population',
  'based on the "is_active" dimension. Let me call the relevant endpoint and provide the results.',
].join(' ');

describe('buildDiscussDraft', () => {
  it('refine: seeds plan id + brief, DISCUSSION ONLY, no outcome body', () => {
    const draft = buildDiscussDraft(plan, noisyOutcome, { refine: true });
    expect(draft).toMatch(/I'd like to refine plan/);
    expect(draft).toMatch(/74a5e6a6-942c-4185-a986-8f895601d5ca/);
    expect(draft).toMatch(/Count Nibras employees/);
    expect(draft).toMatch(/DISCUSSION ONLY/);
    expect(draft).toMatch(/Fork or Replan/);
    expect(draft).not.toMatch(/analyze the employee/);
    expect(draft).not.toMatch(/call the relevant endpoint/);
    expect(draft).not.toMatch(/Nibras' was not found/);
  });

  it('outcome discuss: marks prior body as context-only and DISCUSSION ONLY', () => {
    const draft = buildDiscussDraft(plan, noisyOutcome, { refine: false });
    expect(draft).toMatch(/Let's discuss the outcome/);
    expect(draft).toMatch(/Prior outcome \(context only/);
    expect(draft).toMatch(/DISCUSSION ONLY/);
    expect(draft).toMatch(/do not re-execute|Do not call tools/i);
  });
});
