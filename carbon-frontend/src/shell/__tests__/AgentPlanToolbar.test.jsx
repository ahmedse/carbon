// src/shell/__tests__/AgentPlanToolbar.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentPlanToolbar from '../AgentPlanToolbar';

const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'Create a professional Word report analyzing salary distribution at GOFSCO.',
  steps: [],
};

describe('AgentPlanToolbar', () => {
  it('toolbar: Approve / Cancel / Discuss; no Fork or Replan', () => {
    const onApprove = vi.fn();
    const onDecline = vi.fn();
    const onDiscuss = vi.fn();
    render(
      <AgentPlanToolbar
        plan={PLAN}
        onApprove={onApprove}
        onDecline={onDecline}
        onDiscuss={onDiscuss}
      />,
    );

    expect(screen.getByTestId('agent-plan-toolbar')).toBeInTheDocument();
    expect(screen.getByTestId('agent-plan-label')).toHaveTextContent(
      /Create a professional Word report analyzing salary distribution at GOFSCO/i,
    );
    expect(screen.getByTestId('agent-review-consent')).toBeInTheDocument();
    expect(screen.queryByTestId('agent-review-more')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Fork/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: /Replan/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));
    expect(onApprove).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel plan' }));
    expect(onDecline).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Discuss in Chat/i }));
    expect(onDiscuss).toHaveBeenCalled();
  });

  it('inspect mode: Discuss only', () => {
    render(
      <AgentPlanToolbar
        plan={{ ...PLAN, status: 'completed' }}
        mode="inspect"
        onApprove={vi.fn()}
        onDecline={vi.fn()}
        onDiscuss={vi.fn()}
      />,
    );
    expect(screen.getByTestId('agent-review-inspect')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Discuss in Chat/i })).toBeInTheDocument();
    expect(screen.queryByTestId('agent-review-more')).not.toBeInTheDocument();
  });
});
