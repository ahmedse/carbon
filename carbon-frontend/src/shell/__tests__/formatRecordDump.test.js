import { describe, expect, it } from 'vitest';
import { dumpBlockToTable, presentRecordDump } from '../formatRecordDump';

const DUMP = 'Payroll runs (13): id=56, org_unit=1, period_start=2026-08-01, period_end=2026-08-31, status=committed, created_at=2026-09-25T18:47:58.558784+03:00; id=68, org_unit=6, period_start=2026-08-01, period_end=2026-08-31, status=committed, created_at=2026-09-25T18:48:57.360110+03:00.';

describe('presentRecordDump', () => {
  it('turns a field dump into a table and keeps the prose', () => {
    const text = presentRecordDump(`${DUMP}\n\nNo October runs.`);
    expect(text).toContain('Payroll runs (2 of 13)');
    expect(text).toContain('| Id | Org Unit | Period Start | Period End | Status | Created At |');
    expect(text).toContain('| 56 | 1 | 2026-08-01 | 2026-08-31 | committed | 2026-09-25 |');
    expect(text).not.toContain('id=');
    expect(text).not.toContain('T18:');
    expect(text).toContain('No October runs.');
  });

  it('leaves ordinary sentences alone', () => {
    const prose = 'Balance is 30. Nothing was submitted.';
    expect(presentRecordDump(prose)).toBe(prose);
    expect(dumpBlockToTable('I cannot draft a plan for this request.')).toBeNull();
  });

  it('shows the entity label, not the chip token', () => {
    const dump = 'Profile (1): name=Ahmed, department=[[org-unit:14:Human Resources Department]].';
    const text = presentRecordDump(dump);
    expect(text).toContain('Human Resources Department');
    expect(text).not.toContain('[[');
  });
});
