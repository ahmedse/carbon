// src/shell/__tests__/AgentReviewSurface.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentReviewSurface from '../AgentReviewSurface';

vi.mock('../../components/graph/PlanDagGraph', () => ({
  default: function MockPlanDagGraph() {
    return <div data-testid="plan-dag-graph">graph</div>;
  },
}));

const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'List leave balances for org unit 8.',
  steps: [
    { step_id: 0, intent: 'Retrieve employees', tool_name: 'get_entity_details', agent_role: 'researcher', status: 'pending', depends_on: [] },
    { step_id: 1, intent: 'Fetch leave balances', tool_name: 'search_entity', agent_role: 'researcher', status: 'pending', depends_on: [0] },
  ],
};

describe('AgentReviewSurface', () => {
  it('shows graph hero plus Approve/Decline controls', () => {
    const onApprove = vi.fn();
    const onDecline = vi.fn();
    render(
      <AgentReviewSurface
        plan={PLAN}
        onApprove={onApprove}
        onDecline={onDecline}
        onFork={vi.fn()}
        onEditStep={vi.fn()}
      />,
    );

    expect(screen.getByTestId('agent-review-surface')).toBeInTheDocument();
    expect(screen.getByTestId('plan-dag-graph')).toBeInTheDocument();
    expect(screen.getByTestId('agent-review-consent')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));
    expect(onApprove).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Decline' }));
    expect(onDecline).toHaveBeenCalled();
  });

  it('shows Rename / Replan / Fork / Discuss on inspect mode for completed plans', () => {
    const onRename = vi.fn();
    const onReplan = vi.fn();
    const onDiscuss = vi.fn();
    render(
      <AgentReviewSurface
        plan={{ ...PLAN, status: 'completed' }}
        mode="inspect"
        onApprove={vi.fn()}
        onDecline={vi.fn()}
        onFork={vi.fn()}
        onRenamePlan={onRename}
        onReplanPlan={onReplan}
        onDiscuss={onDiscuss}
      />,
    );
    expect(screen.getByTestId('agent-review-inspect')).toBeInTheDocument();
    expect(screen.queryByTestId('agent-review-consent')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Replan…' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Fork/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Discuss in Chat/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
    expect(screen.getByTestId('agent-brief-editor-rename')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Rename'), {
      target: { value: 'Payroll variance board pack 2026' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save title' }));
    expect(onRename).toHaveBeenCalledWith('Payroll variance board pack 2026');
  });
});
