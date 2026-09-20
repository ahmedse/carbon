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
  it('toolbar: Approve / Cancel / Discuss; label is not editable', () => {
    const onApprove = vi.fn();
    const onDecline = vi.fn();
    const onDiscuss = vi.fn();
    render(
      <AgentPlanToolbar
        plan={PLAN}
        onApprove={onApprove}
        onDecline={onDecline}
        onDiscuss={onDiscuss}
        onFork={vi.fn()}
        onReplanPlan={vi.fn()}
      />,
    );

    expect(screen.getByTestId('agent-plan-toolbar')).toBeInTheDocument();
    expect(screen.getByTestId('agent-plan-label')).toHaveTextContent(/Create a professional Word report/i);
    expect(screen.queryByTestId('agent-plan-label-edit')).not.toBeInTheDocument();
    expect(screen.getByTestId('agent-review-consent')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));
    expect(onApprove).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel plan' }));
    expect(onDecline).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Discuss in Chat/i }));
    expect(onDiscuss).toHaveBeenCalled();
  });

  it('inspect More: Fork + Replan only (no Rename of prompt)', () => {
    const onReplan = vi.fn();
    render(
      <AgentPlanToolbar
        plan={{ ...PLAN, status: 'completed' }}
        mode="inspect"
        onApprove={vi.fn()}
        onDecline={vi.fn()}
        onFork={vi.fn()}
        onReplanPlan={onReplan}
        onDiscuss={vi.fn()}
      />,
    );
    expect(screen.getByTestId('agent-review-inspect')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('agent-review-more'));
    expect(screen.queryByRole('menuitem', { name: 'Rename' })).not.toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Fork/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Replan…' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Replan…' }));
    expect(screen.getByTestId('agent-brief-editor-replan')).toBeInTheDocument();
  });
});
