// src/utils/errorNormalizer.js
// Normalizes any error (fetch, API, network, auth, validation) into a standard shape.
// Wired into api.js apiFetch so ALL API errors flow through this normalizer.

/**
 * @typedef {Object} NormalizedError
 * @property {'network'|'auth'|'server'|'validation'|'not_found'|'unknown'} type
 * @property {string} message — human-readable
 * @property {boolean} canRetry
 * @property {number|null} status
 * @property {Object|null} feedback — original structured feedback envelope if present
 * @property {string} correlationId — unique id for support reference
 * @property {string} timestamp — ISO string
 */

let _correlationCounter = 0;

function generateCorrelationId() {
  _correlationCounter += 1;
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 6);
  return `${ts}-${rand}-${_correlationCounter}`;
}

/**
 * Classify an HTTP status code into a type.
 */
function classifyStatus(status) {
  if (!status) return "network";
  if (status === 401 || status === 403) return "auth";
  if (status === 404) return "not_found";
  if (status === 422 || status === 400) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

/**
 * Normalize any error into the standard shape.
 * @param {Error|Object} error — raw error from apiFetch catch block
 * @param {Object} [context] — additional context: { endpoint, method, status }
 * @returns {NormalizedError}
 */
export function normalizeError(error, context = {}) {
  const correlationId = generateCorrelationId();
  const timestamp = new Date().toISOString();
  const status = error?.status ?? context?.status ?? null;
  const feedback = error?.feedback ?? null;

  // Timeout / abort (check FIRST — Chrome may throw TypeError instead of AbortError on abort)
  if (
    error?.name === "AbortError" ||
    error?.message === "Request timed out"
  ) {
    return {
      type: "network",
      message: "The request timed out. Please try again.",
      canRetry: true,
      status: null,
      feedback: null,
      correlationId,
      timestamp,
    };
  }

  // Network / fetch failure (only when NOT an abort/timeout)
  if (
    !status &&
    (error?.message === "Failed to fetch" ||
      error?.message === "Network error" ||
      error?.name === "TypeError")
  ) {
    return {
      type: "network",
      message: "Unable to reach the server. Check your connection and try again.",
      canRetry: true,
      status: null,
      feedback: null,
      correlationId,
      timestamp,
    };
  }

  // Auth (401/403)
  if (classifyStatus(status) === "auth") {
    return {
      type: "auth",
      message:
        status === 401
          ? feedback?.detail || "Your session has expired. Please sign in again."
          : feedback?.detail || "You don't have permission to perform this action.",
      canRetry: false,
      status,
      feedback,
      correlationId,
      timestamp,
    };
  }

  // Not found / Validation / Server — delegate to classifier
  const type = classifyStatus(status);
  if (type === "not_found") {
    return {
      type: "not_found",
      message: feedback?.detail || "The requested resource was not found.",
      canRetry: false,
      status,
      feedback,
      correlationId,
      timestamp,
    };
  }

  if (type === "validation") {
    return {
      type: "validation",
      message: feedback?.detail || error?.message || "The request was invalid.",
      canRetry: false,
      status,
      feedback,
      correlationId,
      timestamp,
    };
  }

  if (type === "server") {
    return {
      type: "server",
      message: "Something went wrong on our end. Our team has been notified.",
      canRetry: true,
      status,
      feedback,
      correlationId,
      timestamp,
    };
  }

  // Unknown / fallback
  return {
    type: "unknown",
    message: error?.message || "An unexpected error occurred.",
    canRetry: true,
    status,
    feedback,
    correlationId,
    timestamp,
  };
}
