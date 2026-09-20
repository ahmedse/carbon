// src/shell/__tests__/AgentRunToolbar.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentRunToolbar from '../AgentRunToolbar';

const PLAN = {
  id: 'p1',
  brief: 'Build the board pack for Q3.',
  status: 'approved',
};

describe('AgentRunToolbar', () => {
  it('renders under-tab run controls with plan label', () => {
    const onRun = vi.fn();
    render(
      <AgentRunToolbar
        plan={PLAN}
        phase="idle"
        effectiveStatus="approved"
        onRun={onRun}
        onPause={vi.fn()}
        onStop={vi.fn()}
        onRerun={vi.fn()}
        onRetry={vi.fn()}
        onFork={vi.fn()}
      />,
    );
    expect(screen.getByTestId('agent-run-toolbar')).toBeInTheDocument();
    expect(screen.getByTestId('agent-run-label')).toHaveTextContent(/board pack/i);
    fireEvent.click(screen.getByRole('button', { name: /Run plan/i }));
    expect(onRun).toHaveBeenCalled();
  });

  it('shows Edit on Plan and Open Output when settled', () => {
    const onOpenPlan = vi.fn();
    const onOpenOutput = vi.fn();
    render(
      <AgentRunToolbar
        plan={{ ...PLAN, status: 'completed' }}
        phase="finished"
        effectiveStatus="completed"
        onOpenPlan={onOpenPlan}
        onOpenOutput={onOpenOutput}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Edit on Plan/i }));
    expect(onOpenPlan).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Open Output/i }));
    expect(onOpenOutput).toHaveBeenCalled();
  });
});
