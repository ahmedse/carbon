// src/api/api.js

import { API_BASE_URL } from "../config";
import { isJwtExpired } from "../jwt";

/**
 * Refresh the access token using refresh token in localStorage.
 * Returns new access token string or throws.
 */
async function refreshAccessToken() {
  const refresh = localStorage.getItem("refresh");
  if (!refresh) throw new Error("No refresh token");
  const res = await fetch(`${API_BASE_URL}/api/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) throw new Error("Session expired");
  const data = await res.json();
  if (!data.access) throw new Error("No new access token");
  localStorage.setItem("access", data.access);
  return data.access;
}

/**
 * Logs out globally: clears user storage and redirects to login with expired param.
 */
function globalLogout() {
  localStorage.clear();
  window.location.href = "/login?expired=1";
}

/**
 * Universal API call helper with JWT refresh, project/module params, errors, and JSON parsing.
 * Handles 401, auto-refresh, and robust error messages.
 */
export async function apiFetch(
  endpoint,
  { method = "GET", body, token, project_id, module_id } = {}
) {
  let url = `${API_BASE_URL}${endpoint}`;
  let accessToken = token || localStorage.getItem("access");

  // Attach project_id/module_id as query params if needed
  const isDataSchemaOrCore = /^\/(dataschema|core)\//.test(endpoint) || /^\/api\/(dataschema|core)\//.test(endpoint);
  if (isDataSchemaOrCore) {
    const params = [];
    if (project_id) params.push(`project_id=${encodeURIComponent(project_id)}`);
    if (module_id) params.push(`module_id=${encodeURIComponent(module_id)}`);
    if (params.length) {
      url += (url.includes("?") ? "&" : "?") + params.join("&");
    }
    if (
      ["POST", "PUT", "PATCH"].includes(method) &&
      body &&
      typeof body === "object"
    ) {
      if (project_id && !("project_id" in body)) body.project_id = project_id;
      if (module_id && !("module_id" in body)) body.module_id = module_id;
    }
  }

  // Always ensure access token is fresh
  if (isJwtExpired(accessToken)) {
    try {
      accessToken = await refreshAccessToken();
    } catch (e) {
      globalLogout();
      return;
    }
  }

  let headers = {
    "Content-Type": "application/json",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  async function doFetch() {
    let response;
    try {
      response = await fetch(url, {
        method,
        headers,
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
    } catch (networkError) {
      console.error("Network error:", networkError);
      throw new Error("Network error");
    }
    const isJson = response.headers.get("content-type")?.includes("application/json");
    let data;
    try {
      data = isJson ? await response.json() : await response.text();
    } catch (parseError) {
      data = null;
    }

    // Check for token errors
    if (!response.ok) {
      if (
        data &&
        (data.code === "token_not_valid" ||
          data.detail === "Given token not valid for any token type" ||
          response.status === 401)
      ) {
        // Try to refresh and retry **once**
        try {
          accessToken = await refreshAccessToken();
          headers.Authorization = `Bearer ${accessToken}`;
          // retry
          response = await fetch(url, {
            method,
            headers,
            ...(body ? { body: JSON.stringify(body) } : {}),
          });
          const retryData = response.headers.get("content-type")?.includes("application/json")
            ? await response.json()
            : await response.text();
          if (!response.ok) {
            globalLogout();
            return;
          }
          return retryData;
        } catch (refreshErr) {
          globalLogout();
          return;
        }
      }
      // Other errors: propagate
      throw new Error(
        (data && (data.detail || data.message)) ||
          `API Error: ${response.status}`
      );
    }
    return data;
  }

  return await doFetch();
}