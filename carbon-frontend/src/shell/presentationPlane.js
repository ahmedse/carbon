// presentationPlane.js — Operator / Proof / Analyst view gate (RULE_23).
// Engines may emit tool ids, row counts, JSON. L0 Chat + Agent surfaces must
// show grounded outcomes only; proof and technical detail are opt-in.
//
// audience: 'operator' | 'proof' | 'analyst'

/** @typedef {'operator'|'proof'|'analyst'} PresentationAudience */

const ENGINE_LEAKAGE_RE =
  /\b(call_host_api|invoke_skill|plan_task|provider_|engine_turn|RULE_\d+|ADR-\d+|host\s+mutations?)\b/i;

/** Operator rewrites for known engine caveat strings (defense in depth). */
const CAVEAT_OPERATOR_REWRITE = [
  [
    /host\s+mutations?|ADR-0046|\bG2\b|chat_no_host_mutation|cannot\s+stage/i,
    'This change can’t be submitted in Chat — use Agent or My.',
  ],
];

/** Outcome labels for known tools (never snake_case on L0). */
const TOOL_OUTCOME = {
  call_host_api: 'System check',
  search_knowledge: 'Knowledge base',
  get_entity_details: 'Record details',
  search_entity: 'Records search',
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
  aggregate_entity: 'Records summary',
};

/** Refine call_host_api (and similar) from api_name / path hints. */
const API_HINTS = [
  // Mutations first — never collapse submit_* into a vague "records" read label.
  [/submit_my_leave|create_leave_record/i, 'Submit leave request'],
  [/submit_my_loan/i, 'Submit loan request'],
  [/submit_my_attendance/i, 'Submit attendance permission'],
  [/create_employee/i, 'Create employee'],
  [/update_employee/i, 'Update employee'],
  [/get_my_leave_balance|leave.?balance/i, 'Leave balance'],
  [/list_my_leave/i, 'Leave history'],
  [/list_my_loan/i, 'Loan history'],
  [/leave|vacation|annual/i, 'Leave records'],
  [/loan/i, 'Loan records'],
  [/generate_gosi_wps_sif|generate.*gosi/i, 'Build the file'],
  [/validate_gosi_wps_sif|validate.*gosi/i, 'Check the file'],
  [/submit_gosi_wps_sif|submit.*gosi/i, 'Send to GOSI'],
  [/payroll|salary|gosi/i, 'Payroll records'],
  [/employee|people\.|\/people\//i, 'People records'],
  [/attendance/i, 'Attendance'],
  [/org.?unit|organization/i, 'Organization'],
];

/**
 * @param {string|null|undefined} name
 * @param {{ apiName?: string, audience?: PresentationAudience }} [opts]
 * @returns {string} Empty string means "omit on this audience"
 */
export function presentToolLabel(name, opts = {}) {
  const audience = opts.audience || 'operator';
  const raw = name == null ? '' : String(name).trim();
  if (!raw) return '';

  if (audience === 'analyst') {
    return raw;
  }

  const api = opts.apiName != null ? String(opts.apiName) : '';
  if (raw === 'call_host_api' || raw.includes('call_host_api')) {
    for (const [re, label] of API_HINTS) {
      if (api && re.test(api)) return label;
    }
    return audience === 'proof' ? 'System check' : 'System check';
  }

  if (TOOL_OUTCOME[raw]) return TOOL_OUTCOME[raw];

  // Unknown snake_case: omit on operator; soft title on proof; raw on analyst
  if (/^[a-z][a-z0-9_]*$/.test(raw) && raw.includes('_')) {
    if (audience === 'operator') return '';
    return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  return raw;
}

/**
 * Present one provenance/envelope source for a given audience.
 * @param {object} src
 * @param {PresentationAudience} [audience]
 * @param {{ rows?: (n: number) => string, truncated?: string }} [labels]
 * @returns {{ label: string, resolvedAt?: string }|null}
 */
export function presentSource(src, audience = 'operator', labels = {}) {
  if (!src || typeof src !== 'object') return null;
  const tool = presentToolLabel(src.tool, {
    audience,
    apiName: src.api_name || src.path || src.endpoint || '',
  });

  if (audience === 'operator') {
    if (!tool) return null;
    // Never surface "0 rows" — it reads as failure to humans.
    return { label: tool, resolvedAt: src.resolved_at || undefined };
  }

  if (audience === 'proof') {
    if (!tool) return null;
    const parts = [tool];
    const rows = src.rows_returned;
    if (typeof rows === 'number' && rows > 0 && labels.rows) {
      parts.push(labels.rows(rows));
    }
    if (src.truncated && labels.truncated) parts.push(labels.truncated);
    return { label: parts.join(' · '), resolvedAt: src.resolved_at || undefined };
  }

  // analyst — full fidelity
  const parts = [];
  if (src.tool) parts.push(String(src.tool));
  if (src.rows_returned != null && labels.rows) parts.push(labels.rows(src.rows_returned));
  else if (src.rows_returned != null) parts.push(`${src.rows_returned} rows`);
  if (src.truncated) parts.push(labels.truncated || 'Truncated');
  return {
    label: parts.join(' · ') || 'Source',
    resolvedAt: src.resolved_at || undefined,
  };
}

/**
 * @param {Array} sources
 * @param {PresentationAudience} [audience]
 * @param {object} [labels]
 * @returns {{ chips: Array<{label: string, resolvedAt?: string}>, softFallback: boolean }}
 */
export function presentSources(sources, audience = 'operator', labels = {}) {
  const list = Array.isArray(sources) ? sources : [];
  const chips = [];
  for (const src of list) {
    const chip = presentSource(src, audience, labels);
    if (chip?.label) chips.push(chip);
  }
  // Had engine sources but nothing mappable → soft fallback on operator only
  const softFallback = audience === 'operator' && list.length > 0 && chips.length === 0;
  return { chips, softFallback };
}

/**
 * Present one envelope caveat for a given audience.
 * @param {{ level?: string, text?: string, message?: string }|string|null} caveat
 * @param {PresentationAudience} [audience]
 * @param {{ chatCannotSubmit?: string }} [labels]
 * @returns {{ level: string, text: string }|null}
 */
export function presentCaveat(caveat, audience = 'operator', labels = {}) {
  const raw =
    typeof caveat === 'string'
      ? caveat
      : String(caveat?.text || caveat?.message || '').trim();
  if (!raw) return null;

  const level =
    (typeof caveat === 'object' && caveat?.level) || 'info';

  if (audience === 'analyst') {
    return { level, text: raw };
  }

  for (const [re, fallback] of CAVEAT_OPERATOR_REWRITE) {
    if (re.test(raw)) {
      return {
        level,
        text: labels.chatCannotSubmit || fallback,
      };
    }
  }

  // Strip ADR / RULE / G2 citations; drop the line if nothing useful remains.
  const stripped = raw
    .replace(/\s*\(?\s*ADR-\d+(?:\s*[\/·]\s*G\d+)?\s*\)?/gi, '')
    .replace(/\s*\(?\s*RULE_\d+\s*\)?/gi, '')
    .replace(/\s*\(?\s*G\d+\s*\)?/gi, '');
  let cleaned = stripped.replace(/\s{2,}/g, ' ').trim();
  // Only trim leftover citation punctuation when we actually removed a cite.
  if (stripped !== raw) {
    cleaned = cleaned.replace(/^[\s\-–—:,.]+|[\s\-–—:,.]+$/g, '').trim();
  }

  if (!cleaned || (audience === 'operator' && hasEngineLeakage(cleaned))) {
    return null;
  }

  return { level, text: cleaned };
}

/**
 * @param {Array} caveats
 * @param {PresentationAudience} [audience]
 * @param {object} [labels]
 * @returns {Array<{ level: string, text: string }>}
 */
export function presentCaveats(caveats, audience = 'operator', labels = {}) {
  const list = Array.isArray(caveats) ? caveats : [];
  const out = [];
  for (const c of list) {
    const presented = presentCaveat(c, audience, labels);
    if (presented?.text) out.push(presented);
  }
  return out;
}

/** Consent expand control — Operator label (not "Details & JSON"). */
export function presentConsentExpandLabel({ open = false } = {}) {
  return open ? 'Hide preparation details' : 'How this was prepared';
}

export function presentTechnicalDetailsLabel({ open = false } = {}) {
  return open ? 'Hide technical details' : 'Technical details';
}

/** True if text still contains engine leakage (for tests / lint). */
export function hasEngineLeakage(text) {
  return ENGINE_LEAKAGE_RE.test(String(text || ''));
}

export { ENGINE_LEAKAGE_RE, TOOL_OUTCOME };
