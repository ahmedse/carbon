/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import OpsCanvasHost from './OpsCanvasHost';

describe('OpsCanvasHost', () => {
  it('renders Agent Job Map with live run and plan steps', () => {
    const artifact = {
      id: 'c1',
      title: 'Payroll board pack',
      artifact_type: 'job_map',
      content_json: {
        kind: 'job_map',
        mode: 'agent',
        plan_id: 'plan-abc',
        layers: {
          intent: { ask: 'Build payroll variance pack', contract: 'agent' },
          job_map: {
            steps: [
              { id: '1', title: 'Fetch run', tool: 'resolve_entity', status: 'completed' },
              { id: '2', title: 'Export pack', tool: 'export_document', status: 'running' },
            ],
            tools: ['resolve_entity', 'export_document'],
            capabilities: ['ai:run_agent'],
            entities: [],
          },
          live_run: {
            progress_pct: 50,
            status: 'running',
            qos: { acceptance_status: 'partial', requirements_total: 2, requirements_met: 1 },
            blockers: [],
          },
          evidence: { headline: 'Mid-run', tables: [], sources: [], caveats: [] },
          outcome: { summary: '', canvas_id: 'c1', sor_links: [] },
        },
      },
    };
    render(<OpsCanvasHost artifact={artifact} />);
    expect(screen.getByTestId('ops-canvas-host')).toBeTruthy();
    expect(screen.getByText('Payroll board pack')).toBeTruthy();
    expect(screen.getByText(/Agent · execution/)).toBeTruthy();
    expect(screen.getByText(/Live run/)).toBeTruthy();
    expect(screen.getByText(/Job map · plan steps/)).toBeTruthy();
    expect(screen.getByText(/Fetch run/)).toBeTruthy();
    expect(screen.getByText('QoS partial')).toBeTruthy();
  });

  it('demotes Chat brief as advisory', () => {
    const artifact = {
      id: 'c2',
      title: 'Leave brief',
      artifact_type: 'job_map',
      content_json: {
        kind: 'job_map',
        mode: 'chat',
        layers: {
          intent: { ask: 'Leave balances?', contract: 'advisory' },
          job_map: { steps: [], tools: [], capabilities: [], entities: [] },
          live_run: { progress_pct: 100, status: 'complete', blockers: [] },
          evidence: { headline: 'Five types', tables: [], sources: [], caveats: [] },
          outcome: { summary: 'Done', canvas_id: 'c2', sor_links: [] },
        },
      },
    };
    render(<OpsCanvasHost artifact={artifact} />);
    expect(screen.getByText(/Chat · advisory/)).toBeTruthy();
    expect(screen.getAllByText(/Chat Job Brief/).length).toBeGreaterThan(0);
    expect(screen.getByText('Five types')).toBeTruthy();
  });
});
