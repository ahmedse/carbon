export const STATE_COLOR = {
  passed: 'success',
  exempt: 'info',
  failed: 'error',
  conflict: 'error',
  stale: 'warning',
  unknown: 'warning',
  unmeasured: 'default',
  open: 'default',
  running: 'info',
  succeeded: 'success',
  met: 'success',
  missed: 'warning',
};

export function stateColor(state) {
  return STATE_COLOR[state] || 'default';
}

export function levelColor(level) {
  if (level >= 5) return 'success';
  if (level >= 3) return 'primary';
  if (level >= 1) return 'warning';
  return 'error';
}

/** Level index → name (0 Unmanaged … 6 Excellent). */
export const LEVEL_NAMES = [
  'Unmanaged',
  'Declared',
  'Specified',
  'Built',
  'Proven',
  'Operated',
  'Excellent',
];

export function levelName(level) {
  if (level == null || level < 0 || level >= LEVEL_NAMES.length) return 'Unknown';
  return LEVEL_NAMES[level];
}

/** Ladder column levels 1–6. */
export const LADDER_LEVELS = [1, 2, 3, 4, 5, 6];

export const ASPECT_ORDER = [
  'specified',
  'correct',
  'secure',
  'reliable',
  'performant',
  'usable',
  'maintainable',
  'observed',
  'governed',
];

export const COWORKER_LEVELS = [
  { id: 'L0', name: 'Safe', mapped: false },
  { id: 'L1', name: 'Grounded', mapped: false },
  { id: 'L2', name: 'Continuous', mapped: true },
  { id: 'L3', name: 'Coherent', mapped: true },
  { id: 'L4', name: 'Proactive', mapped: true },
  { id: 'L5', name: 'Autonomous', mapped: false },
  { id: 'L6', name: 'Understands', mapped: false },
  { id: 'L7', name: 'Lean', mapped: false },
];

export const PULSE_AREAS = [
  { id: 'trust', title: 'Trust & consent', promise: 'Will not change records without approval', proof: 'ADR-0046 is declared. Live refusal is not mapped.', mapped: true },
  { id: 'understand', title: 'Understand & respond', promise: 'Gets the meaning in Arabic and English', proof: 'Not mapped. L6 has no Excellence probe yet.', mapped: false },
  { id: 'remember', title: 'Know & remember', promise: 'Uses real host data and this conversation', proof: 'L2 Continuous is bound on Chat. Memory itself has no checks.', mapped: true },
  { id: 'coherent', title: 'Stay coherent', promise: 'One voice and one decision per turn', proof: 'L3 Coherent is bound on Chat.', mapped: true },
  { id: 'act', title: 'Act with approval', promise: 'Plans, previews, and runs only with consent', proof: 'L4 Proactive is bound on Agent. L5 is not mapped.', mapped: true },
  { id: 'pack', title: 'Your domain pack', promise: 'Vocabulary and processes come from the instance', proof: 'Pack contract gate is bound. L7 Lean is not mapped.', mapped: true },
  { id: 'production', title: 'Proven in production', promise: 'Works on real journeys over time', proof: 'Soak and a fresh gauge series are bound on Ops.', mapped: true },
];

export function pulseArea(id) {
  return PULSE_AREAS.find((area) => area.id === id) || null;
}

export function aspectLabel(aspect) {
  if (!aspect) return '—';
  return aspect.charAt(0).toUpperCase() + aspect.slice(1);
}

export const DIMENSION_SHORT = {
  specified: 'spec',
  correct: 'corr',
  secure: 'sec',
  reliable: 'rel',
  performant: 'perf',
  usable: 'use',
  maintainable: 'maint',
  observed: 'obs',
  governed: 'gov',
};
