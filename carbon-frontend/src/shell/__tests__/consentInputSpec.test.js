import { describe, it, expect } from 'vitest';
import { consentFormValid, consentInputSpec } from '../consentInputSpec';

describe('consentInputSpec', () => {
  it('requires hire form when create_employee body is empty', () => {
    const spec = consentInputSpec({
      status: 'awaiting_approval',
      tool_args: { api_name: 'create_employee', body: {} },
    });
    expect(spec).not.toBeNull();
    expect(spec.requiresForm).toBe(true);
    expect(spec.fields.some((f) => f.key === 'employee_no')).toBe(true);
    expect(consentFormValid(spec.fields, {})).toBe(false);
    expect(consentFormValid(spec.fields, {
      employee_no: 'E1',
      full_name: 'Ada',
      org_unit: 1,
      join_date: '2026-09-21',
      basic_salary: '500',
    })).toBe(true);
  });

  it('returns null for non-consent steps', () => {
    expect(consentInputSpec({ status: 'completed', tool_args: { api_name: 'create_employee' } })).toBeNull();
  });
});
