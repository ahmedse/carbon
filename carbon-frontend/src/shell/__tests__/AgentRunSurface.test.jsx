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
      depends_on: [],
    },
    {
      step_id: 1,
      intent: 'Create a rule',
      tool_name: 'create_dq_rule',
      status: 'completed',
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

  it('renders progress strip and step list as the Run hero — no artifact cards', () => {
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
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/2\/2/);
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/1 artifacts/);
    expect(screen.getByTestId('agent-run-list')).toHaveTextContent('Step list body');
    // ADR-0043: deliverable cards belong on Output, not Run.
    expect(screen.queryByTestId('agent-run-artifacts')).toBeNull();
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

  it('hides the step list when List is toggled off', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        listContent={<div>Step list body</div>}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Hide list' }));
    expect(screen.queryByTestId('agent-run-list')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'List' }));
    expect(screen.getByTestId('agent-run-list')).toHaveTextContent('Step list body');
  });
});
