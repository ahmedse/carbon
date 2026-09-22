// src/shell/aiTaskStatus.js
// Sprint 23 W3-B — shared status copy maps for the agentic task surface
// (plan lifecycle + step lifecycle). Kept out of component files so fast
// refresh is not degraded (react-refresh/only-export-components). Outcome
// copy only (RULE_23) — no engine class names, no transport details.

export const PLAN_STATUS = {
  discovering: { label: 'Clarifying…', color: 'info' },
  pending_approval: { label: 'Needs review', color: 'warning' },
  approved: { label: 'Approved', color: 'primary' },
  running: { label: 'Running…', color: 'primary' },
  paused: { label: 'Needs approval', color: 'warning' },
  completed: { label: 'Completed', color: 'success' },
  completed_with_gaps: { label: 'Completed with gaps', color: 'warning' },
  failed: { label: 'Failed', color: 'error' },
  cancelled: { label: 'Cancelled', color: 'default' },
};

/** Resolve plan status chip meta; unknown statuses fall back to raw label. */
export function planStatusMeta(status) {
  return PLAN_STATUS[status] || { label: status || 'Unknown', color: 'default' };
}

const STEP_TERMINAL = new Set(['completed', 'failed', 'skipped']);
const PLAN_STATUS_LOCKED = new Set(['discovering', 'pending_approval', 'cancelled']);

/**
 * Derive display/plan status from step outcomes when every step is terminal.
 * Keeps discovering / pending_approval / cancelled untouched. If any step
 * failed → failed; otherwise all finished → completed. Used by the picker and
 * run chrome so list rows stay honest even when a run row lagged.
 *
 * Honesty: never surface Completed / Completed-with-gaps while any step is
 * still open (Pending under Completed is a product lie).
 * @param {object|null|undefined} plan
 * @returns {string}
 */
export function effectivePlanStatus(plan) {
  if (!plan) return '';
  const status = plan.status || '';
  if (PLAN_STATUS_LOCKED.has(status)) return status;
  const steps = Array.isArray(plan.steps) ? plan.steps : [];
  if (steps.some((s) => s.status === 'awaiting_approval')) return 'paused';
  // False-complete guard — trust steps over a dishonest run.status.
  if (
    (status === 'completed' || status === 'completed_with_gaps')
    && steps.length
    && !steps.every((s) => STEP_TERMINAL.has(s.status))
  ) {
    if (steps.some((s) => s.status === 'running')) return 'running';
    return 'failed';
  }
  if (status === 'completed_with_gaps') return 'completed_with_gaps';
  if (!steps.length) return status;
  if (!steps.every((s) => STEP_TERMINAL.has(s.status))) return status;
  const failed = steps.filter((s) => s.status === 'failed');
  const completed = steps.filter((s) => s.status === 'completed');
  if (
    failed.length
    && completed.length
    && failed.every((s) => String(s.error || '').startsWith('[caught]'))
  ) {
    return 'completed_with_gaps';
  }
  if (failed.length) return 'failed';
  return 'completed';
}

export const STEP_STATUS = {
  pending: { label: 'Pending', color: 'default' },
  running: { label: 'Running…', color: 'primary' },
  awaiting_approval: { label: 'Needs approval', color: 'warning' },
  completed: { label: 'Finished', color: 'success' },
  failed: { label: 'Failed', color: 'error' },
  skipped: { label: 'Skipped', color: 'default' },
};

/** Resolve step status chip meta; unknown statuses fall back to raw label. */
export function stepStatusMeta(status) {
  return STEP_STATUS[status] || { label: status || 'Pending', color: 'default' };
}

/** Terminal plan statuses that may be reset via POST …/rerun/ then streamed. */
export const RERUNNABLE_STATUSES = Object.freeze([
  'completed',
  'completed_with_gaps',
  'failed',
  'cancelled',
]);

/** True when a plan may be wiped and re-executed from a clean slate. */
export function isRerunnableStatus(status) {
  return RERUNNABLE_STATUSES.includes(status);
}

/** Session/UI phases that mean the run has settled (ledger + Output CTAs). */
export function isSettledPhase(phase) {
  return phase === 'finished' || phase === 'stopped' || phase === 'error';
}

/** Dense UPPERCASE labels for DAG node interiors (same vocabulary as STEP_STATUS). */
export const NODE_STATUS_DENSE = Object.fromEntries(
  Object.entries(STEP_STATUS).map(([k, v]) => [
    k,
    String(v.label).replace(/…/g, '').toUpperCase().replace('NEEDS APPROVAL', 'APPROVAL'),
  ]),
);

// W3-G — human-facing tool names via presentation plane (RULE_23).
// Unknown tools title-case for step chips; L0 Chat omits unknowns via presentSource.
import { presentToolLabel } from './presentationPlane';

export const TOOL_LABELS = {
  search_knowledge: 'Knowledge base',
  get_entity_details: 'Record details',
  search_entity: 'Records search',
  call_host_api: 'System check',
  navigate_to: 'Open page',
  open_entity: 'Open record',
  ask_clarification: 'Clarification',
  learn_fact: 'Saved memory',
  forget_fact: 'Removed memory',
  run_ops_workflow: 'Workflow',
  draft_skill: 'Draft skill',
  invoke_skill: 'Skill run',
  create_dq_rule: 'Data quality rule',
  export_document: 'Export',
  list_my_capabilities: 'Capabilities',
  edit_plan: 'Edit plan',
  approve_plan: 'Approve plan',
  plan_task: 'Plan',
  web_research: 'Web research',
  create_employee: 'Create employee',
  update_employee: 'Update employee',
  submit_my_leave: 'Submit leave',
  create_leave_record: 'Leave request',
  submit_my_loan: 'Submit loan',
  analyze_employees: 'Employee data',
  people_query: 'People records',
};

/**
 * @param {string} name
 * @param {{ apiName?: string, audience?: 'operator'|'proof'|'analyst' }} [opts]
 */
export function toolLabel(name, opts = {}) {
  if (!name) return '';
  const presented = presentToolLabel(name, {
    audience: opts.audience || 'operator',
    apiName: opts.apiName,
  });
  if (presented) return presented;
  if (TOOL_LABELS[name]) return TOOL_LABELS[name];
  return String(name)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// W3-G — friendly agent role names for the step "who" chips. Roles are the
// AGENT_ROLES values from the engine (orchestrator/researcher/planner/critic/
// domain_specialist); unknown roles title-case their snake_case value.
export const AGENT_ROLE_LABELS = {
  orchestrator: 'Orchestrator',
  researcher: 'Researcher',
  planner: 'Planner',
  critic: 'Critic',
  domain_specialist: 'Domain specialist',
};

export function agentRoleLabel(role) {
  if (!role) return '';
  if (AGENT_ROLE_LABELS[role]) return AGENT_ROLE_LABELS[role];
  return String(role)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * ADR-0043 status chip copy for the run header (progress + blocker).
 * @param {object|null} plan
 * @param {Array} [runSteps]
 * @param {string} [phase]
 * @returns {{ label: string, color: string }}
 */
export function runHeaderStatusChip(plan, runSteps = [], phase = 'idle') {
  const steps = (Array.isArray(runSteps) && runSteps.length)
    ? runSteps
    : (Array.isArray(plan?.steps) ? plan.steps : []);
  const total = steps.length;
  const settled = steps.filter((s) => STEP_TERMINAL.has(s.status)).length;
  const awaiting = steps.some((s) => s.status === 'awaiting_approval');
  const failed = steps.some((s) => s.status === 'failed');
  const effective = effectivePlanStatus(plan);
  const meta = planStatusMeta(effective);

  if (awaiting || phase === 'paused' || effective === 'paused') {
    return {
      label: total ? `${settled}/${total} · Needs approval` : meta.label,
      color: 'warning',
    };
  }
  if (phase === 'working' || effective === 'running') {
    return {
      label: total ? `${settled}/${total} · running` : meta.label,
      color: 'primary',
    };
  }
  if (phase === 'error' || effective === 'failed' || failed) {
    return {
      label: total ? `${settled}/${total} · failed` : meta.label,
      color: 'error',
    };
  }
  if (phase === 'stopped' || effective === 'cancelled') {
    return {
      label: total ? `${settled}/${total} · stopped` : (meta.label || 'Stopped'),
      color: 'default',
    };
  }
  if (effective === 'completed' || effective === 'completed_with_gaps' || phase === 'finished') {
    return {
      label: total ? `${settled}/${total} · done` : meta.label,
      color: effective === 'completed_with_gaps' ? 'warning' : 'success',
    };
  }
  return { label: meta.label, color: meta.color };
}
