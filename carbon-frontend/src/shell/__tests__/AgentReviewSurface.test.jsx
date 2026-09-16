// src/shell/__tests__/AgentReviewSurface.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentReviewSurface from '../AgentReviewSurface';

vi.mock('../AgentRunSurface', () => ({
  default: function MockRunSurface({ listContent }) {
    return (
      <div data-testid="agent-run-surface">
        <div data-testid="plan-dag-graph">graph</div>
        <button type="button" onClick={() => {}}>List</button>
        {listContent}
      </div>
    );
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
});
