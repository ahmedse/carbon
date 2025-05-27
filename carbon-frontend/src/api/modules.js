// File: src/api/modules.js

import { apiFetch } from "./api";

// Helper to build query string
function buildQuery(params) {
  const esc = encodeURIComponent;
  return (
    Object.keys(params)
      .map((k) => esc(k) + "=" + esc(params[k]))
      .join("&")
  );
}

export async function fetchModules(token, project_id) {
  const query = buildQuery({ project_id });
  return apiFetch(`/api/core/modules/?${query}`, { token });
}