import { describe, expect, it } from 'vitest';
import { mergeCanvasJourney } from '../mergeCanvasJourney';

describe('mergeCanvasJourney', () => {
  it('overlays completed run steps onto a Planned seed board', () => {
    const seed = {
      title: 'Seed',
      content_json: {
        kind: 'job_map',
        mode: 'agent',
        plan_id: 'plan-1',
        layers: {
          intent: { ask: 'Payroll', success_criteria: '', contract: 'agent' },
          job_map: {
            steps: [{ id: '0', title: 'One blob', tool: 'invoke_skill', status: 'pending' }],
            tools: [],
          },
          live_run: { progress_pct: 0, status: 'planned', blockers: [], pending_consent: null },
          evidence: { tables: [], headline: '', prose: '' },
          outcome: { summary: '' },
        },
      },
    };
    const merged = mergeCanvasJourney(seed, {
      status: 'completed',
      brief: 'Payroll',
      finalResponse: 'October payroll validated against GOSI.',
      steps: [
        { step_id: 0, intent: 'List runs', tool_name: 'list_payroll_runs', status: 'completed' },
        { step_id: 1, intent: 'Compute', tool_name: 'compute_payroll_run', status: 'completed' },
      ],
      artifacts: [{ name: 'audit.docx' }],
    });
    const layers = merged.content_json.layers;
    expect(layers.live_run.status).toBe('completed');
    expect(layers.live_run.progress_pct).toBe(100);
    expect(layers.job_map.steps).toHaveLength(2);
    expect(layers.job_map.steps[0].status).toBe('completed');
    expect(layers.outcome.summary).toMatch(/GOSI/);
    expect(layers.evidence.tables.some((t) => t.title === 'Deliverables')).toBe(true);
  });

  it('builds a board from journey alone when artifact missing', () => {
    const merged = mergeCanvasJourney(null, {
      status: 'running',
      brief: 'Audit',
      steps: [
        { step_id: 0, intent: 'Research', status: 'completed' },
        { step_id: 1, intent: 'Export', status: 'pending' },
      ],
    });
    expect(merged.content_json.mode).toBe('agent');
    expect(merged.content_json.layers.live_run.status).toBe('running');
  });
});
