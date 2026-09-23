// Strip engine jargon from Operator-facing strings (RULE_23).
// Prefer presentationPlane for structured tool/source labels; this helper
// cleans free-form prose that still slipped through.

const RULE_ID = /\bRULE_\d+\b[:\s-]*/gi;
const SNAKE_TOOL = /\b(deny_[a-z0-9_]+|call_host_api|search_knowledge|export_document|code_execute|invoke_skill|plan_task|generate_gosi_wps_sif|validate_gosi_wps_sif|submit_gosi_wps_sif|submit_my_leave|submit_my_loan)\b/gi;
const DOTTED_API = /\b[a-z][a-z0-9]*(?:[._][a-z0-9]+)+\b/gi;

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
