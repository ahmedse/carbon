// carbon-frontend/src/api/dq.js
import { apiFetch } from './api';
import { API_BASE_URL, API_ROUTES } from '../config';

/**
 * Data Quality API Integration
 * Provides scoped access to DQ metrics, rules, and results
 */

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
