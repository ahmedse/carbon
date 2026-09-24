export const STATE_COLOR = {
  passed: 'success',
  exempt: 'info',
  failed: 'error',
  conflict: 'error',
  stale: 'warning',
  unknown: 'warning',
  unmeasured: 'default',
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
