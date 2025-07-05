// src/api/api.js

import { API_BASE_URL } from "../config";
import { isJwtExpired } from "../jwt";

/**
 * apiFetch - universal API call helper with JWT refresh, project/module params, errors, and JSON parsing
 *
 * @param {string} endpoint - relative API endpoint (e.g. "/dataschema/tables/")
 * @param {object} opts - { method, body, token, project_id, module_id }
 * @returns {Promise<any>} - parsed JSON response or throws error
 */
export async function apiFetch(endpoint, { method = "GET", body, token, project_id, module_id } = {}) {
  let url = `${API_BASE_URL}${endpoint}`;
  let accessToken = token || localStorage.getItem("access");

  // Refresh expired token
  if (isJwtExpired(accessToken) && typeof window.refreshAccessToken === "function") {
    try {
      accessToken = await window.refreshAccessToken();
    } catch {
      if (typeof window.logout === "function") window.logout();
      throw new Error("Session expired. Please log in again.");
    }
  }

  let headers = {
    "Content-Type": "application/json",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  // --- PROJECT/MODULE PARAM INJECTION LOGIC ---
  // For /dataschema/ or /core/ endpoints, always append project_id, module_id if present
  const isDataSchemaOrCore = /^\/(dataschema|core)\//.test(endpoint) || /^\/api\/(dataschema|core)\//.test(endpoint);
  if (isDataSchemaOrCore) {
    const params = [];
    if (project_id) params.push(`project_id=${encodeURIComponent(project_id)}`);
    if (module_id) params.push(`module_id=${encodeURIComponent(module_id)}`);
    if (params.length) {
      url += (url.includes("?") ? "&" : "?") + params.join("&");
    }
    // Also inject into body for POST/PUT/PATCH if not present
    if (["POST", "PUT", "PATCH"].includes(method) && body && typeof body === "object") {
      if (project_id && !("project_id" in body)) body.project_id = project_id;
      if (module_id && !("module_id" in body)) body.module_id = module_id;
    }
  }

  // Helper for making fetch and parsing error+json
  async function doFetch() {
    const res = await fetch(url, { method, headers, ...(body ? { body: JSON.stringify(body) } : {}) });
    const isJson = res.headers.get("content-type")?.includes("application/json");
    let data;
    try {
      data = isJson ? await res.json() : await res.text();
    } catch {
      data = null;
    }

    if (!res.ok) {
      if (data && data.detail) throw new Error(data.detail);
      if (typeof data === "string" && data.length < 200) throw new Error(data);
      throw new Error("API error");
    }
    return data;
  }

  try {
    return await doFetch();
  } catch (err) {
    if (err.message === "Unauthorized" || /401/.test(err.message)) {
      try {
        accessToken = await window.refreshAccessToken();
        headers = { ...headers, Authorization: `Bearer ${accessToken}` };
        return await doFetch();
      } catch {
        if (typeof window.logout === "function") window.logout();
        throw new Error("Session expired. Please log in again.");
      }
    }
    throw err;
  }
}