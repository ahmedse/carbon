import { describe, it, expect } from 'vitest';
import {
  bodySummary,
  changePreview,
  consentFormValid,
  consentInputSpec,
  consequenceForApi,
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
    expect(spec.actionLabel).toMatch(/leave/i);
    expect(spec.actionLabel).not.toMatch(/system check/i);
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
    expect(spec.rows).toEqual([
      { label: 'Leave Type', value: 'Annual Leave' },
      { label: 'Start Date', value: '2026-10-01' },
      { label: 'Days', value: '1' },
    ]);
    expect(spec.consequence).toMatch(/Creates a leave request/i);
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

  it('falls back to body keys when consent_slots were omitted', () => {
    const body = { leave_type: 'annual', start_date: '2026-09-23', days: 1 };
    const spec = consentInputSpec({
      status: 'awaiting_approval',
      tool_args: { api_name: 'submit_my_leave', body },
    });
    expect(spec).not.toBeNull();
    expect(spec.prefilled).toBe(true);
    expect(spec.rows.map((r) => r.label)).toEqual(['Leave type', 'Start date', 'Days']);
    expect(changePreview({
      status: 'awaiting_approval',
      tool_args: { api_name: 'submit_my_leave', body },
    }).summary).toMatch(/annual/i);
  });

  it('still returns an action preview when body is empty but api is known', () => {
    const spec = consentInputSpec({
      status: 'awaiting_approval',
      tool_args: { api_name: 'submit_my_leave', body: {} },
    });
    expect(spec).not.toBeNull();
    expect(spec.actionLabel).toMatch(/leave/i);
    expect(spec.consequence).toBe(consequenceForApi('submit_my_leave'));
    expect(spec.requiresForm).toBe(false);
  });

  it('returns null for non-consent steps', () => {
    expect(
      consentInputSpec({
        status: 'completed',
        consent_slots: LEAVE_SLOTS,
        tool_args: { api_name: 'submit_my_leave' },
      }),
    ).toBeNull();
  });
});
