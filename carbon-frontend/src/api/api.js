// src/api/api.js

import { API_BASE_URL, API_ROUTES } from "../config";
import { isJwtExpired } from "../jwt";

/** Joins base URL and path, stripping duplicate slashes. */
function joinUrl(base, path) {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

/** Builds a query string from params object (ignores undefined/null/empty). */
function buildQuery(params) {
  return Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}

/** Returns true if endpoint should receive project/module params. */
function needsProjectModuleParams(endpoint) {
  const ep = endpoint.replace(/^\/+/, "");
  return (
    ep.startsWith("core/") ||
    ep.startsWith("dataschema/") ||
    ep.startsWith("api/core/") ||
    ep.startsWith("api/dataschema/")
  );
}

/** Sanitizes URL: merges all query params after all '?', ensures only one '?'. */
function sanitizeUrl(url) {
  const [base, ...rest] = url.split("?");
  const params = new URLSearchParams();
  rest.forEach(queryPart => {
    for (const [k, v] of new URLSearchParams(queryPart).entries()) {
      params.append(k, v);
    }
  });
  return params.toString() ? `${base}?${params.toString()}` : base;
}

/** Refreshes the access token using refresh token in localStorage. */
async function refreshAccessToken() {
  const refresh = localStorage.getItem("refresh");
  if (!refresh) throw new Error("No refresh token");
  const res = await fetch(joinUrl(API_BASE_URL, API_ROUTES.tokenRefresh), { // internal refresh helper
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) throw new Error("Session expired");
  const data = await res.json();
  if (!data.access) throw new Error("No new access token");
  localStorage.setItem("access", data.access);
  if (data.refresh) localStorage.setItem("refresh", data.refresh);
  return data.access;
}

/** Returns the currently valid access token, refreshing if expired. */
async function getValidAccessToken(token) {
  let accessToken = token || localStorage.getItem("access");
  const refresh = localStorage.getItem("refresh");

  if (!accessToken) {
    if (refresh) {
      try {
        accessToken = await refreshAccessToken();
      } catch (e) {
        globalLogout();
        throw new Error("Session expired");
      }
    }
    return accessToken;
  }

  if (isJwtExpired(accessToken)) {
    try {
      accessToken = await refreshAccessToken();
    } catch (e) {
      globalLogout();
      throw new Error("Session expired");
    }
  }

  return accessToken;
}

/** Performs a fetch with authentication and optional retry on 401. */
export async function authFetch(
  endpoint,
  {
    method = "GET",
    body,
    token,
    project_id,
    module_id,
    timeoutMs = 15000,
    headers: customHeaders = {},
  } = {}
) {
  let url = joinUrl(API_BASE_URL, endpoint);
  let accessToken = await getValidAccessToken(token || localStorage.getItem('access'));

  if (needsProjectModuleParams(endpoint)) {
    const [basePath, existingParams] = url.split("?");
    const merged = new URLSearchParams(existingParams || "");
    if (project_id) merged.set("project_id", project_id);
    if (module_id) merged.set("module_id", module_id);
    url = merged.toString() ? `${basePath}?${merged.toString()}` : basePath;
  }

  url = sanitizeUrl(url);

  const headers = {
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    ...customHeaders,
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const fetchOptions = {
    method,
    headers,
    signal: controller.signal,
    ...(body instanceof FormData ? { body } : body ? { body: JSON.stringify(body) } : {}),
  };

  let response;
  try {
    response = await fetch(url, fetchOptions); // internal api helper
    clearTimeout(timeout);

    if (response.status === 401 && accessToken) {
      // Try refreshing once
      accessToken = await refreshAccessToken();
      headers.Authorization = `Bearer ${accessToken}`;
      response = await fetch(url, { ...fetchOptions, headers }); // retry after refresh
      clearTimeout(timeout);
    }

    return response;
  } catch (error) {
    clearTimeout(timeout);
    if (error.name === "AbortError") {
      throw new Error("Request timed out");
    }
    if (error.message === "Failed to fetch") {
      throw new Error("Network error");
    }
    console.error('🔴 authFetch Catch Block:', {
      endpoint,
      method,
      errorMessage: error.message,
      errorStack: error.stack,
      timestamp: new Date().toISOString(),
    });
    throw error;
  }
}

/** Logs out globally: clears user storage and redirects to login with expired param. */
function globalLogout() {
  localStorage.clear();
  window.location.href = `${import.meta.env.VITE_BASE}login?expired=1`;
}

/**
 * Universal API call helper with JWT refresh, robust param handling, errors, JSON parsing, and optional timeout.
 * @param {string} endpoint - API endpoint, relative to API_BASE_URL
 * @param {object} opts - Options: method, body, token, project_id, module_id, timeoutMs, headers
 */
export async function apiFetch(
  endpoint,
  {
    method = "GET",
    body,
    token,
    project_id,
    module_id,
    timeoutMs = 15000, // 15s default timeout
    headers: customHeaders = {},
  } = {}
) {
  let url = joinUrl(API_BASE_URL, endpoint);
  let accessToken = token || localStorage.getItem("access");

  // Build query params robustly
  if (needsProjectModuleParams(endpoint)) {
    // Collect params from both the endpoint and the function call
    const [basePath, existingParams] = url.split("?");
    const merged = new URLSearchParams(existingParams || "");
    if (project_id) merged.set("project_id", project_id);
    if (module_id) merged.set("module_id", module_id);
    url = merged.toString() ? `${basePath}?${merged.toString()}` : basePath;

    // For mutating methods, add to body too (but do not overwrite explicitly set values)
    if (
      ["POST", "PUT", "PATCH"].includes(method) &&
      body &&
      typeof body === "object"
    ) {
      if (project_id && !("project_id" in body)) body.project_id = project_id;
      if (module_id && !("module_id" in body)) body.module_id = module_id;
    }
  }

  // Final robust cleanup: remove duplicate/malformed ? in case of legacy code
  url = sanitizeUrl(url);

  // Debug logging (only in development)
  if (
    typeof process !== "undefined" &&
    process.env.NODE_ENV === "development"
  ) {
    // Do NOT log sensitive tokens
    console.debug("[apiFetch]", { endpoint, method, url, project_id, module_id, body });
  }

  // Ensure access token is fresh
  if (accessToken && isJwtExpired(accessToken)) {
    try {
      accessToken = await refreshAccessToken();
    } catch (e) {
      globalLogout();
      throw new Error("Session expired");
    }
  }

  const headers = {
    "Content-Type": "application/json",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    ...customHeaders,
  };

  // Use AbortController for timeout
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  let responseData;

  try {
    response = await fetch(url, { // internal apiFetch
      method,
      headers,
      signal: controller.signal,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    clearTimeout(timeout);

    const isJson = response.headers.get("content-type")?.includes("application/json");
    responseData = isJson ? await response.json() : await response.text();

    // Handle token errors: try refresh exactly once
    if (
      !response.ok &&
      response.status === 401 &&
      accessToken // don't retry if no token at all
    ) {
      try {
        accessToken = await refreshAccessToken();
        headers.Authorization = `Bearer ${accessToken}`;
        // Retry request after token refresh
        response = await fetch(url, { // retry after refresh
          method,
          headers,
          signal: controller.signal,
          ...(body ? { body: JSON.stringify(body) } : {}),
        });
        clearTimeout(timeout);
        const retryIsJson = response.headers.get("content-type")?.includes("application/json");
        responseData = retryIsJson ? await response.json() : await response.text();
      } catch (refreshError) {
        globalLogout();
        throw new Error("Session expired");
      }
    }

    // Check for fatal errors and propagate with detail
    if (!response.ok) {
      const feedback =
        responseData && typeof responseData === "object"
          ? responseData.feedback
          : null;
      const detail =
        feedback?.detail ||
        (responseData && (responseData.detail || responseData.message)) ||
        `API Error: ${response.status}`;
      
      // ===== COMPREHENSIVE ERROR LOGGING =====
      const errorLog = {
        timestamp: new Date().toISOString(),
        endpoint,
        method,
        status: response.status,
        detail,
        requestBody: body,
        responseData,
        responseHeaders: Object.fromEntries(response.headers.entries()),
      };
      
      // Log to console with table format for readability
      console.group(`🔴 API ERROR - ${method} ${endpoint}`);
      console.error('Status:', response.status);
      console.error('Detail:', detail);
      console.error('Request:', { method, endpoint, body });
      console.error('Response:', responseData);
      console.table(errorLog);
      console.groupEnd();
      
      // Store in sessionStorage for backend inspection
      try {
        const errorHistory = JSON.parse(sessionStorage.getItem('api_errors') || '[]');
        errorHistory.push(errorLog);
        if (errorHistory.length > 50) errorHistory.shift(); // Keep last 50
        sessionStorage.setItem('api_errors', JSON.stringify(errorHistory));
      } catch (e) {
        console.warn('Failed to store error history:', e);
      }
      
      const err = new Error(detail);
      if (feedback) err.feedback = feedback;
      err.status = response.status;
      throw err;
    }

    return responseData;
  } catch (error) {
    clearTimeout(timeout);
    if (error.name === "AbortError") {
      throw new Error("Request timed out");
    }
    if (error.message === "Failed to fetch") {
      throw new Error("Network error");
    }
    
    // Log unexpected errors
    console.error('🔴 apiFetch Catch Block:', {
      endpoint,
      method,
      errorMessage: error.message,
      errorStack: error.stack,
      timestamp: new Date().toISOString(),
    });
    
    // If not already logged out, propagate error message
    throw error;
  }
}