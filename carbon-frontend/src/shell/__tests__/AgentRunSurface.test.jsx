// src/shell/__tests__/AgentRunSurface.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentRunSurface, { mergePlanWithRunSteps } from '../AgentRunSurface';

const PLAN = {
  id: 'plan-1',
  status: 'completed',
  brief: 'Audit duplicates',
  steps: [
    {
      step_id: 0,
      intent: 'Search for duplicate records',
      tool_name: 'search_entity',
      tool_args: { dataset: 'emissions' },
      status: 'completed',
      finished_at: '2026-09-20T10:00:00Z',
      depends_on: [],
    },
    {
      step_id: 1,
      intent: 'Create a rule',
      tool_name: 'create_dq_rule',
      status: 'completed',
      finished_at: '2026-09-20T10:01:00Z',
      depends_on: [0],
    },
  ],
};

describe('mergePlanWithRunSteps', () => {
  it('overlays streamed tool_output onto plan steps', () => {
    const merged = mergePlanWithRunSteps(PLAN, [
      { step_id: 0, tool_output: { count: 3 }, status: 'completed' },
    ]);
    expect(merged.steps[0].tool_output).toEqual({ count: 3 });
    expect(merged.steps[0].tool_name).toBe('search_entity');
  });
});

describe('AgentRunSurface', () => {
  it('does not stack Job Map or DAG on the Run surface', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        conversationId="conv-1"
        listContent={<div>Step list body</div>}
      />,
    );
    expect(screen.queryByTestId('agent-run-job-map')).toBeNull();
    expect(screen.queryByTestId('agent-run-job-map-board')).toBeNull();
    expect(screen.queryByTestId('plan-dag-graph')).toBeNull();
  });

  it('renders visual timeline spine with beat nodes', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        artifacts={[{ id: 1, name: 'report.csv' }]}
        listContent={<div>Step list body</div>}
      />,
    );

    expect(screen.getByTestId('agent-run-surface')).toBeInTheDocument();
    const timeline = screen.getByTestId('agent-run-chronicle');
    expect(timeline).toHaveAttribute('data-timeline', 'visual');
    expect(timeline).toHaveTextContent('Search for duplicate records');
    expect(screen.getByTestId('run-timeline-node-0')).toBeInTheDocument();
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/2\/2/);
    expect(screen.queryByTestId('agent-run-list')).not.toBeInTheDocument();
    expect(screen.queryByText('report.csv')).toBeNull();
  });

  it('hands off to Output when deliverables exist after a finished run', () => {
    const onOpenOutput = vi.fn();
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        artifacts={[{ id: 1, name: 'report.csv' }, { id: 2, name: 'chart.png' }]}
        listContent={<div>Step list body</div>}
        onOpenOutput={onOpenOutput}
      />,
    );
    expect(screen.getByTestId('agent-run-output-handoff')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open Output' }));
    expect(onOpenOutput).toHaveBeenCalledTimes(1);
  });

  it('shows post-done Rerun and Edit on Plan CTAs when settled', () => {
    const onRerun = vi.fn();
    const onOpenPlan = vi.fn();
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        listContent={<div>Step list body</div>}
        onRerun={onRerun}
        onOpenPlan={onOpenPlan}
        canRerun
      />,
    );
    expect(screen.getByTestId('agent-run-post-done')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Rerun' }));
    expect(onRerun).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Edit on Plan' }));
    expect(onOpenPlan).toHaveBeenCalled();
  });

  it('toggles step details without losing chronicle', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        listContent={<div>Step list body</div>}
      />,
    );

    expect(screen.getByTestId('agent-run-chronicle')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('agent-run-toggle-details'));
    expect(screen.getByTestId('agent-run-list')).toHaveTextContent('Step list body');
    fireEvent.click(screen.getByTestId('agent-run-toggle-details'));
    expect(screen.queryByTestId('agent-run-list')).not.toBeInTheDocument();
  });

  it('does not host Run health accordion', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
      />,
    );
    expect(screen.queryByTestId('agent-run-health')).toBeNull();
  });

  it('opens docked side pane from timeline beat click', async () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
      />,
    );
    expect(screen.getByTestId('run-structure-detail')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('run-timeline-open-0'));
    expect(await screen.findByTestId('beat-detail-body')).toBeInTheDocument();
    expect(screen.getByTestId('beat-detail-body')).toHaveTextContent('Search for duplicate records');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows one Approve control on the consent timeline node only', () => {
    const onConfirm = vi.fn();
    const onDecline = vi.fn();
    const consentPlan = {
      id: 'plan-consent',
      status: 'paused',
      brief: 'Hire someone',
      steps: [
        {
          step_id: 0,
          intent: 'Create employee',
          tool_name: 'call_host_api',
          tool_args: { api_name: 'create_employee', body: {} },
          status: 'awaiting_approval',
          depends_on: [],
        },
      ],
    };
    render(
      <AgentRunSurface
        plan={consentPlan}
        runSteps={[]}
        phase="paused"
        onConfirmStep={onConfirm}
        onDeclineStep={onDecline}
        confirmingId={null}
        consentHero={(
          <div data-testid="consent-hero-card" data-consent-mode="status-strip">
            Needs your approval
          </div>
        )}
      />,
    );
    expect(screen.getByTestId('timeline-consent-0')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /^Approve$/i })).toHaveLength(1);
    expect(screen.getByTestId('consent-hero-card')).toHaveAttribute('data-consent-mode', 'status-strip');
    // No operator JSON dump of api_name in the dock / timeline
    expect(screen.queryByText(/"api_name"/)).not.toBeInTheDocument();
    expect(screen.getByTestId('timeline-consent-form-0')).toBeInTheDocument();
  });
});
