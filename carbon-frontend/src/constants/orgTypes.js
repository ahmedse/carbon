// src/constants/orgTypes.js — SINGLE source of truth for org unit types.
// Backend: backend/mdm/models.py ORG_TYPE_CHOICES (keys MUST match exactly).
export const ORG_TYPE_KEYS = [
  'university', 'campus', 'college', 'department', 'division', 'team',
  'facility', 'other', 'company', 'section', 'crew', 'base', 'yard',
  'store', 'cost_center',
];
// Display labels — i18n keys (catalog.json), fall back to capitalized key.
export const orgTypeLabelKey = (type) => (ORG_TYPE_KEYS.includes(type) ? type : 'other');
