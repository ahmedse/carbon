// src/__tests__/NLRuleTestCard.test.jsx
// Phase 8-B — NL Rule Test card: rule preview, pass-rate summary, local
// threshold re-scoring, and Execute-Mode-gated Save.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import NLRuleTestCard from '../shell/NLRuleTestCard';

// Real Phase 8-A backend contract shape.
const metadata = {
  type: 'nl_rule_test',
  rule_preview: {
    type: 'threshold',
    params: { operator: 'gte', value: 80 },
    severity: 'warn',
    confidence: 0.84,
    field: 'total_kwh',
    rule_text: 'Monthly electricity ≥ 80% of prior year',
  },
  test_summary: {
    total_rows: 3,
    applicable_rows: 3,
    passed: 1,
    failed: 2,
    pass_rate: 0.333,
  },
  violations: [
    { row: 2, value: 41200 },
    { row: 3, value: 38900 },
  ],
  rows: [{ actual: 47800 }, { actual: 41200 }, { actual: 38900 }],
  recommendation: 'Review the violations before saving the rule.',
};

function renderCard(props = {}) {
  return render(<NLRuleTestCard metadata={metadata} {...props} />);
}

describe('NLRuleTestCard rendering', () => {
  it('renders rule preview and test summary', () => {
    renderCard();

    expect(screen.getByText('Monthly electricity ≥ 80% of prior year')).toBeInTheDocument();
    expect(screen.getByText('Threshold')).toBeInTheDocument();
    expect(screen.getByText('Severity: Warning')).toBeInTheDocument();
    expect(screen.getByText(/Pass rate: 33%/)).toBeInTheDocument();
    expect(screen.getByText(/1\/3 applicable rows passed/)).toBeInTheDocument();
    expect(screen.getByText(/2 violations/)).toBeInTheDocument();
    expect(screen.getByText('Review the violations before saving the rule.')).toBeInTheDocument();
  });

  it('re-scores the pass rate locally when the threshold slider is dragged', async () => {
    renderCard({ executeMode: false });

    const slider = screen.getByRole('slider', { name: 'Adjust threshold' });
    fireEvent.change(slider, { target: { value: 40 } });

    await screen.findByText(/Pass rate: 100%/);
    expect(screen.getByText(/3\/3 applicable rows passed/)).toBeInTheDocument();
  });
});

describe('NLRuleTestCard save gating', () => {
  it('disables Save Rule with a tooltip when Execute Mode is off', async () => {
    renderCard({ executeMode: false });

    const saveButton = screen.getByRole('button', { name: 'Save Rule' });
    expect(saveButton).toBeDisabled();

    fireEvent.mouseOver(saveButton);
    await screen.findByText('Enable Execute Mode to save');
  });

  it('calls onSave when Execute Mode is on and Save Rule is clicked', async () => {
    const onSave = vi.fn().mockResolvedValue({ id: 1, name: 'Monthly electricity ≥ 80%' });
    renderCard({ executeMode: true, onSave });

    const saveButton = screen.getByRole('button', { name: 'Save Rule' });
    expect(saveButton).toBeEnabled();

    fireEvent.click(saveButton);

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'threshold',
        params: { operator: 'gte', value: 80 },
        severity: 'warn',
        field: 'total_kwh',
      }),
    );
  });

  it('shows a Saved ✓ chip after a successful save', async () => {
    const onSave = vi.fn().mockResolvedValue({ id: 1, name: 'Monthly electricity ≥ 80%' });
    renderCard({ executeMode: true, onSave });

    fireEvent.click(screen.getByRole('button', { name: 'Save Rule' }));

    await screen.findByText('Saved ✓');
    expect(screen.queryByRole('button', { name: 'Save Rule' })).not.toBeInTheDocument();
  });
});
