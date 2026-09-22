import { describe, it, expect } from 'vitest';
import {
  bodySummary,
  consentFormValid,
  consentInputSpec,
  firstMissingField,
} from '../consentInputSpec';

const LEAVE_SLOTS = [
  {
    field: 'leave_type',
    label: 'Leave Type',
    type: 'governed',
    required: true,
    options: [
      { code: 'annual', label: 'Annual Leave' },
      { code: 'emergency', label: 'Emergency Leave' },
    ],
  },
  { field: 'start_date', label: 'Start Date', type: 'date', required: true },
  { field: 'days', label: 'Days', type: 'days', required: true },
];

describe('consentInputSpec', () => {
  it('reads fields and governed options from the step slots', () => {
    const spec = consentInputSpec({
      status: 'awaiting_approval',
      consent_slots: LEAVE_SLOTS,
      tool_args: { api_name: 'submit_my_leave', body: {} },
    });
    expect(spec.fields.map((f) => f.key)).toEqual(['leave_type', 'start_date', 'days']);
    expect(spec.fields[0].options).toEqual([
      { value: 'annual', label: 'Annual Leave' },
      { value: 'emergency', label: 'Emergency Leave' },
    ]);
    expect(spec.prefilled).toBe(false);
  });

  it('asks nothing when the platform already resolved every slot', () => {
    const body = { leave_type: 'annual', start_date: '2026-10-01', days: 1 };
    const spec = consentInputSpec({
      status: 'awaiting_approval',
      consent_slots: LEAVE_SLOTS,
      tool_args: { api_name: 'submit_my_leave', body },
    });
    expect(spec.prefilled).toBe(true);
    expect(firstMissingField(spec.fields, spec.values)).toBeNull();
    expect(bodySummary(spec.fields, spec.values)).toBe(
      'Leave Type: Annual Leave · Start Date: 2026-10-01 · Days: 1',
    );
  });

  it('asks only for the first genuinely missing slot', () => {
    const spec = consentInputSpec({
      status: 'awaiting_approval',
      consent_slots: LEAVE_SLOTS,
      tool_args: {
        api_name: 'submit_my_leave',
        body: { leave_type: 'annual', days: 1 },
      },
    });
    expect(firstMissingField(spec.fields, spec.values).key).toBe('start_date');
    expect(consentFormValid(spec.fields, spec.values)).toBe(false);
  });

  it('returns null without slots or for non-consent steps', () => {
    expect(
      consentInputSpec({
        status: 'awaiting_approval',
        tool_args: { api_name: 'submit_my_leave', body: {} },
      }),
    ).toBeNull();
    expect(
      consentInputSpec({
        status: 'completed',
        consent_slots: LEAVE_SLOTS,
        tool_args: { api_name: 'submit_my_leave' },
      }),
    ).toBeNull();
  });
});
