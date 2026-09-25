import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PlanProposalForm from '../PlanProposalForm';

function proposal(overrides = {}) {
  return {
    kind: 'plan_proposal',
    conversation_id: 'conv-1',
    brief: 'lowest 20 salaries and their jobs',
    steps: [
      {
        step_id: 1,
        intent: 'Read the 20 lowest salaries',
        args: [{ name: 'limit', value: '20' }],
        blocked: false,
        gap: '',
      },
      { step_id: 2, intent: 'Read their positions', args: [], blocked: false, gap: '' },
    ],
    blocked_count: 0,
    ...overrides,
  };
}

describe('PlanProposalForm', () => {
  it('shows the steps and says nothing exists yet', () => {
    render(<PlanProposalForm proposal={proposal()} />);
    expect(screen.getByText('Read the 20 lowest salaries')).toBeTruthy();
    expect(screen.getByText('limit: 20')).toBeTruthy();
    expect(screen.getByText(/Not created yet/)).toBeTruthy();
  });

  it('creates the task only when the user chooses Create task', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<PlanProposalForm proposal={proposal()} onCreate={onCreate} />);
    expect(onCreate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Create task' }));
    await waitFor(() => expect(screen.getByText(/Task created/)).toBeTruthy());
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it('sends the user own words as a change', () => {
    const onChange = vi.fn();
    render(<PlanProposalForm proposal={proposal()} onCreate={vi.fn()} onChange={onChange} />);
    fireEvent.change(screen.getByPlaceholderText(/what to change/), {
      target: { value: 'add department and hire date' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Change' }));
    expect(onChange).toHaveBeenCalledWith('add department and hire date');
  });

  it('marks a step the plan cannot run, before the user commits', () => {
    render(<PlanProposalForm proposal={proposal({
      steps: [
        { step_id: 1, intent: 'Read salaries', args: [], blocked: false, gap: '' },
        { step_id: 2, intent: 'Mail the board', args: [], blocked: true, gap: 'no capability' },
      ],
      blocked_count: 1,
    })} />);
    expect(screen.getByText(/no capability/)).toBeTruthy();
    expect(screen.getByText(/cannot run as planned/)).toBeTruthy();
  });

  it('does not create a task when the catalog cannot produce the deliverable', () => {
    const onCreate = vi.fn();
    render(<PlanProposalForm proposal={proposal({
      steps: [
        { step_id: 1, intent: 'Read lines', args: [], blocked: false, gap: '' },
        {
          step_id: 2,
          intent: 'Export the workbook',
          args: [],
          blocked: true,
          gap: 'declared output',
          reason: 'This export does not name the fields it will contain.',
          findings: [{ code: 'output_fit', detail: 'This export does not name the fields it will contain.', blocks: true }],
        },
      ],
      blocked_count: 1,
      blocks_create: true,
    })} onCreate={onCreate} />);
    expect(screen.getByText(/does not name the fields/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Create task' })).toHaveProperty('disabled', true);
    fireEvent.click(screen.getByRole('button', { name: 'Create task' }));
    expect(onCreate).not.toHaveBeenCalled();
  });

  it('offers no approve control — approving lives in Tasks', () => {
    render(<PlanProposalForm proposal={proposal()} onCreate={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /approve/i })).toBeNull();
  });
});
