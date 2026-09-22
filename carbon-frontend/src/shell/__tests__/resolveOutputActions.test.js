import { describe, it, expect } from 'vitest';
import {
  collectNavigateActionsFromSteps,
  resolveOutputActions,
} from '../resolveOutputActions';

describe('resolveOutputActions', () => {
  it('prefers plan.output_actions from the API', () => {
    const actions = resolveOutputActions({
      output_actions: [
        { type: 'navigate', route: '/my/requests/9', label: 'Open request', summary: 'CRS-9' },
      ],
      steps: [],
    });
    expect(actions).toHaveLength(1);
    expect(actions[0].route).toBe('/my/requests/9');
  });

  it('falls back to host navigate receipts on step tool_output', () => {
    const actions = collectNavigateActionsFromSteps([
      {
        step_id: 2,
        status: 'completed',
        tool_output: {
          status_code: 201,
          action: 'navigate',
          route: '/my/requests/3',
          label: 'Open leave request',
          summary: 'annual · 2026-09-22',
        },
      },
    ]);
    expect(actions[0]).toMatchObject({
      type: 'navigate',
      route: '/my/requests/3',
      label: 'Open leave request',
    });
  });

  it('rejects unsafe routes', () => {
    const actions = resolveOutputActions({
      output_actions: [
        { type: 'navigate', route: 'https://evil.example', label: 'Nope' },
      ],
    });
    expect(actions).toEqual([]);
  });
});
