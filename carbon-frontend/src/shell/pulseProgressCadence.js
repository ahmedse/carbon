// A6 — Intelligence Contract: step transitions visible without a >2s poll gap.
// First status comes from the SSE frame (same tick as step_start), not a poll.
// Polls are the DAG / subagent fallback only. Do not raise these above 2000.

export const A6_MAX_POLL_GAP_MS = 2000;
export const A6_FIRST_STATUS_MS = 1000;

export const LIVE_PLAN_POLL_MS = 2000;
export const LIVE_CANVAS_POLL_MS = 2000;

export const SUBAGENT_FAST_POLL_MS = 1500;
export const SUBAGENT_SLOW_POLL_MS = 2000;
export const SUBAGENT_BACKOFF_AFTER_POLLS = 5;
