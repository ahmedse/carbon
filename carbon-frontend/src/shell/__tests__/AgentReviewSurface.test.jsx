// src/shell/__tests__/AgentReviewSurface.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AgentReviewSurface from '../AgentReviewSurface';

vi.mock('../../components/graph/PlanDagGraph', () => ({
  default: function MockPlanDagGraph({ mode, live }) {
    return (
      <div
        data-testid="plan-dag-graph"
        data-mode={mode}
        data-live={live ? 'yes' : 'no'}
      >
        graph
      </div>
    );
  },
}));

const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'List leave balances for org unit 8.',
  steps: [
    { step_id: 0, intent: 'Retrieve employees', tool_name: 'get_entity_details', status: 'pending', depends_on: [] },
  ],
};

describe('AgentReviewSurface', () => {
  it('Plan body is the live status DAG (chrome lives in cockpit toolbar)', () => {
    render(<AgentReviewSurface plan={PLAN} />);
    expect(screen.getByTestId('agent-review-surface')).toBeInTheDocument();
    expect(screen.getByTestId('plan-dag-graph')).toHaveAttribute('data-mode', 'execution');
    expect(screen.getByTestId('plan-dag-graph')).toHaveAttribute('data-live', 'no');
    expect(screen.queryByTestId('agent-review-consent')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-review-step-list')).not.toBeInTheDocument();
  });

  it('honors live prop so the Plan graph tracks the run', () => {
    render(<AgentReviewSurface plan={PLAN} live />);
    expect(screen.getByTestId('plan-dag-graph')).toHaveAttribute('data-live', 'yes');
  });
});
