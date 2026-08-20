// src/shell/aiTaskStatus.js
// Sprint 23 W3-B — shared status copy maps for the agentic task surface
// (plan lifecycle + step lifecycle). Kept out of component files so fast
// refresh is not degraded (react-refresh/only-export-components). Outcome
// copy only (RULE_23) — no engine class names, no transport details.

export const PLAN_STATUS = {
  pending_approval: { label: 'Needs review', color: 'warning' },
  approved: { label: 'Approved', color: 'primary' },
  running: { label: 'Running…', color: 'primary' },
  paused: { label: 'Needs approval', color: 'warning' },
  completed: { label: 'Completed', color: 'success' },
  failed: { label: 'Failed', color: 'error' },
  cancelled: { label: 'Cancelled', color: 'default' },
};

export const STEP_STATUS = {
  pending: { label: 'Pending', color: 'default' },
  running: { label: 'Running…', color: 'primary' },
  awaiting_approval: { label: 'Needs approval', color: 'warning' },
  completed: { label: 'Finished', color: 'success' },
  failed: { label: 'Failed', color: 'error' },
  skipped: { label: 'Skipped', color: 'default' },
};
