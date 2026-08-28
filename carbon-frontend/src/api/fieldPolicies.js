// src/api/fieldPolicies.js
// Field-level access policies (column-level RBAC) + masking strategy wrappers.
// Backend: dataschema/policy_views.py (EPH-4A) + DataField.masking_strategy (EPH-4B).
// apiFetch-only — never raw fetch (RULE_10).

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/**
 * Fetch all access policies for a field.
 * GET dataschema/fields/{fieldId}/policies/
 * @param {string} token
 * @param {number|string} fieldId
 * @returns {Promise<Array>} [{ id, field, required_capability, action, created_by, created_at }]
 */
export function getFieldPolicies(token, fieldId) {
  return apiFetch(`${API_ROUTES.fields}${fieldId}/policies/`, { token });
}

/**
 * Create a field access policy. action ∈ 'deny' | 'mask'.
 * Backend returns 400 { detail } when (field, required_capability) already exists.
 * @param {string} token
 * @param {number|string} fieldId
 * @param {{ required_capability: string, action: 'deny'|'mask' }} data
 * @returns {Promise<Object>}
 */
export function createFieldPolicy(token, fieldId, data) {
  return apiFetch(`${API_ROUTES.fields}${fieldId}/policies/`, {
    method: "POST",
    body: { required_capability: data.required_capability, action: data.action },
    token,
  });
}

/**
 * Delete a field access policy (204).
 * @param {string} token
 * @param {number|string} fieldId
 * @param {number|string} policyId
 * @returns {Promise<void>}
 */
export function deleteFieldPolicy(token, fieldId, policyId) {
  return apiFetch(`${API_ROUTES.fields}${fieldId}/policies/${policyId}/`, {
    method: "DELETE",
    token,
  });
}

/**
 * Update a field's masking strategy. strategy ∈ 'none'|'redact'|'hash'|'truncate'|'null'.
 * PATCH dataschema/fields/{fieldId}/ — masking_strategy is writable on DataFieldSerializer.
 * @param {string} token
 * @param {number|string} fieldId
 * @param {string} strategy
 * @returns {Promise<Object>}
 */
export function updateFieldMaskingStrategy(token, fieldId, strategy) {
  return apiFetch(`${API_ROUTES.fields}${fieldId}/`, {
    method: "PATCH",
    body: { masking_strategy: strategy },
    token,
  });
}

/**
 * List all non-archived fields (admin panel).
 * The existing fetchDataSchemaFields() requires a data_table filter, so this helper
 * hits the unfiltered ModelViewSet route dataschema/fields/ instead and normalizes
 * CarbonPageNumberPagination envelopes ({ results: [...] }) to plain arrays.
 * @param {string} token
 * @param {number|string|null} project_id
 * @param {number|string|null} module_id
 * @returns {Promise<Array>}
 */
export async function fetchAllFields(token, project_id, module_id) {
  const data = await apiFetch(API_ROUTES.fields, { token, project_id, module_id });
  return Array.isArray(data) ? data : data?.results || [];
}
