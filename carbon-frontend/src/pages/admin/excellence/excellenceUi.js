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
