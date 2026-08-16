// src/__tests__/InvestigationCard.test.jsx
// Phase 9-B — InvestigationCard: summary, plan steps, severity-tinted findings,
// and per-finding / card-level actions.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import InvestigationCard from '../shell/InvestigationCard';

const baseMetadata = {
  type: 'investigation',
  table_id: 7,
  table_name: 'emissions',
  summary: 'A single DQ rule failed on 1 of 1 rows.',
  plan_steps: [
    { step: 1, label: 'Profile table', status: 'done', detail: '10 rows · 3 fields' },
    { step: 2, label: 'Evaluate DQ rules', status: 'done', detail: '1 rules run · 1 failed' },
    { step: 3, label: 'Detect anomalies', status: 'done', detail: '0 anomalies' },
    { step: 4, label: 'Retrieve knowledge graph', status: 'done', detail: '2 entities' },
    { step: 5, label: 'Synthesize findings', status: 'done', detail: 'Synthesis complete.' },
  ],
  findings: [
    {
      severity: 'high',
      title: "DQ rule 'email required' failed",
      detail: '1 of 1 applicable row(s) violated rule.',
      recommended_action: 'Review the failing rows.',
      entity_ref: 'email',
    },
    {
      severity: 'low',
      title: 'Anomaly: row_count',
      detail: 'Detected an anomalous value.',
      recommended_action: 'Investigate this anomaly.',
      entity_ref: 'emissions.row_count',
    },
  ],
  counts: { rules_run: 1, rules_failed: 1, anomalies: 0, kg_entities: 2 },
};

describe('InvestigationCard rendering', () => {
  it('renders the summary and plan steps', () => {
    render(<InvestigationCard metadata={baseMetadata} />);

    expect(screen.getByText('Investigation: emissions')).toBeInTheDocument();
    expect(screen.getByText('A single DQ rule failed on 1 of 1 rows.')).toBeInTheDocument();
    expect(screen.getByText('Profile table')).toBeInTheDocument();
    expect(screen.getByText('Evaluate DQ rules')).toBeInTheDocument();
    expect(screen.getByText('Detect anomalies')).toBeInTheDocument();
    expect(screen.getByText('Retrieve knowledge graph')).toBeInTheDocument();
    expect(screen.getByText('Synthesize findings')).toBeInTheDocument();
  });

  it('renders findings tinted by severity', () => {
    render(<InvestigationCard metadata={baseMetadata} />);

    expect(screen.getByText("DQ rule 'email required' failed")).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
    // Medium is the default when severity is absent/unmapped.
    expect(screen.queryByText('Medium')).not.toBeInTheDocument();
  });

  it('marks an llm_unavailable step with a warning chip', () => {
    const metadata = {
      ...baseMetadata,
      plan_steps: [
        { step: 5, label: 'Synthesize findings', status: 'llm_unavailable', detail: 'LLM unavailable.' },
      ],
    };

    render(<InvestigationCard metadata={metadata} />);

    expect(screen.getByText('Synthesis unavailable')).toBeInTheDocument();
  });

  it('calls onChatAbout and onCreateRule with the finding', () => {
    const onChatAbout = vi.fn();
    const onCreateRule = vi.fn();
    render(
      <InvestigationCard
        metadata={baseMetadata}
        onChatAbout={onChatAbout}
        onCreateRule={onCreateRule}
      />,
    );

    const chatButtons = screen.getAllByRole('button', { name: 'Chat about this' });
    fireEvent.click(chatButtons[0]);
    expect(onChatAbout).toHaveBeenCalledWith(baseMetadata.findings[0]);

    const createButtons = screen.getAllByRole('button', { name: 'Create rule' });
    fireEvent.click(createButtons[0]);
    expect(onCreateRule).toHaveBeenCalledWith(baseMetadata.findings[0]);
  });

  it('calls onRerun when the Re-run action is clicked', () => {
    const onRerun = vi.fn();
    render(<InvestigationCard metadata={baseMetadata} onRerun={onRerun} />);

    fireEvent.click(screen.getByRole('button', { name: 'Re-run' }));
    expect(onRerun).toHaveBeenCalledTimes(1);
  });

  it('dismisses a finding client-side without a handler', () => {
    render(<InvestigationCard metadata={baseMetadata} />);

    expect(screen.getByText("DQ rule 'email required' failed")).toBeInTheDocument();
    const dismissButtons = screen.getAllByRole('button', { name: 'Dismiss' });
    fireEvent.click(dismissButtons[0]);

    expect(screen.queryByText("DQ rule 'email required' failed")).not.toBeInTheDocument();
    // The second finding remains.
    expect(screen.getByText('Anomaly: row_count')).toBeInTheDocument();
  });
});
