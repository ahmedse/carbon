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
  it('shows Start as a word, not a media deck, when the plan is ready', () => {
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
      />,
    );
    expect(screen.getByTestId('agent-run-toolbar')).toBeInTheDocument();
    expect(screen.getByTestId('agent-run-play')).toHaveTextContent(/Start/i);
    expect(screen.queryByTestId('agent-run-pause')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/fork/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('agent-run-play'));
    expect(onRun).toHaveBeenCalled();
  });

  it('shows Pause and Stop as words while working', () => {
    render(
      <AgentRunToolbar
        plan={PLAN}
        phase="working"
        effectiveStatus="running"
        onPause={vi.fn()}
        onStop={vi.fn()}
      />,
    );
    expect(screen.getByTestId('agent-run-pause')).toHaveTextContent(/Pause/i);
    expect(screen.getByTestId('agent-run-stop')).toHaveTextContent(/Stop/i);
    expect(screen.queryByTestId('agent-run-play')).not.toBeInTheDocument();
  });

  it('does not show Edit on Plan or Open Output on the live bar', () => {
    render(
      <AgentRunToolbar
        plan={{ ...PLAN, status: 'completed' }}
        phase="finished"
        effectiveStatus="completed"
        onOpenPlan={vi.fn()}
        onOpenOutput={vi.fn()}
        onRerun={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: /Edit on Plan/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Open Output/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('agent-run-rerun')).toBeInTheDocument();
  });

  it('shows Resume and Cancel when the run is paused, not Stop', () => {
    const onRun = vi.fn();
    const onCancel = vi.fn();
    render(
      <AgentRunToolbar
        plan={{ ...PLAN, status: 'paused' }}
        phase="paused"
        effectiveStatus="paused"
        onRun={onRun}
        onPause={vi.fn()}
        onStop={vi.fn()}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByTestId('agent-run-resume')).toHaveTextContent(/Resume/i);
    expect(screen.getByTestId('agent-run-cancel')).toHaveTextContent(/Cancel run/i);
    expect(screen.queryByTestId('agent-run-stop')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-run-pause')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('agent-run-resume'));
    fireEvent.click(screen.getByTestId('agent-run-cancel'));
    expect(onRun).toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalled();
  });

  it('offers Cancel but not Resume while a step is waiting for approval', () => {
    render(
      <AgentRunToolbar
        plan={{ ...PLAN, status: 'paused' }}
        phase="paused"
        effectiveStatus="paused"
        awaitingConsent
        onRun={vi.fn()}
        onCancel={vi.fn()}
        onStop={vi.fn()}
      />,
    );
    expect(screen.getByTestId('agent-run-cancel')).toBeInTheDocument();
    expect(screen.queryByTestId('agent-run-resume')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-run-stop')).not.toBeInTheDocument();
  });

  it('shows retry only when failed', () => {
    render(
      <AgentRunToolbar
        plan={{ ...PLAN, status: 'failed' }}
        phase="error"
        effectiveStatus="failed"
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByTestId('agent-run-retry')).toBeInTheDocument();
  });
});
