import { describe, it, expect } from 'vitest';
import {
  headersMatchIdentity,
  isIdentityMapping,
  pickOfficialIdentityTemplate,
  suggestColumnMap,
  unmappedRequired,
} from '../components/inbound/suggestMap';
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

describe('official identity template helpers', () => {
  const identityCols = Object.fromEntries(FIELDS.map((f) => [f.name, f.name]));
  const official = {
    id: 11,
    name: 'People · Employee snapshot',
    target_key: 'people.employee_snapshot',
    mapping: { columns: identityCols, crosswalks: {} },
  };
  const custom = {
    id: 12,
    name: 'My alias map',
    target_key: 'people.employee_snapshot',
    mapping: { columns: { Code: 'employee_no' }, crosswalks: {} },
  };

  it('headersMatchIdentity requires every field name as a header', () => {
    expect(headersMatchIdentity(FIELDS.map((f) => f.name), FIELDS)).toBe(true);
    expect(headersMatchIdentity(['Code', 'FullNameEn'], FIELDS)).toBe(false);
    expect(headersMatchIdentity([], FIELDS)).toBe(false);
  });

  it('isIdentityMapping requires field→field for every declared field', () => {
    expect(isIdentityMapping(identityCols, FIELDS)).toBe(true);
    expect(isIdentityMapping({ employee_no: 'employee_no' }, FIELDS)).toBe(false);
    expect(isIdentityMapping({ Code: 'employee_no' }, FIELDS)).toBe(false);
  });

  it('pickOfficialIdentityTemplate prefers identity map for the target key', () => {
    const hit = pickOfficialIdentityTemplate(
      [custom, official],
      FIELDS,
      'people.employee_snapshot',
    );
    expect(hit).toEqual(official);
  });

  it('pickOfficialIdentityTemplate falls back to People · name', () => {
    const namedOnly = {
      id: 13,
      name: 'People · Employee snapshot',
      target_key: 'people.employee_snapshot',
      mapping: { columns: { Code: 'employee_no' }, crosswalks: {} },
    };
    const hit = pickOfficialIdentityTemplate(
      [namedOnly],
      FIELDS,
      'people.employee_snapshot',
    );
    expect(hit).toEqual(namedOnly);
  });

  it('pickOfficialIdentityTemplate ignores other target keys', () => {
    const other = {
      ...official,
      id: 14,
      target_key: 'people.leave_history',
      name: 'People · Leave history',
    };
    expect(
      pickOfficialIdentityTemplate([other], FIELDS, 'people.employee_snapshot'),
    ).toBeNull();
  });
});
