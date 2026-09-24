// Strip engine jargon from Operator-facing strings (RULE_23).
// Prefer presentationPlane for structured tool/source labels; this helper
// cleans free-form prose that still slipped through.

const RULE_ID = /\bRULE_\d+\b[:\s-]*/gi;
const SNAKE_TOOL = /\b(deny_[a-z0-9_]+|call_host_api|search_knowledge|export_document|code_execute|invoke_skill|plan_task|generate_gosi_wps_sif|validate_gosi_wps_sif|submit_gosi_wps_sif|submit_my_leave|submit_my_loan)\b/gi;
const DOTTED_API = /\b[a-z][a-z0-9]*(?:[._][a-z0-9]+)+\b/gi;

/**
 * Common host/API errors → short employee-facing line + a concrete next move.
 * Display-only mapping of *error text* (not user intent) — Rules 1–5 intact.
 */
const FRIENDLY_ERRORS = [
  {
    re: /missing required path parameter ['"]?id['"]?/i,
    msg: 'Pulse needed which payroll run or record to use, and that id was missing from the step.',
    fix: 'Open Plan, edit this step so it names the exact run (for example “October 2026 payroll”), then Retry.',
  },
  {
    re: /missing required (?:path|query|body) parameter/i,
    msg: 'A required detail was missing from the request, so nothing was sent.',
    fix: 'Open Plan and add the missing detail to this step, then Retry.',
  },
  {
    re: /\b404\b|not found/i,
    msg: 'That record was not found.',
    fix: 'Check the step points at an existing record, or Skip it and continue.',
  },
  {
    re: /unknown dimension|required field was missing|was not one of the allowed values/i,
    msg: 'A required detail was missing from the request, so nothing was sent.',
    fix: 'Open Plan and add the missing detail to this step, then Retry.',
  },
  {
    re: /\b403\b|forbidden|\bpermission\b|\bnot allowed\b/i,
    msg: 'You do not have permission for this action in this workspace.',
    fix: 'Ask HR / your admin for access, or Skip this step.',
  },
  {
    re: /timeout|timed out/i,
    msg: 'The system took too long to answer.',
    fix: 'Retry this step. If it keeps timing out, discuss it in Plan mode.',
  },
];

/**
 * @param {string|null|undefined} text
 * @returns {{ message: string, fix: string }}
 */
export function explainStepError(text) {
  const raw = String(text || '').trim();
  if (!raw) return { message: '', fix: '' };
  for (const { re, msg, fix } of FRIENDLY_ERRORS) {
    if (re.test(raw)) return { message: msg, fix };
  }
  return {
    message: stripEngineJargon(raw),
    fix: 'Retry the step, Skip it, or open Plan mode to change the request.',
  };
}

/** Employee-friendly error message (string) — see explainStepError for the fix. */
export function friendlyStepError(text) {
  return explainStepError(text).message;
}

/**
 * Remove RULE_xx tokens and common snake_case tool ids from display copy.
 * @param {string|null|undefined} text
 * @returns {string}
 */
export function stripEngineJargon(text) {
  if (text == null || text === '') return '';
  let out = String(text);
  out = out.replace(RULE_ID, '');
  out = out.replace(SNAKE_TOOL, (m) => {
    if (m === 'call_host_api') return 'system check';
    return '';
  });
  out = out.replace(DOTTED_API, '');
  return out.replace(/\s{2,}/g, ' ').replace(/\s+([,.;:])/g, '$1').trim();
}
