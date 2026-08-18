// src/__tests__/AIStatusBar.test.jsx
// Phase 17-B — AI Workspace status bar (footer, under the input area).
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AIStatusBar from '../shell/AIStatusBar';

describe('AIStatusBar', () => {
  it('renders the ready state with no retry affordance', () => {
    render(<AIStatusBar variant="ready" label="Ready" />);
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('renders the working state', () => {
    render(<AIStatusBar variant="working" label="Working…" />);
    expect(screen.getByText('Working…')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('renders a transient error with a retry button that fires onRetry', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <AIStatusBar
        variant="transient"
        label="Couldn't reach the AI service — tap to retry"
        onRetry={onRetry}
      />,
    );
    expect(
      screen.getByText("Couldn't reach the AI service — tap to retry"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders the offline state with a retry button', () => {
    render(<AIStatusBar variant="offline" label="AI service is offline" onRetry={vi.fn()} />);
    expect(screen.getByText('AI service is offline')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});
