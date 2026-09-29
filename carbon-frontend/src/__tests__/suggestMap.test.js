import { describe, it, expect } from 'vitest';
import { suggestColumnMap, unmappedRequired } from '../components/inbound/suggestMap';
import { PEOPLE_FIELD_ALIASES } from '../apps/people/inboundAliases';

const FIELDS = [
  { name: 'employee_no', label: 'Employee number', required: true },
  { name: 'full_name', label: 'Full name', required: true },
  { name: 'org_unit', label: 'Org unit code', required: true },
  { name: 'basic_salary', label: 'Basic salary', required: true },
];

describe('suggestColumnMap', () => {
  it('maps GOFSCO-style headers via People aliases', () => {
    const columns = suggestColumnMap(
      ['Code', 'FullNameEn', 'Cost Center', 'Salary'],
      FIELDS,
      PEOPLE_FIELD_ALIASES,
    );
    expect(columns).toEqual({
      Code: 'employee_no',
      FullNameEn: 'full_name',
      'Cost Center': 'org_unit',
      Salary: 'basic_salary',
    });
    expect(unmappedRequired(columns, FIELDS)).toEqual([]);
  });

  it('leaves unknown headers unmapped', () => {
    const columns = suggestColumnMap(['notes'], FIELDS, PEOPLE_FIELD_ALIASES);
    expect(columns.notes).toBe('');
    expect(unmappedRequired(columns, FIELDS)).toHaveLength(4);
  });
});
