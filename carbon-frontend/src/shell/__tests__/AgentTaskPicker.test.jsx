// src/shell/__tests__/AgentTaskPicker.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentTaskPicker from '../AgentTaskPicker';

const plans = [
  { id: 'a', brief: 'Active leave plan', status: 'pending_approval', created_at: '2026-09-16T10:00:00Z' },
  { id: 'b', brief: 'Old payroll', status: 'completed', created_at: '2026-09-15T10:00:00Z' },
  {
    id: 'c',
    brief: 'Stuck running but all finished',
    status: 'running',
    steps: [
      { step_id: 0, status: 'completed' },
      { step_id: 1, status: 'completed' },
    ],
    created_at: '2026-09-14T10:00:00Z',
  },
];

describe('AgentTaskPicker', () => {
  it('renders a Task select (not a long list)', () => {
    render(<AgentTaskPicker plans={plans} selectedId="" onSelect={vi.fn()} />);
    expect(screen.getByLabelText('Task')).toBeInTheDocument();
    expect(screen.getByText(/New \/ pick one/i)).toBeInTheDocument();
    expect(screen.queryByText('My tasks')).not.toBeInTheDocument();
  });

  it('calls onSelect when a task is chosen', async () => {
    const onSelect = vi.fn();
    render(<AgentTaskPicker plans={plans} selectedId="" onSelect={onSelect} />);
    fireEvent.mouseDown(screen.getByLabelText('Task'));
    fireEvent.click(await screen.findByRole('option', { name: /Active leave plan/i }));
    expect(onSelect).toHaveBeenCalledWith('a');
  });

  it('shows a multi-line scrollable brief in the closed select', () => {
    const long = {
      id: 'long',
      brief: 'Submit an annual leave request for one day on October 7, 2026. Also confirm balance and notify the manager before submitting.',
      status: 'pending_approval',
      created_at: '2026-09-16T10:00:00Z',
    };
    render(<AgentTaskPicker plans={[long]} selectedId="long" onSelect={vi.fn()} />);
    const brief = screen.getByTitle(long.brief);
    expect(brief).toBeInTheDocument();
    expect(brief).toHaveTextContent(/Submit an annual leave request/);
    expect(brief).toHaveTextContent(/notify the manager/);
    expect(brief).toHaveStyle({ maxHeight: '4.05em' });
  });
});
