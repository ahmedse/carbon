// src/api/modules.js
// Module API wrappers.

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/**
 * Helper to build a query string from params object.
 * Not currently used, but available for future expansion.
 */
function buildQuery(params) {
  const esc = encodeURIComponent;
  return (
    Object.keys(params)
      .filter((k) => params[k] !== undefined && params[k] !== null)
      .map((k) => esc(k) + "=" + esc(params[k]))
      .join("&")
  );
}

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