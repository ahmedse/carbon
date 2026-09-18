/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import OpsCanvasHost from './OpsCanvasHost';

describe('OpsCanvasHost', () => {
  it('renders five Job Map layers from a job_map artifact', () => {
    const artifact = {
      id: 'c1',
      title: 'Leave follow-up',
      artifact_type: 'job_map',
      content_json: {
        kind: 'job_map',
        mode: 'chat',
        layers: {
          intent: { ask: 'What are their leave entitlements?', contract: 'advisory' },
          job_map: {
            steps: [{ id: '1', title: 'List leave', tool: 'list_leave_entitlements', status: 'done' }],
            tools: ['list_leave_entitlements'],
            capabilities: [],
            entities: [],
          },
          live_run: { progress_pct: 100, status: 'complete', blockers: [] },
          evidence: { headline: 'Five leave types', tables: [], sources: [], caveats: [] },
          outcome: { summary: 'Entitlements retrieved', canvas_id: 'c1', sor_links: [] },
        },
      },
    };
    render(<OpsCanvasHost artifact={artifact} />);
    expect(screen.getByTestId('ops-canvas-host')).toBeTruthy();
    expect(screen.getByText('Leave follow-up')).toBeTruthy();
    expect(screen.getByText(/What are their leave entitlements/)).toBeTruthy();
    expect(screen.getByText('Five leave types')).toBeTruthy();
    expect(screen.getByText(/List leave/)).toBeTruthy();
  });

  it('renders FlightDirector QoS chips on live_run', () => {
    const artifact = {
      id: 'c2',
      title: 'Agent map',
      artifact_type: 'job_map',
      content_json: {
        kind: 'job_map',
        mode: 'agent',
        layers: {
          intent: { ask: 'Audit leave', contract: 'agent' },
          job_map: { steps: [], tools: [], capabilities: [], entities: [] },
          live_run: {
            progress_pct: 100,
            status: 'completed',
            qos: {
              acceptance_status: 'met',
              requirements_total: 2,
              requirements_met: 2,
              requirements_partial: 0,
              requirements_missed: 0,
            },
            blockers: [],
          },
          evidence: { headline: '', tables: [], sources: [], caveats: [] },
          outcome: { summary: '', canvas_id: 'c2', sor_links: [] },
        },
      },
    };
    render(<OpsCanvasHost artifact={artifact} />);
    expect(screen.getByText('QoS met')).toBeTruthy();
    expect(screen.getByText('2/2 met')).toBeTruthy();
  });
});
