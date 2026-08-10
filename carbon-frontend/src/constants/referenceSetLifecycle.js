// src/constants/referenceSetLifecycle.js
// Shared lifecycle constants for reference sets (mirrors backend mdm/models.py).
// Single source of truth for the frontend so chips, labels, and allowed
// transitions stay consistent across MDMPage and the detail-page tabs.

export const LIFECYCLE_STATES = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'deprecated', label: 'Deprecated' },
  { value: 'archived', label: 'Archived' },
];

export const LIFECYCLE_LABELS = Object.fromEntries(
  LIFECYCLE_STATES.map((s) => [s.value, s.label])
);

export const LIFECYCLE_COLORS = {
  draft: 'default',
  active: 'success',
  deprecated: 'warning',
  archived: 'error',
};

// Mirrors ReferenceSet.VALID_LIFECYCLE_TRANSITIONS in backend/mdm/models.py.
export const VALID_LIFECYCLE_TRANSITIONS = {
  draft: ['active'],
  active: ['deprecated'],
  deprecated: ['active', 'archived'],
  archived: [],
};

// Helper: returns the allowed next states for a given current state.
export function getValidTransitions(currentState) {
  return VALID_LIFECYCLE_TRANSITIONS[currentState] || [];
}
