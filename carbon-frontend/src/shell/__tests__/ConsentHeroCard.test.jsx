import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ConsentHeroCard from '../ConsentHeroCard';
import { stripEngineJargon } from '../humanizeOperatorCopy';

describe('stripEngineJargon', () => {
  it('strips RULE_xx tokens', () => {
    expect(stripEngineJargon('deny under RULE_21 consent')).toBe('deny under consent');
  });

  it('humanizes snake_case tool ids toward outcome language', () => {
    expect(stripEngineJargon('call_host_api for leave')).toMatch(/system check/i);
    expect(stripEngineJargon('call_host_api for leave')).not.toMatch(/call_host_api/);
  });
});

describe('ConsentHeroCard', () => {
  const step = {
    step_id: 8,
    status: 'awaiting_approval',
    intent: 'Deny compensation request CR-4412 under RULE_21',
  };

  it('renders status strip without Approve/Decline buttons', () => {
    render(
      <ConsentHeroCard
        step={step}
        completedLabel="8 steps completed, 2 to go"
      />,
    );
    expect(screen.getByTestId('consent-hero-card')).toBeInTheDocument();
    expect(screen.getByTestId('consent-hero-card')).toHaveAttribute('data-consent-mode', 'status-strip');
    expect(screen.getByText(/Needs your approval/)).toBeInTheDocument();
    expect(screen.getByText(/Paused — 8 steps completed/)).toBeInTheDocument();
    expect(screen.queryByText(/RULE_21/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Decline' })).not.toBeInTheDocument();
  });

  it('returns null when step is not awaiting approval', () => {
    const { container } = render(
      <ConsentHeroCard
        step={{ ...step, status: 'completed' }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('links to the step details panel where approve/decline live', () => {
    const onReview = vi.fn();
    render(
      <ConsentHeroCard step={step} onReviewStep={onReview} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Open step details/i }));
    expect(onReview).toHaveBeenCalled();
  });

  it('names the host write from api_name, never System check', () => {
    render(
      <ConsentHeroCard
        step={{
          ...step,
          tool_name: 'call_host_api',
          tool_args: { api_name: 'submit_my_leave', body: { leave_type: 'annual' } },
        }}
      />,
    );
    expect(screen.getByTestId('consent-hero-card')).toHaveTextContent(/Submit leave request/i);
    expect(screen.getByTestId('consent-hero-card')).not.toHaveTextContent(/System check/i);
  });
});
