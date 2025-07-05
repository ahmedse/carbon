// src/api/modules.js

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

// Helper to build query string (if needed for other calls)
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
 * Fetch modules, always sending project_id (and module_id if needed).
 * @param {string} token 
 * @param {string|number} project_id 
 * @param {string|number} [module_id] 
 * @returns {Promise<any>}
 */
export function fetchModules(token, project_id, module_id) {
  return apiFetch(API_ROUTES.modules, { token, project_id, module_id });
}