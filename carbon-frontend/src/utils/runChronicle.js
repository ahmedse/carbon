/**
 * Build Operator-facing chronicle events from plan + live run steps.
 * Pure helper — no React. Timestamps come from step fields when present;
 * otherwise beat labels (#1, #2…) keep the timeline readable.
 */

const TERMINAL = new Set(['completed', 'failed', 'skipped']);

const STATUS_LABEL = {
  pending: 'Pending',
  running: 'Running…',
  awaiting_approval: 'Needs approval',
  paused: 'Paused',
  completed: 'Finished',
  failed: 'Failed',
  skipped: 'Skipped',
};

/** Tools that typically mutate Carbon — soft copy for consent detail. */
const WRITEISH = new Set([
  'create_dq_rule',
  'learn_fact',
  'forget_fact',
  'run_ops_workflow',
  'draft_skill',
  'invoke_skill',
]);

function pickTime(step) {
  const raw =
    step?.finished_at
    || step?.completed_at
    || step?.updated_at
    || step?.started_at
    || step?.created_at
    || null;
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatClock(date) {
  if (!date) return null;
  try {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return date.toISOString().slice(11, 19);
  }
}

function formatClockFull(date) {
  if (!date) return null;
  try {
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return date.toISOString();
  }
}

function eventKind(status) {
  switch (status) {
    case 'running':
      return 'running';
    case 'awaiting_approval':
      return 'consent';
    case 'paused':
      return 'paused';
    case 'failed':
      return 'failed';
    case 'completed':
      return 'done';
    case 'skipped':
      return 'skipped';
    case 'pending':
    default:
      return 'pending';
  }
}

function consentDetail(step) {
  const tool = step?.tool_name || '';
  if (WRITEISH.has(tool) || step?.requires_confirmation || step?.is_write) {
    return 'Waiting for your OK before changing data.';
  }
  return 'Waiting for your OK to continue.';
}

/**
 * @param {object|null} plan
 * @param {Array} [runSteps]
 * @returns {Array<object>}
 */
export function buildRunChronicle(plan, runSteps = []) {
  const live = Array.isArray(runSteps) ? runSteps : [];
  const byId = new Map(live.map((s) => [s.step_id, s]));
  const base = Array.isArray(plan?.steps) ? plan.steps : [];
  const merged = base.map((s) => {
    const patch = byId.get(s.step_id);
    return patch ? { ...s, ...patch } : s;
  });
  live.forEach((s) => {
    if (!merged.some((m) => m.step_id === s.step_id)) merged.push(s);
  });

  const total = merged.length;

  return merged.map((step, index) => {
    const status = step.status || 'pending';
    const when = pickTime(step);
    const clock = formatClock(when);
    const beatNum = index + 1;
    const title = step.intent || `Step ${step.step_id ?? beatNum}`;
    let detail = null;
    if (status === 'awaiting_approval') {
      detail = consentDetail(step);
    } else if (status === 'failed' && (step.error || step.error_message)) {
      detail = String(step.error || step.error_message).slice(0, 160);
    } else if (status === 'completed' && step.consent_granted) {
      detail = 'Approved by you';
    } else if (status === 'running') {
      detail = 'In progress…';
    }

    return {
      id: `evt-${step.step_id ?? index}`,
      stepId: step.step_id,
      beat: beatNum,
      beatLabel: clock || `#${beatNum}`,
      clock,
      clockFull: formatClockFull(when),
      title,
      detail,
      status,
      statusLabel: STATUS_LABEL[status] || status || 'Pending',
      kind: eventKind(status),
      latencyMs: typeof step.latency_ms === 'number' ? step.latency_ms : null,
      settled: TERMINAL.has(status),
      total,
    };
  });
}

export function chronicleTone(kind) {
  switch (kind) {
    case 'done':
      return 'success';
    case 'failed':
      return 'error';
    case 'consent':
    case 'paused':
      return 'warning';
    case 'running':
      return 'primary';
    default:
      return 'default';
  }
}
