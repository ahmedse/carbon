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
 * Trigger on-demand DQ validation for a table
 */
export function runDQValidation(tableId, token) {
  return apiFetch('dq/run-validation/', { method: 'POST', token, body: { data_table: tableId } });
}

/**
 * Fetch all DQ rules (optionally filtered)
 */
export function getDQRules(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });
  const qs = queryParams.toString();
  return apiFetch(`dq/rules/${qs ? `?${qs}` : ''}`, { token });
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
 * Delete a DQ rule.
 */
export function deleteDQRule(token, id) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/`, { method: 'DELETE', token });
}

/**
 * Execute a DQ rule now. Returns the created DQResult.
 */
export function executeDQRule(token, id) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/execute/`, { method: 'POST', token });
}

export function getDQRuleHistory(token, id) {
  return apiFetch(`${API_ROUTES.dqRules}${id}/history/`, { token });
}

/**
 * Run ALL active DQ rules for a table against real rows (the real engine).
 * Writes DQResults and rolls up quality_status/score to the catalog asset.
 * Server-enforced admin-only (is_superuser | is_staff).
 * @param {string} token
 * @param {number|string} tableId
 */
export function runTableValidation(token, tableId) {
  return apiFetch('dq/run-validation/', {
    method: 'POST',
    token,
    body: { data_table: tableId },
  });
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
