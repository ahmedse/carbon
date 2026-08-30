// src/api/api.js

import { API_BASE_URL, API_ROUTES } from "../config";
import { isJwtExpired } from "../jwt";
import { normalizeError } from "../utils/errorNormalizer";

/** Joins base URL and path, stripping duplicate slashes. */
function joinUrl(base, path) {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
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

// ── Refresh serialization ────────────────────────────────────────────────
// SimpleJWT rotates refresh tokens and blacklists the old one. Two concurrent
// refresh calls (10-min interval + tab-focus refresh, or parallel 401 retries)
// race: the first rotates, the second is rejected with 401 on the now-
// blacklisted token and would force a spurious logout. Share one in-flight
// promise so all callers await the SAME refresh.
let refreshInFlight = null;
let lastRefreshTimestamp = 0;

/** Refreshes the access token using refresh token in localStorage. */
export async function refreshAccessToken() {
  // If a refresh is already in-flight, return the same promise
  // so all callers get the SAME new token (prevents rotation race).
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh = localStorage.getItem("refresh");
    if (!refresh) throw new Error("No refresh token");
    const res = await fetch(joinUrl(API_BASE_URL, API_ROUTES.tokenRefresh), { // internal refresh helper
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) {
      // Refresh token is dead — redirect immediately so visibility-handler retries can't loop
      lastRefreshTimestamp = 0;
      globalLogout();
      throw new Error("Session expired");
    }
    const data = await res.json();
    if (!data.access) throw new Error("No new access token");
    localStorage.setItem("access", data.access);
    if (data.refresh) localStorage.setItem("refresh", data.refresh);
    lastRefreshTimestamp = Date.now();
    return data.access;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/** Returns timestamp of last successful refresh (for 401 retry dedup logic). */
export function getLastRefreshTimestamp() {
  return lastRefreshTimestamp;
}

/** Returns the currently valid access token, refreshing if expired. */
async function getValidAccessToken(token) {
  let accessToken = token || localStorage.getItem("access");
  const refresh = localStorage.getItem("refresh");

  if (!accessToken) {
    if (refresh) {
      try {
        accessToken = await refreshAccessToken();
      } catch (_e) {
        globalLogout();
        throw new Error("Session expired");
      }
    }
    return accessToken;
  }

  if (isJwtExpired(accessToken)) {
    try {
      accessToken = await refreshAccessToken();
    } catch (_e) {
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

    // If 401 and we haven't just refreshed (within 2s), try refresh once
    const timeSinceLastRefresh = Date.now() - getLastRefreshTimestamp();
    const justRefreshed = timeSinceLastRefresh < 2000;

    if (response.status === 401 && accessToken && !justRefreshed) {
      try {
        accessToken = await refreshAccessToken();
        headers.Authorization = `Bearer ${accessToken}`;
        response = await fetch(url, { ...fetchOptions, headers }); // retry after refresh
        clearTimeout(timeout);
      } catch (_refreshError) {
        globalLogout();
        throw new Error("Session expired");
      }
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
    typeof import.meta.env !== "undefined" &&
    import.meta.env.MODE === "development"
  ) {
    // Do NOT log sensitive tokens
    console.debug("[apiFetch]", { endpoint, method, url, project_id, module_id, body });
  }

  // Ensure access token is fresh
  if (accessToken && isJwtExpired(accessToken)) {
    try {
      accessToken = await refreshAccessToken();
    } catch (_e) {
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

    // Handle token errors: try refresh exactly once.
    // If a refresh happened recently (within 2s), skip the retry — we just
    // refreshed, so a 401 now means the problem is NOT the token.
    const timeSinceLastRefresh = Date.now() - getLastRefreshTimestamp();
    const justRefreshed = timeSinceLastRefresh < 2000; // 2-second window

    if (
      !response.ok &&
      response.status === 401 &&
      accessToken &&
      !justRefreshed
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
      } catch (_refreshError) {
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

      const normalized = normalizeError(
        { message: detail, status: response.status, feedback },
        { endpoint, method }
      );
      const err = new Error(normalized.message);
      err.normalized = normalized;
      err.feedback = feedback;
      err.status = response.status;
      // Attach raw payload so callers can map DRF field errors per-field.
      err.data = responseData;
      throw err;
    }

    return responseData;
  } catch (error) {
    clearTimeout(timeout);
    // Detect AbortController timeout (including Chrome quirk where abort throws TypeError)
    let err = error;
    if (error.name === "AbortError" || controller.signal.aborted) {
      err = new Error("Request timed out");
    }
    // Normalize all errors through the standard shape
    const normalized = normalizeError(
      err,
      { endpoint, method, status: err.status }
    );
    const finalErr = new Error(normalized.message);
    finalErr.normalized = normalized;
    if (err.feedback) finalErr.feedback = err.feedback;
    if (err.status) finalErr.status = err.status;
    if (err.data !== undefined) finalErr.data = err.data;
    throw finalErr;
  }
}

/**
 * Streaming variant of authFetch for Server-Sent Events (SSE).
 *
 * Resolves a valid access token via the shared `getValidAccessToken`
 * (refresh-if-expired, logout-on-failure), opens the stream with a single
 * `fetch`, and on 401 mirrors `authFetch`'s refresh-once-and-retry. Returns
 * the RAW `Response` WITHOUT consuming the body, so callers can read
 * `response.body` (e.g. via `response.body.getReader()`).
 *
 * @param {string} endpoint - endpoint relative to API_BASE_URL
 * @param {object} opts - { token, headers, signal }
 * @returns {Promise<Response>}
 */
export async function apiFetchStream(
  endpoint,
  { token, headers: customHeaders = {}, signal } = {}
) {
  let url = joinUrl(API_BASE_URL, endpoint);
  url = sanitizeUrl(url);

  let accessToken = await getValidAccessToken(
    token || localStorage.getItem("access")
  );

  const headers = {
    Accept: "text/event-stream",
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    ...customHeaders,
  };

  let response;
  try {
    response = await fetch(url, { method: "GET", headers, signal });

    // Mirror authFetch: on 401 (and not just-refreshed), refresh once and retry.
    const timeSinceLastRefresh = Date.now() - getLastRefreshTimestamp();
    const justRefreshed = timeSinceLastRefresh < 2000;

    if (response.status === 401 && accessToken && !justRefreshed) {
      try {
        accessToken = await refreshAccessToken();
        headers.Authorization = `Bearer ${accessToken}`;
        response = await fetch(url, { method: "GET", headers, signal });
      } catch (_refreshError) {
        globalLogout();
        throw new Error("Session expired");
      }
    }

    if (!response.ok) {
      const normalized = normalizeError(
        { message: `API Error: ${response.status}`, status: response.status },
        { endpoint, method: "GET" }
      );
      const err = new Error(normalized.message);
      err.normalized = normalized;
      err.status = response.status;
      throw err;
    }

    return response;
  } catch (error) {
    if (error.name === "AbortError") {
      throw error; // intentional close — caller distinguishes abort
    }
    if (error.message === "Failed to fetch") {
      throw new Error("Network error");
    }
    throw error;
  }
}