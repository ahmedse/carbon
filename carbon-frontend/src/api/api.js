// src/api/api.js
// Universal API client with JWT refresh, error, project/module handling.

import { API_BASE_URL } from "../config";
import { isJwtExpired } from "../jwt";

/**
 * Universal API call helper with JWT refresh, project/module params, errors, and JSON parsing.
 * Handles 401, auto-refresh, and robust error messages.
 *
 * @param {string} endpoint - relative API endpoint
 * @param {object} opts - { method, body, token, project_id, module_id }
 * @returns {Promise<any>}
 */
export async function apiFetch(endpoint, { method = "GET", body, token, project_id, module_id } = {}) {
  let url = `${API_BASE_URL}${endpoint}`;
  let accessToken = token || localStorage.getItem("access");

  // Debug: log initial request
  if (import.meta.env.DEV) {
    console.debug(`[apiFetch] ${method} ${url}`, { body, project_id, module_id });
  }

  // Refresh expired token, using global window.refreshAccessToken if present
  if (isJwtExpired(accessToken) && typeof window.refreshAccessToken === "function") {
    try {
      accessToken = await window.refreshAccessToken();
      if (import.meta.env.DEV) console.debug("Access token refreshed.");
    } catch (err) {
      if (typeof window.logout === "function") window.logout();
      throw new Error("Session expired. Please log in again.");
    }
  }

  let headers = {
    "Content-Type": "application/json",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  // Attach project_id/module_id as query params if /dataschema/ or /core/ endpoint
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

  // Helper to actually perform the fetch and parse result
  async function doFetch() {
    let response;
    try {
      response = await fetch(url, { method, headers, ...(body ? { body: JSON.stringify(body) } : {}) });
    } catch (networkError) {
      // Network error (server down, etc)
      throw new Error(`Network error: ${networkError.message || networkError}`);
    }
    const isJson = response.headers.get("content-type")?.includes("application/json");
    let data;
    try {
      data = isJson ? await response.json() : await response.text();
    } catch (parseError) {
      data = null;
    }

    if (!response.ok) {
      // Debug log for errors
      if (import.meta.env.DEV) {
        console.error("[apiFetch] API Error:", { url, method, status: response.status, data });
      }
      // Show backend error if available
      if (data && data.detail) throw new Error(data.detail);
      if (typeof data === "string" && data.length < 200) throw new Error(data);
      throw new Error(`API error (${response.status})`);
    }
    return data;
  }

  try {
    return await doFetch();
  } catch (err) {
    // Try token refresh on Unauthorized
    if (err.message === "Unauthorized" || /401/.test(err.message)) {
      try {
        accessToken = await window.refreshAccessToken();
        headers = { ...headers, Authorization: `Bearer ${accessToken}` };
        if (import.meta.env.DEV) console.debug("Retrying after token refresh...");
        return await doFetch();
      } catch {
        if (typeof window.logout === "function") window.logout();
        throw new Error("Session expired. Please log in again.");
      }
    }
    // Debug any other error
    if (import.meta.env.DEV) console.error("[apiFetch] Final error:", err);
    throw err;
  }
}