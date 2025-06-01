// File: src/api/api.js

import { API_BASE_URL } from "../config";
import { isJwtExpired } from "../jwt";

/**
 * apiFetch - universal API call helper with JWT refresh, context, errors, and JSON parsing
 *
 * @param {string} endpoint - relative API endpoint (e.g. "/api/datacollection/item-definitions/")
 * @param {object} opts - { method, body, token, context_id }
 * @returns {Promise<any>} - parsed JSON response or throws error
 */
export async function apiFetch(endpoint, { method = "GET", body, token, context_id } = {}) {
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

  // --- CONTEXT INJECTION LOGIC ---
  // Only inject for /api/dataschema/ endpoints if context_id is provided
  const isDataSchema = /^\/api\/dataschema\//.test(endpoint);
  if (isDataSchema && context_id) {
    const hasQuery = url.includes("?");
    const alreadyHasContext = url.includes("context_id=");
    if (!alreadyHasContext) {
      url += (hasQuery ? "&" : "?") + "context_id=" + encodeURIComponent(context_id);
    }
    // Also inject into body for POST/PUT/PATCH if not present
    if (["POST", "PUT", "PATCH"].includes(method) && body && typeof body === "object" && !("context_id" in body)) {
      body.context_id = context_id;
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
      // Prefer backend detail error if available
      if (data && data.detail) throw new Error(data.detail);
      if (typeof data === "string" && data.length < 200) throw new Error(data);
      throw new Error("API error");
    }
    return data;
  }

  try {
    return await doFetch();
  } catch (err) {
    // If 401, try refresh, once
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