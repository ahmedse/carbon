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

// W3-G — human-facing tool names (RULE_23 outcome copy). The engine exposes
// snake_case function names (e.g. `create_dq_rule`); the console shows a
// friendly label instead. Unknown tools fall back to a title-cased rewrite
// so a newly registered plugin never renders as a raw identifier.
export const TOOL_LABELS = {
  search_knowledge: 'Search knowledge',
  get_entity_details: 'Entity details',
  search_entity: 'Search records',
  call_host_api: 'Call host API',
  navigate_to: 'Navigate',
  open_entity: 'Open entity',
  ask_clarification: 'Ask a question',
  learn_fact: 'Remember fact',
  forget_fact: 'Forget fact',
  run_ops_workflow: 'Run workflow',
  draft_skill: 'Draft skill',
  invoke_skill: 'Run skill',
  create_dq_rule: 'Create DQ rule',
  export_document: 'Export document',
  list_my_capabilities: 'List capabilities',
  edit_plan: 'Edit plan',
  approve_plan: 'Approve plan',
  plan_task: 'Plan task',
  web_research: 'Web research',
};

export function toolLabel(name) {
  if (!name) return '';
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
