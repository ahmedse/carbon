// carbon-frontend/src/api/dq.js
import { apiFetch } from './api';
import { API_BASE_URL, API_ROUTES } from '../config';

/**
 * Fetch org-scoped DQ metrics summary
 */
export async function getOrgDQMetrics(token) {
  return apiFetch(`${API_BASE_URL}dq/metrics/`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Fetch table-level DQ metrics and active rules
 * @param {number} tableId - DataTable ID
 * @param {string} token - Auth token
 */
export async function getTableDQMetrics(tableId, token) {
  return apiFetch(`${API_BASE_URL}dq/metrics/table/${tableId}/`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Fetch field-level DQ metrics
 * @param {number} fieldId - DataField ID
 * @param {string} token - Auth token
 */
export async function getFieldDQMetrics(fieldId, token) {
  return apiFetch(`${API_BASE_URL}dq/metrics/field/${fieldId}/`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Fetch DQ results for a specific table or rule
 * @param {Object} filters - Query filters { data_table, rule, etc }
 * @param {string} token - Auth token
 */
export async function getDQResults(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });

  const url = `${API_BASE_URL}dq/results/${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  return apiFetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Trigger on-demand DQ validation for a table
 * @param {number} tableId - DataTable ID
 * @param {string} token - Auth token
 */
export async function runDQValidation(tableId, token) {
  return apiFetch(`${API_BASE_URL}dq/run-validation/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      data_table: tableId,
    }),
  });
}

/**
 * Fetch all DQ rules (optionally filtered)
 * @param {Object} filters - Query filters { data_table, data_field, etc }
 * @param {string} token - Auth token
 */
export async function getDQRules(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });

  const url = `${API_BASE_URL}dq/rules/${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  return apiFetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Fetch table profiles
 * @param {Object} filters - Query filters { data_table, etc }
 * @param {string} token - Auth token
 */
export async function getTableProfiles(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });

  const url = `${API_BASE_URL}dq/table-profiles/${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  return apiFetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Fetch field profiles
 * @param {Object} filters - Query filters { data_table, data_field, etc }
 * @param {string} token - Auth token
 */
export async function getFieldProfiles(filters = {}, token) {
  const queryParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      queryParams.append(key, value);
    }
  });

  const url = `${API_BASE_URL}dq/field-profiles/${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  return apiFetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

// =====================================================================
// DQ Rule CRUD — clean wrappers using relative endpoints + apiFetch.
// apiFetch handles JWT validity/refresh; token is read from localStorage
// when not supplied. Do NOT prepend API_BASE_URL to these endpoints.
// =====================================================================

/**
 * List DQ rules for a table (and optionally a field).
 * @param {string} token
 * @param {{ data_table?: number|string, data_field?: number|string }} filters
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
