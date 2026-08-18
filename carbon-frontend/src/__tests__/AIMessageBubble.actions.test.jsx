// src/__tests__/AIMessageBubble.actions.test.jsx
// Sprint "fly to rule detail" — AI-driven action buttons on assistant bubbles:
//   * navigate action  → in-app Link to the created/found entity
//   * pending_actions  → staged tool executions (Confirm & create / Decline)
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

const assistantMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer.',
  created_at: '2026-08-15T10:00:00Z',
  outcome: null,
};

function renderBubble(message, props = {}) {
  return render(
    <MemoryRouter>
      <AIMessageBubble message={message} {...props} />
    </MemoryRouter>,
  );
}

describe('AIMessageBubble AI-driven actions', () => {
  it('renders a navigate Link from metadata.action when safe', () => {
    const message = {
      ...assistantMessage,
      metadata: {
        action: {
          type: 'navigate',
          route: '/dq/rules/abc-123',
          label: 'View rule',
          summary: 'Rule created.',
        },
      },
    };
    renderBubble(message);
    const link = screen.getByRole('link', { name: 'View rule' });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute('href')).toBe('/dq/rules/abc-123');
  });

  it('does not render a navigate Link for unsafe routes', () => {
    const message = {
      ...assistantMessage,
      metadata: {
        action: {
          type: 'navigate',
          route: 'https://evil.example',
          label: 'View rule',
        },
      },
    };
    renderBubble(message);
    expect(screen.queryByRole('link', { name: 'View rule' })).not.toBeInTheDocument();
  });

  it('renders Confirm & create / Decline for a pending action', () => {
    const message = {
      ...assistantMessage,
      metadata: {
        pending_actions: [
          {
            execution_id: 'exec-1',
            tool: 'create_dq_rule',
            confirmation_message: 'Create DQ rule "employee-number" (range)?',
            proposed_rule: { name: 'employee-number' },
          },
        ],
      },
    };
    renderBubble(message, {
      onConfirmExecution: vi.fn(),
      onDeclineExecution: vi.fn(),
    });
    expect(screen.getByRole('button', { name: /Confirm and create/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument();
  });

  it('calls onConfirmExecution with the execution id', () => {
    const onConfirmExecution = vi.fn();
    const message = {
      ...assistantMessage,
      metadata: {
        pending_actions: [
          {
            execution_id: 'exec-1',
            tool: 'create_dq_rule',
            confirmation_message: 'Create DQ rule "employee-number" (range)?',
            proposed_rule: { name: 'employee-number' },
          },
        ],
      },
    };
    renderBubble(message, { onConfirmExecution, onDeclineExecution: vi.fn() });
    fireEvent.click(screen.getByRole('button', { name: /Confirm and create/i }));
    expect(onConfirmExecution).toHaveBeenCalledWith('exec-1', expect.any(Object));
  });

  it('calls onDeclineExecution with the execution id', () => {
    const onDeclineExecution = vi.fn();
    const message = {
      ...assistantMessage,
      metadata: {
        pending_actions: [
          {
            execution_id: 'exec-1',
            tool: 'create_dq_rule',
            confirmation_message: 'Create DQ rule "employee-number" (range)?',
            proposed_rule: { name: 'employee-number' },
          },
        ],
      },
    };
    renderBubble(message, { onConfirmExecution: vi.fn(), onDeclineExecution });
    fireEvent.click(screen.getByRole('button', { name: /Decline/i }));
    expect(onDeclineExecution).toHaveBeenCalledWith('exec-1', expect.any(Object));
  });

  it('renders nothing when metadata has no actions', () => {
    renderBubble(assistantMessage);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Confirm and create/i })).not.toBeInTheDocument();
  });
});
