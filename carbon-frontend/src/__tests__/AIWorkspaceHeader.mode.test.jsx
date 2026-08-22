// src/__tests__/AIWorkspaceHeader.mode.test.jsx
// W5-A (ADR-0014) — Chat/Agent are the two top-level Pulse modes. The header
// owns the mode buttons AND the always-visible safety-contract text, which
// changes with the agent lifecycle state (§4 of the ADR — exact copy).
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AIWorkspaceHeader from '../shell/AIWorkspaceHeader';

// The context menu is unrelated to the mode/contract surface under test.
vi.mock('../shell/AIContextMenu', () => ({ default: () => null }));

describe('AIWorkspaceHeader mode toggle + safety contract (W5-A / ADR-0014)', () => {
  it('renders the chat contract text by default in Chat mode', () => {
    render(<AIWorkspaceHeader onClose={vi.fn()} />);
    expect(
      screen.getByText(/Answers and advice only\. Nothing is created or changed/i),
    ).toBeInTheDocument();
  });

  it('renders the agent contract text in Agent mode while idle', () => {
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" agentLifecycleState="idle" />);
    expect(
      screen.getByText(/Describe an outcome\. The AI will plan before doing anything/i),
    ).toBeInTheDocument();
  });

  it('renders the plan-pending contract text (nothing runs until approval)', () => {
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" agentLifecycleState="plan_pending" />);
    expect(screen.getByText(/Review the plan\. Nothing runs until you approve/i)).toBeInTheDocument();
  });

  it('renders the running contract text with the pause affordance note', () => {
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" agentLifecycleState="running" />);
    expect(screen.getByText(/Running — Step N of M · Pause anytime/i)).toBeInTheDocument();
  });

  it('renders the consent-needed contract text when a step requires approval', () => {
    render(
      <AIWorkspaceHeader onClose={vi.fn()} mode="agent" agentLifecycleState="consent_needed" />,
    );
    expect(screen.getByText(/Approval needed — A step requires your confirmation/i)).toBeInTheDocument();
  });

  it('renders the done contract text when the run completes', () => {
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" agentLifecycleState="done" />);
    expect(screen.getByText(/Done — Results are ready/i)).toBeInTheDocument();
  });

  it('falls back to the idle contract text for unknown lifecycle states', () => {
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" agentLifecycleState="bogus" />);
    expect(
      screen.getByText(/Describe an outcome\. The AI will plan before doing anything/i),
    ).toBeInTheDocument();
  });

  it('reports a mode change via onModeChange when Agent is clicked', () => {
    const onModeChange = vi.fn();
    render(<AIWorkspaceHeader onClose={vi.fn()} onModeChange={onModeChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Agent mode' }));
    expect(onModeChange).toHaveBeenCalledWith('agent');
  });

  it('reports a mode change via onModeChange when Chat is clicked in Agent mode', () => {
    const onModeChange = vi.fn();
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" onModeChange={onModeChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Chat mode' }));
    expect(onModeChange).toHaveBeenCalledWith('chat');
  });

  it('does not report a change when re-selecting the active mode', () => {
    const onModeChange = vi.fn();
    render(<AIWorkspaceHeader onClose={vi.fn()} mode="agent" onModeChange={onModeChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Agent mode' }));
    expect(onModeChange).not.toHaveBeenCalled();
  });
});
