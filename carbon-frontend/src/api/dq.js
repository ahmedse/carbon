// carbon-frontend/src/api/dq.js
import { apiFetch } from './api';
import { API_ROUTES } from '../config';

/**
 * Fetch org-scoped DQ metrics summary
 */
export function getOrgDQMetrics(token) {
  return apiFetch('dq/metrics/', { token });
}

/**
 * Fetch table-level DQ metrics and active rules
 */
export function getTableDQMetrics(tableId, token) {
  return apiFetch(`dq/metrics/table/${tableId}/`, { token });
}

/**
 * Fetch field-level DQ metrics
 */
export function getFieldDQMetrics(fieldId, token) {
  return apiFetch(`dq/metrics/field/${fieldId}/`, { token });
}

/**
 * Fetch DQ results for a specific table or rule
 */
export function getDQResults(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });
  const qs = queryParams.toString();
  return apiFetch(`dq/results/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Fetch table profiles
 */
export function getTableProfiles(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });
  const qs = queryParams.toString();
  return apiFetch(`dq/table-profiles/${qs ? `?${qs}` : ''}`, { token });
}

// =====================================================================
// DQ Rule CRUD — clean wrappers using relative endpoints + apiFetch.
// apiFetch handles JWT validity/refresh; token is read from localStorage
// when not supplied. Do NOT prepend API_BASE_URL to these endpoints.
// =====================================================================

/**
 * List DQ rules for a table (and optionally a field).
 */
export function listDQRules(token, filters = {}) {
  const params = new URLSearchParams();
  if (filters.data_table != null) params.set('data_table', filters.data_table);
  if (filters.data_field != null) params.set('data_field', filters.data_field);
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.dqRules}${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Create a new DQ rule.
 */
export function createDQRule(token, data) {
  return apiFetch(API_ROUTES.dqRules, { method: 'POST', token, body: data });
}

/**
 * Partially update a DQ rule.
 */
export function updateDQRule(token, id, data) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/`, { method: 'PATCH', token, body: data });
}

/**
 * Delete a DQ rule. Archives when results exist, hard-deletes otherwise.
 */
export function deleteDQRule(token, id) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/`, { method: 'DELETE', token });
}

/**
 * Fetch a single DQ rule (full detail incl. definition, tags, bindings).
 */
export function getDQRule(token, id) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/`, { token });
}

/**
 * Run a DQ rule now — creates a followable DQ job
 * (rule_run for deterministic rules, nl_check for NL rules).
 * @returns {Promise<object>} DQJob
 */
export function runDQRule(token, id, prompt) {
  const body = prompt ? { prompt } : {};
  return apiFetch(`${API_ROUTES.dqRules}${id}/run/`, { method: 'POST', token, body });
}

export function getDQRuleHistory(token, id) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/history/`, { token });
}

/**
 * Fetch sample failures for a DQ result (row ids + reasons).
 * GET /dq/results/{id}/failures/
 */
export function getDQResultFailures(token, resultId) {
  return apiFetch(`dq/results/${resultId}/failures/`, { token });
}

/**
 * Fetch DQ rule tags (categorization).
 * GET /dq/tags/
 */
export function listDQTags(token) {
  return apiFetch('dq/tags/', { token });
}

// =====================================================================
// DQ Jobs — explicit, user-started jobs with a followable lifecycle.
// =====================================================================

/**
 * List DQ jobs (optionally filtered by status / job_type / rule / table).
 */
export function listDQJobs(token, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null && v !== '') params.set(k, v); });
  const qs = params.toString();
  return apiFetch(`dq/jobs/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Create + start a DQ job. job_type is one of rule_run|profile|freshness|schema|nl_check|suggest|anomaly.
 * rule_run/nl_check require rule_id; profile/freshness/schema/anomaly/suggest require data_table_id.
 */
export function createDQJob(token, data) {
  return apiFetch('dq/jobs/', { method: 'POST', token, body: data });
}

/**
 * Fetch a single job (Pulse jobs are refreshed server-side first).
 */
export function getDQJob(token, id) {
  return apiFetch(`dq/jobs/${id}/`, { token });
}

/**
 * Cancel a queued/running job (best-effort).
 */
export function cancelDQJob(token, id) {
  return apiFetch(`dq/jobs/${id}/cancel/`, { method: 'POST', token });
}

// =====================================================================
// DQ Suggestions — Pulse rule suggestions awaiting human review.
// =====================================================================

/**
 * List DQ suggestions (optionally filtered by status / data_table).
 */
export function listDQSuggestions(token, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null && v !== '') params.set(k, v); });
  const qs = params.toString();
  return apiFetch(`dq/suggestions/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Accept a suggestion → creates a real DQRule, returns it.
 */
export function acceptDQSuggestion(token, id) {
  return apiFetch(`dq/suggestions/${id}/accept/`, { method: 'POST', token });
}

/**
 * Reject a suggestion, optionally with a reason.
 */
export function rejectDQSuggestion(token, id, reason) {
  const body = reason ? { reason } : {};
  return apiFetch(`dq/suggestions/${id}/reject/`, { method: 'POST', token, body });
}

// =====================================================================
// DQ Anomalies — Pulse anomaly.detect results.
// =====================================================================

/**
 * List DQ anomalies (optionally filtered by data_table / severity / date / from / to).
 */
export function listDQAnomalies(token, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null && v !== '') params.set(k, v); });
  const qs = params.toString();
  return apiFetch(`dq/anomalies/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Fetch freshness checks (optionally filtered).
 * GET /dq/freshness/
 */
export function getFreshnessChecks(filters = {}, token) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null) params.set(k, v); });
  const qs = params.toString();
  return apiFetch(`dq/freshness/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Fetch schema snapshots.
 * GET /dq/schema-snapshots/
 */
export function getSchemaSnapshots(filters = {}, token) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null) params.set(k, v); });
  const qs = params.toString();
  return apiFetch(`dq/schema-snapshots/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Fetch schema changes.
 * GET /dq/schema-changes/
 */
export function getSchemaChanges(filters = {}, token) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null) params.set(k, v); });
  const qs = params.toString();
  return apiFetch(`dq/schema-changes/${qs ? `?${qs}` : ''}`, { token });
}
