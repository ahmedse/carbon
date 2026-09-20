import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ConsentHeroCard from '../ConsentHeroCard';
import { stripEngineJargon } from '../humanizeOperatorCopy';

describe('stripEngineJargon', () => {
  it('strips RULE_xx tokens', () => {
    expect(stripEngineJargon('deny under RULE_21 consent')).toBe('deny under consent');
  });

  it('humanizes snake_case tool ids', () => {
    expect(stripEngineJargon('call_host_api for leave')).toMatch(/call host api/i);
  });
});

describe('ConsentHeroCard', () => {
  const step = {
    step_id: 8,
    status: 'awaiting_approval',
    intent: 'Deny compensation request CR-4412 under RULE_21',
  };

  it('renders above-fold Approve/Decline without engine rule ids', () => {
    const onConfirm = vi.fn();
    const onDecline = vi.fn();
    render(
      <ConsentHeroCard
        step={step}
        onConfirm={onConfirm}
        onDecline={onDecline}
        completedLabel="8 steps completed, 2 to go"
      />,
    );
    expect(screen.getByTestId('consent-hero-card')).toBeInTheDocument();
    expect(screen.getByText(/Paused — 8 steps completed/)).toBeInTheDocument();
    expect(screen.queryByText(/RULE_21/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(onConfirm).toHaveBeenCalledWith(8);
    fireEvent.click(screen.getByRole('button', { name: 'Decline' }));
    expect(onDecline).toHaveBeenCalledWith(8);
  });

  it('returns null when step is not awaiting approval', () => {
    const { container } = render(
      <ConsentHeroCard
        step={{ ...step, status: 'completed' }}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
