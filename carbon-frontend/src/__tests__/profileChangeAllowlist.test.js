// profileChangeAllowlist — NSR-5A FE allowlist parity with backend.
import { describe, it, expect } from 'vitest';
import {
  PROFILE_CHANGE_FIELDS,
  isProfileChangeField,
} from '../apps/my/components/profileChangeAllowlist';

describe('profileChangeAllowlist', () => {
  it('matches NSR-5A personal/display fields', () => {
    expect(PROFILE_CHANGE_FIELDS).toEqual([
      'full_name',
      'name_en_given',
      'name_en_family',
      'name_ar_given',
      'name_ar_family',
      'nationality',
      'gender',
      'date_of_birth',
    ]);
  });

  it('accepts allowlisted codes and rejects free-text', () => {
    expect(isProfileChangeField('full_name')).toBe(true);
    expect(isProfileChangeField('mobile_number')).toBe(false);
    expect(isProfileChangeField('basic_salary')).toBe(false);
    expect(isProfileChangeField('')).toBe(false);
  });
});
