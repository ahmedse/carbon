// Shared allowlist for My profile-change requests (NSR-5A).
// Keep in sync with backend/people/profile_change_service.py PROFILE_CHANGE_ALLOWLIST.
// Unknown / free-text fields are ignored on approve — the My form must only offer these.

export const PROFILE_CHANGE_FIELDS = Object.freeze([
  'full_name',
  'name_en_given',
  'name_en_family',
  'name_ar_given',
  'name_ar_family',
  'nationality',
  'gender',
  'date_of_birth',
]);

export function isProfileChangeField(code) {
  return PROFILE_CHANGE_FIELDS.includes(code);
}
