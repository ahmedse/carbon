import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TaskBoard from '../TaskBoard';

const plans = [
  { id: 'need', brief: 'Emergency loan', status: 'pending_approval', created_at: '2026-09-23T10:00:00Z' },
  { id: 'run', brief: 'Leave 24-26 Sep', status: 'running', created_at: '2026-09-22T10:00:00Z' },
  { id: 'done', brief: 'Send GOSI file', status: 'completed', created_at: '2026-09-21T10:00:00Z' },
];

describe('TaskBoard', () => {
  it('shows needs-you first and does not open a graph', () => {
    render(<TaskBoard plans={plans} onSelect={vi.fn()} />);
    expect(screen.getByTestId('task-board-coworker')).toHaveTextContent('One thing needs you.');
    expect(screen.getByTestId('task-board-attention')).toHaveTextContent(/Emergency loan/);
    expect(screen.getByTestId('task-board-working')).toHaveTextContent(/Leave 24-26 Sep/);
    expect(screen.getByTestId('task-board-done')).toHaveTextContent(/GOSI file/);
    expect(screen.queryByText('Approve plan')).not.toBeInTheDocument();
  });

  it('opens a task from a row', () => {
    const onSelect = vi.fn();
    render(<TaskBoard plans={plans} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId('task-board-row-need'));
    expect(onSelect).toHaveBeenCalledWith('need');
  });
});
