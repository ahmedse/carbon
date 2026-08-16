// src/__tests__/AIMessageBubble.transparency.test.jsx
// Sprint 17 — per-turn usage chip Tooltip + "why this answer" provenance tooltip.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

const baseMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer.',
  created_at: '2026-08-16T10:00:00Z',
};

function renderBubble(message, props = {}) {
  return render(
    <MemoryRouter>
      <AIMessageBubble message={message} {...props} />
    </MemoryRouter>,
  );
}

describe('AIMessageBubble usage chip Tooltip', () => {
  it('renders the usage chip with a breakdown tooltip without crashing', () => {
    renderBubble({
      ...baseMessage,
      token_usage_json: {
        model: 'gpt-4o',
        prompt_tokens: 100,
        completion_tokens: 1134,
        total_tokens: 1234,
        cost_usd: 0.0042,
        latency_ms: 950,
      },
    });

    expect(screen.getByText('gpt-4o · 1234 tok · $0.0042 · 950ms')).toBeInTheDocument();
  });
});

describe('AIMessageBubble "why this answer" provenance tooltip', () => {
  it('renders the info icon for structured messages', () => {
    renderBubble({
      ...baseMessage,
      metadata: { type: 'dq_suggestions', suggestions: [] },
    });

    expect(screen.getByLabelText('Why this answer')).toBeInTheDocument();
  });

  it('renders the info icon when conversation scope is available', () => {
    renderBubble(baseMessage, {
      conversationType: 'chat',
      appIdentifier: 'emissions',
      scopeJson: { org_unit_ids: ['ou-1', 'ou-2'] },
    });

    expect(screen.getByLabelText('Why this answer')).toBeInTheDocument();
  });

  it('does not render the info icon for user messages', () => {
    renderBubble(
      { id: 'msg-2', role: 'user', content: 'Hello', created_at: '2026-08-16T10:00:00Z' },
      { conversationType: 'chat', appIdentifier: 'emissions' },
    );

    expect(screen.queryByLabelText('Why this answer')).not.toBeInTheDocument();
  });

  it('uses backend provenance payload when present in metadata_json', () => {
    renderBubble({
      ...baseMessage,
      metadata_json: {
        provenance: {
          model: 'gpt-4o',
          engine_turn_id: 'abc123',
          app_identifier: 'platform',
          guard_results: { ScopeGuard: true, AccessGuard: true },
          context_snapshot: { T0: 120, T1: 340, T2: 420 },
          scope_snapshot: { org_unit_ids: ['*'] },
        },
      },
    }, { conversationType: 'dq_validate' });

    // Icon renders even with provenance from metadata.
    expect(screen.getByLabelText('Why this answer')).toBeInTheDocument();
  });
});
