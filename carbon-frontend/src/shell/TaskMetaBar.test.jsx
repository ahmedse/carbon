import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import TaskMetaBar from './TaskMetaBar';

describe('TaskMetaBar', () => {
  it('shows created, ran, and who', () => {
    render(
      <TaskMetaBar
        plan={{
          created_at: '2026-09-27T09:00:00+03:00',
          completed_at: '2026-09-27T09:02:12+03:00',
          created_by: { display_name: 'Ali Mohamed (emp_2378)' },
        }}
      />,
    );
    const bar = screen.getByTestId('task-meta-bar');
    expect(bar).toHaveTextContent(/Created/);
    expect(bar).toHaveTextContent(/Ran/);
    expect(bar).toHaveTextContent('Ali Mohamed (emp_2378)');
    expect(bar).not.toHaveTextContent(/Not run/);
  });

  it('says not run when the task has never finished', () => {
    render(
      <TaskMetaBar
        plan={{
          created_at: '2026-09-27T09:00:00+03:00',
          created_by: { display_name: 'Plan Worker' },
        }}
      />,
    );
    expect(screen.getByTestId('task-meta-bar')).toHaveTextContent(/Not run yet/);
  });

  it('hides when there is nothing to show', () => {
    const { container } = render(<TaskMetaBar plan={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
