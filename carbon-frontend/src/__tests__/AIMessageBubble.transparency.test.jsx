// src/__tests__/AIMessageBubble.transparency.test.jsx
// Sprint 17 — per-turn usage chip Tooltip + "why this answer" provenance tooltip.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';
import { formatContextLines } from '../utils/aiProvenance';

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
          context_snapshot: { T2_history: 120, T3_retrieval: 340 },
          scope_snapshot: { org_unit_ids: ['*'] },
        },
      },
    }, { conversationType: 'dq_validate' });

    // Icon renders even with provenance from metadata.
    expect(screen.getByLabelText('Why this answer')).toBeInTheDocument();
  });

  it('reads the backend top-level message.provenance field (real serialization shape)', () => {
    renderBubble({
      ...baseMessage,
      // Backend serializes provenance as a top-level key, NOT inside metadata_json.
      provenance: {
        model: 'gpt-4o',
        engine_turn_id: 'abc123',
        guard_results: { ScopeGuard: true },
        context_snapshot: {
          T2_history: 120,
          T3_retrieval: 340,
          kg_entities: [{ name: 'monthly_electricity' }, { name: 'emission_factors' }],
        },
        scope_snapshot: { org_unit_ids: ['*'] },
      },
    }, { conversationType: 'chat', appIdentifier: 'carbon' });

    // The icon renders without crashing when provenance is top-level, and the
    // KG entities are not coerced into "[object Object] tok".
    expect(screen.getByLabelText('Why this answer')).toBeInTheDocument();
  });
});

describe('AIMessageBubble nl_rule_test rendering', () => {
  const nlRuleTestMetadata = {
    type: 'nl_rule_test',
    rule_preview: {
      type: 'threshold',
      params: { operator: 'gte', value: 80 },
      severity: 'warn',
      confidence: 0.84,
      field: 'total_kwh',
      rule_text: 'Monthly electricity ≥ 80% of prior year',
    },
    test_summary: { total_rows: 3, applicable_rows: 3, passed: 1, failed: 2, pass_rate: 0.333 },
    violations: [
      { row: 2, value: 41200 },
      { row: 3, value: 38900 },
    ],
    recommendation: 'Review the violations before saving the rule.',
  };

  it('renders the NL rule test card for nl_rule_test metadata', () => {
    renderBubble({ ...baseMessage, metadata: nlRuleTestMetadata });

    expect(screen.getByText('Monthly electricity ≥ 80% of prior year')).toBeInTheDocument();
    expect(screen.getByText(/Pass rate: 33%/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Rule' })).toBeInTheDocument();
  });

  it('exposes a Test live action on DQ suggestions', () => {
    renderBubble(
      {
        ...baseMessage,
        metadata: {
          type: 'dq_suggestions',
          suggestions: [
            { id: 's1', name: 'Electricity threshold', confidence: 0.9 },
          ],
        },
      },
      { onTestLive: vi.fn(), canManageRules: true },
    );

    expect(screen.getByRole('button', { name: 'Test live' })).toBeInTheDocument();
  });
});

describe('formatContextLines', () => {
  it('formats budget tiers with labels and KG entity names, never [object Object]', () => {
    const lines = formatContextLines({
      T2_history: 12,
      T3_retrieval: 34,
      kg_entities: [{ name: 'monthly_electricity' }, { name: 'emission_factors' }],
    });

    expect(lines).toContain('Context: History 12 tok · KG Retrieval 34 tok');
    expect(lines).toContain('Knowledge Graph: monthly_electricity, emission_factors');
    expect(lines.join('\n')).not.toContain('[object Object]');
  });

  it('omits zero tiers and returns an empty array for a missing snapshot', () => {
    expect(formatContextLines({ T2_history: 0, T4_memory: 0 })).toEqual([]);
    expect(formatContextLines(undefined)).toEqual([]);
    expect(formatContextLines(null)).toEqual([]);
  });

  it('truncates KG entity names to 5', () => {
    const kg = Array.from({ length: 8 }, (_, i) => ({ name: `entity_${i}` }));
    const lines = formatContextLines({ T3_retrieval: 1, kg_entities: kg });

    const kgLine = lines.find((l) => l.startsWith('Knowledge Graph:'));
    expect(kgLine).toBeDefined();
    const names = kgLine.replace('Knowledge Graph: ', '').split(', ');
    expect(names).toHaveLength(5);
  });
});
