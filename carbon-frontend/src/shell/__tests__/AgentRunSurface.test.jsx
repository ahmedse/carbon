// src/shell/__tests__/AgentRunSurface.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentRunSurface, { mergePlanWithRunSteps } from '../AgentRunSurface';

vi.mock('../../components/graph/PlanDagGraph', () => ({
  default: function MockPlanDagGraph({ plan, live }) {
    const step = plan?.steps?.[0];
    return (
      <div data-testid="plan-dag-graph" data-live={live ? '1' : '0'}>
        {step?.tool_name || 'no-tool'}
        {step?.tool_output != null && (
          <span data-testid="merged-output">{JSON.stringify(step.tool_output)}</span>
        )}
      </div>
    );
  },
}));

vi.mock('../OpsCanvasShelf', () => ({
  default: function MockShelf() {
    return <div data-testid="ops-canvas-shelf-mock" />;
  },
}));

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
  it('shows Job Map control when conversationId is set', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        conversationId="conv-1"
      />,
    );
    expect(screen.getByTestId('agent-run-job-map')).toBeTruthy();
  });
  it('renders the plan DAG as the hero with a progress strip', () => {
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
    expect(screen.getByTestId('plan-dag-graph')).toBeInTheDocument();
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/2\/2 steps/);
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/2 tools/);
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/1 artifact/);
    expect(screen.queryByTestId('agent-run-list')).not.toBeInTheDocument();
  });

  it('reveals the step list only after List is clicked', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        listContent={<div>Step list body</div>}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'List' }));
    expect(screen.getByTestId('agent-run-list')).toHaveTextContent('Step list body');
    fireEvent.click(screen.getByRole('button', { name: 'Hide list' }));
    expect(screen.queryByTestId('agent-run-list')).not.toBeInTheDocument();
  });

  it('merges live runSteps into the graph plan', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[{ step_id: 0, tool_output: { count: 3 }, status: 'completed' }]}
        phase="finished"
        live={false}
      />,
    );
    expect(screen.getByTestId('merged-output')).toHaveTextContent('{"count":3}');
  });
});
