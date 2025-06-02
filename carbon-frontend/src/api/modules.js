// File: src/api/modules.js

import { apiFetch } from "./api";

// Helper to build query string
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
 * Fetch modules, always sending context_id in query string.
 * @param {string} token 
 * @param {string|number} context_id 
 * @param {string|number} [module_id] 
 * @returns {Promise<any>}
 */
export function fetchModules(token, context_id, module_id) {
  const params = {};
  if (context_id) params.context_id = context_id;
  if (module_id) params.module_id = module_id;
  const query = buildQuery(params);
  return apiFetch(`/api/core/modules/${query ? "?" + query : ""}`, { token });
}