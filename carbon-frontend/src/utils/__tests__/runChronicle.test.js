import { describe, it, expect } from 'vitest';
import { buildRunChronicle, chronicleTone } from '../../utils/runChronicle';
import { humanizeCanvasText, humanStatusLabel } from '../../utils/humanizeCanvas';

describe('buildRunChronicle', () => {
  it('builds Operator events from intents and statuses', () => {
    const events = buildRunChronicle({
      steps: [
        {
          step_id: 0,
          intent: 'Retrieve leave data',
          status: 'completed',
          finished_at: '2026-09-20T10:00:05Z',
          latency_ms: 1200,
          consent_granted: true,
        },
        {
          step_id: 1,
          intent: 'Write compliance note',
          tool_name: 'create_dq_rule',
          status: 'awaiting_approval',
          started_at: '2026-09-20T10:00:10Z',
        },
        {
          step_id: 2,
          intent: 'Fetch summary',
          tool_name: 'search_entity',
          status: 'pending',
        },
      ],
    });
    expect(events).toHaveLength(3);
    expect(events[0].title).toBe('Retrieve leave data');
    expect(events[0].detail).toBe('Approved by you');
    expect(events[0].kind).toBe('done');
    expect(events[0].clock).toBeTruthy();
    expect(events[1].kind).toBe('consent');
    expect(events[1].detail).toMatch(/changing data/i);
    expect(events[2].beatLabel).toBe('#3');
    expect(chronicleTone('consent')).toBe('warning');
  });

  it('uses soft consent copy for non-write tools', () => {
    const [evt] = buildRunChronicle({
      steps: [{
        step_id: 0,
        intent: 'Retrieve leave compliance data',
        tool_name: 'search_entity',
        status: 'awaiting_approval',
      }],
    });
    expect(evt.detail).toMatch(/OK to continue/i);
    expect(evt.beatLabel).toBe('#1');
  });
});

describe('humanizeCanvas', () => {
  it('strips RULE_ jargon for Operator copy', () => {
    expect(humanizeCanvasText('RULE_21: deny write until confirm')).toMatch(/deny write/i);
    expect(humanizeCanvasText('RULE_21: deny write until confirm')).not.toMatch(/RULE/i);
    expect(humanStatusLabel('awaiting_approval')).toBe('Needs your OK');
  });
});
