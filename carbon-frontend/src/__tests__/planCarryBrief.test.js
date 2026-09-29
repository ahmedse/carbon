import { describe, expect, it } from 'vitest';
import { briefFromWriteDraft, requestForPlanSwitch, requestFromAskCommit } from '../shell/planCarryBrief';

describe('planCarryBrief', () => {
  it('builds a leave brief from bound slots', () => {
    expect(briefFromWriteDraft({
      leave_type: 'annual',
      start_date: '2026-10-04',
      end_date: '2026-10-05',
      days: 2,
    })).toBe('I want annual leave for 2 days starting 2026-10-04 ending 2026-10-05.');
  });

  it('does not send yes go or the last chip as the Plan request', () => {
    expect(requestForPlanSwitch({
      draft: {
        leave_type: 'annual',
        start_date: '2026-10-04',
        end_date: '2026-10-05',
        days: 2,
      },
      lastUser: 'yes go',
      userTurns: [
        'I want to request annual leave starting next Sunday.',
        'Make it 2 days.',
        'yes go',
      ],
    })).toBe('I want annual leave for 2 days starting 2026-10-04 ending 2026-10-05.');
  });

  it('treats yes go on Ask as the Switch to Plan button', () => {
    const brief = 'I want annual leave for 2 days starting 2026-10-04 ending 2026-10-05.';
    expect(requestFromAskCommit([
      { role: 'user', content: 'I want to request annual leave starting next Sunday.' },
      {
        role: 'assistant',
        metadata: {
          actions: [{
            type: 'open_panel',
            panel: 'plan',
            label: 'Switch to Plan',
            brief,
            draft: {
              leave_type: 'annual',
              start_date: '2026-10-04',
              end_date: '2026-10-05',
              days: 2,
            },
          }],
        },
      },
    ], 'yes go')).toBe(brief);
  });

  it('uses the slots on the Plan button when the brief text is missing', () => {
    expect(requestFromAskCommit([
      { role: 'user', content: 'My project code is ALPHA-7.' },
      { role: 'user', content: 'yes go' },
      {
        role: 'assistant',
        metadata_json: {
          actions: [{
            type: 'open_panel',
            panel: 'plan',
            label: 'Switch to Plan',
            draft: {
              leave_type: 'annual',
              start_date: '2026-10-04',
              end_date: '2026-10-05',
              days: 2,
            },
          }],
        },
      },
    ], 'yes go')).toBe('I want annual leave for 2 days starting 2026-10-04 ending 2026-10-05.');
  });

  it('does not switch when the last card is not Plan', () => {
    expect(requestFromAskCommit([
      { role: 'assistant', content: '18 days remaining.' },
    ], 'yes go')).toBe('');
  });

  it('uses the action brief when present', () => {
    expect(requestForPlanSwitch({
      brief: 'I want annual leave for 2 days starting 2026-10-04 ending 2026-10-05.',
      lastUser: '2',
    })).toBe('I want annual leave for 2 days starting 2026-10-04 ending 2026-10-05.');
  });
});
