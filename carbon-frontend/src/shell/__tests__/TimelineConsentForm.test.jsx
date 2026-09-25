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

  it('confirms a typed path choice with the picked value', () => {
    const onConfirm = vi.fn();
    render(
      <TimelineConsentForm
        step={{
          step_id: 3,
          status: 'awaiting_approval',
          intent: 'Payroll run details',
          choice: {
            key: 'id',
            options: [
              { value: 30, label: '30 · period_end=2026-09-30' },
              { value: 21, label: '21 · period_end=2026-06-30' },
            ],
          },
        }}
        confirming={false}
        onConfirm={onConfirm}
        onDecline={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('timeline-choice-3-30'));
    fireEvent.click(screen.getByTestId('timeline-approve-3'));
    expect(onConfirm).toHaveBeenCalledWith(3, { body: { id: 30 } });
  });

  it('uses a dropdown when there are many choices and keeps Approve outside it', () => {
    const options = Array.from({ length: 8 }, (_, i) => ({
      value: i + 1,
      label: `period_start=2026-0${(i % 9) + 1}-01 · id=${i + 1}`,
    }));
    render(
      <TimelineConsentForm
        step={{
          step_id: 4,
          status: 'awaiting_approval',
          intent: 'Pick a period',
          choice: { key: 'id', options },
        }}
        confirming={false}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
      />,
    );
    expect(screen.getByTestId('timeline-choice-4-select')).toBeTruthy();
    expect(screen.queryByTestId('timeline-choice-4-1')).toBeNull();
    expect(screen.getByTestId('timeline-approve-4')).toBeDisabled();
  });

  it('lists green evidence and hides the card when a dependency failed', () => {
    const { rerender } = render(
      <TimelineConsentForm
        step={{
          step_id: 6,
          status: 'awaiting_approval',
          intent: 'Board pack',
          tool_name: 'export_document',
          tool_args: { title: 'Board' },
          evidence: [{ step_id: 3, status: 'completed', ok: true }],
        }}
        confirming={false}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
      />,
    );
    expect(screen.getByTestId('timeline-evidence-6')).toHaveTextContent('Step 3: completed');
    rerender(
      <TimelineConsentForm
        step={{
          step_id: 6,
          status: 'awaiting_approval',
          intent: 'Board pack',
          tool_name: 'export_document',
          evidence: [{ step_id: 3, status: 'failed', ok: false }],
        }}
        confirming={false}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('timeline-consent-6')).toBeNull();
  });
});
