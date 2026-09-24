import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import TimelineConsentForm from '../TimelineConsentForm';

const LOAN_SLOTS = [
  {
    field: 'loan_type',
    label: 'Loan Type',
    type: 'governed',
    required: true,
    options: [
      { code: 'personal', label: 'Personal Loan' },
      { code: 'emergency', label: 'Emergency Loan' },
    ],
  },
  { field: 'principal', label: 'Principal', type: 'number', required: true },
  { field: 'term_months', label: 'Term Months', type: 'number', required: true },
];

function loanStep(overrides = {}) {
  return {
    step_id: 2,
    intent: 'Submit loan request',
    status: 'awaiting_approval',
    tool_name: 'call_host_api',
    consent_slots: LOAN_SLOTS,
    tool_args: {
      api_name: 'submit_my_loan',
      body: {
        principal: 500,
        term_months: 12,
        interest_rate: 0,
      },
    },
    ...overrides,
  };
}

describe('TimelineConsentForm', () => {
  it('keeps a loan-type chip selection across poll identity refreshes', () => {
    const onConfirm = vi.fn();
    const { rerender } = render(
      <TimelineConsentForm
        step={loanStep()}
        confirming={false}
        onConfirm={onConfirm}
        onDecline={vi.fn()}
      />,
    );

    expect(screen.getByTestId('timeline-consent-2')).toHaveAttribute(
      'data-consent-mode',
      'ask',
    );
    fireEvent.click(screen.getByTestId('consent-ask-loan_type-personal'));

    expect(screen.getByTestId('timeline-consent-2')).toHaveAttribute(
      'data-consent-mode',
      'summary',
    );
    expect(screen.getByTestId('timeline-approve-2')).not.toBeDisabled();

    // Quiet plan poll rebuilds arrays/objects with the same content.
    rerender(
      <TimelineConsentForm
        step={loanStep({
          consent_slots: LOAN_SLOTS.map((slot) => ({ ...slot })),
          tool_args: {
            api_name: 'submit_my_loan',
            body: {
              principal: 500,
              term_months: 12,
              interest_rate: 0,
            },
          },
        })}
        confirming={false}
        onConfirm={onConfirm}
        onDecline={vi.fn()}
      />,
    );

    expect(screen.getByTestId('timeline-consent-2')).toHaveAttribute(
      'data-consent-mode',
      'summary',
    );
    expect(screen.getByTestId('timeline-approve-2')).not.toBeDisabled();
    fireEvent.click(screen.getByTestId('timeline-approve-2'));
    expect(onConfirm).toHaveBeenCalledWith(2, {
      body: expect.objectContaining({
        loan_type: 'personal',
        principal: 500,
        term_months: 12,
      }),
    });
  });
});
