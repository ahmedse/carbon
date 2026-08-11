// src/api/modules.js
// Module API wrappers.

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/**
 * Fetch modules for a given project (and optional module_id).
 * @param {string} token 
 * @param {string|number} project_id 
 * @param {string|number} [module_id] 
 * @returns {Promise<any>}
 */
export function fetchModules(token, project_id, module_id) {
  return apiFetch(API_ROUTES.modules, { token, project_id, module_id });
}

/**
 * Create a new Data Product (Module).
 * @param {string} token
 * @param {{name:string, description?:string, scope?:number, org_unit?:number|null}} data
 */
export function createModule(token, data) {
  return apiFetch(API_ROUTES.modules, { method: "POST", token, body: data });
}

/**
 * Update an existing Data Product (Module).
 * @param {string} token
 * @param {string|number} id
 * @param {object} data
 */
export function updateModule(token, id, data) {
  return apiFetch(`${API_ROUTES.modules}${id}/`, { method: "PATCH", token, body: data });
}

/**
 * Delete a Data Product (Module).
 * @param {string} token
 * @param {string|number} id
 */
export function deleteModule(token, id) {
  return apiFetch(`${API_ROUTES.modules}${id}/`, { method: "DELETE", token });
}

/**
 * Fetch a single Data Product (Module) by id.
 * @param {string} token
 * @param {string|number} id
 * @returns {Promise<any>}
 */
export function fetchModule(token, id) {
  return apiFetch(`${API_ROUTES.modules}${id}/`, { token });
}

/**
 * Fetch aggregate DQ summary for a Data Product's tables.
 * @param {string} token
 * @param {string|number} id
 * @returns {Promise<{total:number, passing:number, warning:number, failing:number, unknown:number, avg_score:number|null}>}
 */
export function fetchModuleQualitySummary(token, id) {
  return apiFetch(`${API_ROUTES.modules}${id}/quality_summary/`, { token });
}

/**
 * Fetch governance audit trail for a Data Product and its tables.
 * @param {string} token
 * @param {string|number} id
 * @returns {Promise<Array>}
 */
export function fetchModuleAuditTrail(token, id) {
  return apiFetch(`${API_ROUTES.modules}${id}/audit_trail/`, { token });
}