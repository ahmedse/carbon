// src/__tests__/ReasoningTrace.test.jsx
// Wave D3 — on-click "why this answer": the trigger is a real button with the
// required aria-label; clicking reveals sources/tools/freshness in outcome
// language; internal leakage (engine_turn_id, token counts) is filtered out.
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ReasoningTrace from '../shell/ReasoningTrace';

function openTrace(props) {
  render(<ReasoningTrace {...props} />);
  fireEvent.click(screen.getByLabelText('Why this answer'));
}

describe('ReasoningTrace trigger', () => {
  it('renders a trigger with aria-label="Why this answer"', () => {
    render(<ReasoningTrace />);

    expect(screen.getByLabelText('Why this answer')).toBeInTheDocument();
  });
});

describe('ReasoningTrace panel', () => {
  it('reveals sources, tools, and data freshness on click', () => {
    openTrace({
      lines: ['Knowledge Graph: monthly_electricity, emission_factors'],
      actions: [{ label: 'Open rule detail' }],
      pendingActions: [{ confirmation_message: 'Create a DQ rule' }],
      createdAt: '2026-08-16T10:00:00Z',
    });

    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Graph: monthly_electricity, emission_factors')).toBeInTheDocument();
    expect(screen.getByText('Tools used')).toBeInTheDocument();
    expect(screen.getByText('Open rule detail')).toBeInTheDocument();
    expect(screen.getByText('Create a DQ rule')).toBeInTheDocument();
    expect(screen.getByText('Data freshness')).toBeInTheDocument();
  });

  it('does not render engine_turn_id or token text when passed raw-ish lines', () => {
    openTrace({
      lines: [
        'Model: gpt-4o',
        'Turn: engine_turn_abc123',
        'Context: History 120 tok · KG Retrieval 340 tok',
        'Knowledge Graph: monthly_electricity',
      ],
    });

    expect(screen.queryByText(/engine_turn_abc123/)).not.toBeInTheDocument();
    expect(screen.queryByText(/tok/)).not.toBeInTheDocument();
    // Outcome-shaped lines still pass through.
    expect(screen.getByText('Knowledge Graph: monthly_electricity')).toBeInTheDocument();
  });

  it('omits the tools row when there are no tools', () => {
    openTrace({ lines: ['Org units: 3'] });

    expect(screen.queryByText('Tools used')).not.toBeInTheDocument();
    expect(screen.getByText('Org units: 3')).toBeInTheDocument();
  });
});
