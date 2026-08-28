// src/__tests__/AIMessageBubble.actions.test.jsx
// Sprint "fly to rule detail" — AI-driven action buttons on assistant bubbles:
//   * navigate action  → in-app Link to the created/found entity
//   * pending_actions  → staged tool executions (Confirm & create / Decline)
//   * proposal review  → expandable Details & JSON + Edit & confirm (modify
//     the staged body before creating)
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

const RULE_BODY = {
  name: 'employee-number',
  rule_type: 'range',
  rule_level: 'field_validation',
  severity: 'error',
  dimension: 'validity',
  is_active: true,
  definition: {
    schema_version: 1,
    name: 'employee-number',
    level: 'field',
    dimension: 'validity',
    type: 'range',
    severity: 'error',
    active: true,
    params: { min: 1000, max: 9999 },
  },
};

const pendingAction = {
  execution_id: 'exec-1',
  tool: 'create_dq_rule',
  confirmation_message: 'Create DQ rule "employee-number" (range)?',
  proposed_rule: RULE_BODY.definition,
  proposed_body: RULE_BODY,
  validation: { passed: true, evaluable: true, explanation: 'all sample rows satisfy the rule' },
};

const pendingMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer.',
  created_at: '2026-08-15T10:00:00Z',
  outcome: null,
  metadata: { pending_actions: [pendingAction] },
};

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
      executeMode: true,
    });
    expect(screen.getByRole('button', { name: /Confirm and create/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument();
  });

  it('renders a memory proposal as Confirm & remember (not a DQ-rule card)', () => {
    const message = {
      ...assistantMessage,
      metadata: {
        pending_actions: [
          {
            kind: 'memory',
            execution_id: 'exec-mem',
            tool: 'learn_fact',
            operation: 'learn',
            fact: 'Ahmed is from Egypt, Alexandria',
            category: 'observation',
            confirmation_message: 'Remember this observation: Ahmed is from Egypt, Alexandria',
          },
        ],
      },
    };
    renderBubble(message, {
      onConfirmExecution: vi.fn(),
      onDeclineExecution: vi.fn(),
      executeMode: true,
    });
    expect(screen.getByRole('button', { name: /Confirm and remember/i })).toBeInTheDocument();
    // No Edit & confirm for a memory write (not a JSON-editable rule body).
    expect(screen.queryByRole('button', { name: /Edit and confirm/i })).not.toBeInTheDocument();

    // Details show the fact, not a fabricated empty rule JSON.
    fireEvent.click(screen.getByRole('button', { name: /Show details/i }));
    expect(screen.getByText('Fact')).toBeInTheDocument();
    expect(screen.queryByText('Proposed rule (definition JSON)')).not.toBeInTheDocument();
    expect(screen.queryByText('Body that will be POSTed')).not.toBeInTheDocument();
  });

  it('derives a legacy memory proposal (no kind tag) from tool/operation', () => {
    // Legacy persisted messages predate the ``kind`` tag — they carry
    // tool/operation but no kind. The card must still render as a memory
    // write, never as an empty DQ-rule card.
    const message = {
      ...assistantMessage,
      metadata: {
        pending_actions: [
          {
            execution_id: 'exec-legacy-mem',
            tool: 'learn_fact',
            operation: 'learn',
            fact: 'Ahmed is from Egypt, Alexandria',
            category: 'observation',
            confirmation_message: 'Remember this observation: Ahmed is from Egypt, Alexandria',
          },
        ],
      },
    };
    renderBubble(message, {
      onConfirmExecution: vi.fn(),
      onDeclineExecution: vi.fn(),
      executeMode: true,
    });
    expect(screen.getByRole('button', { name: /Confirm and remember/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Edit and confirm/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Show details/i }));
    expect(screen.getByText('Fact')).toBeInTheDocument();
    expect(screen.queryByText('Proposed rule (definition JSON)')).not.toBeInTheDocument();
    expect(screen.queryByText('Body that will be POSTed')).not.toBeInTheDocument();
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
    renderBubble(message, { onConfirmExecution, onDeclineExecution: vi.fn(), executeMode: true });
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
    renderBubble(message, { onConfirmExecution: vi.fn(), onDeclineExecution, executeMode: true });
    fireEvent.click(screen.getByRole('button', { name: /Decline/i }));
    expect(onDeclineExecution).toHaveBeenCalledWith('exec-1', expect.any(Object));
  });

  it('renders nothing when metadata has no actions', () => {
    renderBubble(assistantMessage);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Confirm and create/i })).not.toBeInTheDocument();
  });

  it('hides execution buttons and shows a hint when Agent mode is OFF (Ask mode)', () => {
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
    // executeMode defaults to false in renderBubble → Ask mode.
    renderBubble(message, {
      onConfirmExecution: vi.fn(),
      onDeclineExecution: vi.fn(),
    });
    expect(screen.queryByRole('button', { name: /Confirm and create/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Decline/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Agent mode is OFF/i)).toBeInTheDocument();
    // Details & JSON stays available for review.
    expect(screen.getByRole('button', { name: /Show details/i })).toBeInTheDocument();
  });

  it('shows Confirm & remember in Chat mode (memory is not gated by Agent mode)', () => {
    const message = {
      ...assistantMessage,
      metadata: {
        pending_actions: [
          {
            kind: 'memory',
            execution_id: 'exec-mem',
            tool: 'learn_fact',
            operation: 'learn',
            fact: 'Ahmed means the platform when he talks to me',
            category: 'preference',
            confirmation_message: 'Remember this preference: Ahmed means the platform when he talks to me',
          },
        ],
      },
    };
    // executeMode defaults to false (Chat/Ask mode) — memory must still confirm.
    renderBubble(message, {
      onConfirmExecution: vi.fn(),
      onDeclineExecution: vi.fn(),
    });
    expect(screen.getByRole('button', { name: /Confirm and remember/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument();
    expect(screen.queryByText(/Agent mode is OFF/i)).not.toBeInTheDocument();
  });

  // ── Proposal review: details + JSON + modify ─────────────────────────

  it('expands Details & JSON showing definition and POST body', () => {
    renderBubble(pendingMessage, {
      onConfirmExecution: vi.fn(),
      onDeclineExecution: vi.fn(),
    });

    // Hidden until expanded.
    expect(screen.queryByText('Proposed rule (definition JSON)')).not.toBeInTheDocument();
    expect(screen.queryByText('Body that will be POSTed')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Show details/i }));

    expect(screen.getByText('Proposed rule (definition JSON)')).toBeInTheDocument();
    expect(screen.getByText('Body that will be POSTed')).toBeInTheDocument();
    // The definition JSON is rendered (params visible — appears in both blocks).
    expect(screen.getAllByText(/"min": 1000/).length).toBeGreaterThanOrEqual(1);
    // The exact POST body is rendered (only the body carries rule_level).
    expect(screen.getByText(/"rule_level": "field_validation"/)).toBeInTheDocument();
    // Validation outcome surfaces.
    expect(screen.getByText('Preview passed')).toBeInTheDocument();
  });

  it('opens Edit & confirm with the staged body and confirms the edited version', () => {
    const onConfirmExecution = vi.fn();
    renderBubble(pendingMessage, {
      onConfirmExecution,
      onDeclineExecution: vi.fn(),
      executeMode: true,
    });

    fireEvent.click(screen.getByRole('button', { name: /Edit and confirm/i }));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Edit proposed rule — employee-number')).toBeInTheDocument();
    const editor = within(dialog).getByRole('textbox');
    expect(editor.value).toContain('"min": 1000');

    // Modify the max bound and save.
    fireEvent.change(editor, {
      target: { value: editor.value.replace('"max": 9999', '"max": 50000') },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /Save & confirm/i }));

    expect(onConfirmExecution).toHaveBeenCalledTimes(1);
    const [executionId, pending, editedBody] = onConfirmExecution.mock.calls[0];
    expect(executionId).toBe('exec-1');
    expect(pending.execution_id).toBe('exec-1');
    expect(editedBody.definition.params.max).toBe(50000);
    expect(editedBody.name).toBe('employee-number');
  });

  it('shows a JSON error and does not confirm on invalid edits', () => {
    const onConfirmExecution = vi.fn();
    renderBubble(pendingMessage, {
      onConfirmExecution,
      onDeclineExecution: vi.fn(),
      executeMode: true,
    });

    fireEvent.click(screen.getByRole('button', { name: /Edit and confirm/i }));
    const dialog = screen.getByRole('dialog');
    const editor = within(dialog).getByRole('textbox');

    fireEvent.change(editor, { target: { value: '{ not valid json' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Save & confirm/i }));

    expect(within(dialog).getByText(/Invalid JSON/)).toBeInTheDocument();
    expect(onConfirmExecution).not.toHaveBeenCalled();
    // Dialog stays open so the user can fix the JSON.
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('rejects a body missing required fields even when JSON is valid', () => {
    const onConfirmExecution = vi.fn();
    renderBubble(pendingMessage, {
      onConfirmExecution,
      onDeclineExecution: vi.fn(),
      executeMode: true,
    });

    fireEvent.click(screen.getByRole('button', { name: /Edit and confirm/i }));
    const dialog = screen.getByRole('dialog');
    const editor = within(dialog).getByRole('textbox');

    fireEvent.change(editor, { target: { value: '{"name": "x"}' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Save & confirm/i }));

    expect(within(dialog).getByText(/"rule_type"/)).toBeInTheDocument();
    expect(onConfirmExecution).not.toHaveBeenCalled();
  });

  it('cancels the edit dialog without confirming', async () => {
    const onConfirmExecution = vi.fn();
    renderBubble(pendingMessage, {
      onConfirmExecution,
      onDeclineExecution: vi.fn(),
      executeMode: true,
    });

    fireEvent.click(screen.getByRole('button', { name: /Edit and confirm/i }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /^Cancel$/ }));

    expect(onConfirmExecution).not.toHaveBeenCalled();
    // MUI Dialog animates out — wait for it to unmount.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('renders an "Open in Tasks" button for an open_panel action and calls onOpenPanel', () => {
    const onOpenPanel = vi.fn();
    renderBubble(
      {
        id: 'msg-plan',
        role: 'assistant',
        content: '✅ Plan 7a0c10ae drafted — nothing has run yet.',
        created_at: '2026-08-15T10:00:00Z',
        outcome: null,
        metadata: {
          action: {
            type: 'open_panel',
            panel: 'tasks',
            plan_id: '7a0c10ae',
            label: 'Open in Tasks',
            summary: 'Review, approve and run the plan',
          },
        },
      },
      { onOpenPanel },
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open in Tasks' }));
    expect(onOpenPanel).toHaveBeenCalledWith('tasks', '7a0c10ae');
  });

  it('does not render an open_panel button when no handler is wired', () => {
    renderBubble({
      id: 'msg-plan-2',
      role: 'assistant',
      content: '✅ Plan 8b1d22af drafted — nothing has run yet.',
      created_at: '2026-08-15T10:00:00Z',
      outcome: null,
      metadata: {
        action: { type: 'open_panel', panel: 'tasks', plan_id: '8b1d22af', label: 'Open in Tasks' },
      },
    });

    const button = screen.getByRole('button', { name: 'Open in Tasks' });
    expect(button).toBeDisabled();
  });
});
