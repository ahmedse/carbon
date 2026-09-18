// src/api/aiRegistry.js
// Process Registry API wrappers (P3-05c). Thin read/write wrappers over the
// /carbon-api/ai/registry/processes/ endpoints — all through apiFetch
// (RULE_10, JWT auto-refresh). Consumed ONLY by pages/admin/ai/**.
//
// The backend is the CBAC authority: write actions return 403 {error, detail}
// when the caller lacks the required capability. The frontend renders every
// action but NEVER treats its own capability gating as authoritative.
import { apiFetch } from './api';

const BASE = 'ai/registry/processes/';

/**
 * List process definitions (latest per process_id).
 * @param {string} token
 * @param {{status?: string, processId?: string}} [opts]
 * @returns {Promise<Array>} [{process_id, version, owner, status, kill_switch, updated_at}]
 */
export function listProcesses(token, { status, processId } = {}) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (processId) params.append('process_id', processId);
  const qs = params.toString();
  return apiFetch(`${BASE}${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Create a draft from a full definition document.
 * @param {string} token
 * @param {object} document - full P3-03 definition JSON
 * @returns {Promise<object>} serialized definition (201)
 */
export function createProcess(token, document) {
  return apiFetch(BASE, { token, method: 'POST', body: document });
}

/**
 * Retrieve the latest definition for a process_id.
 * @param {string} token
 * @param {string} id - definition `process_id`
 * @returns {Promise<object>}
 */
export function getProcess(token, id) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/`, { token });
}

/**
 * Edit a draft (full/partial definition document).
 * @param {string} token
 * @param {string} id
 * @param {object} document
 * @returns {Promise<object>}
 */
export function updateProcess(token, id, document) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/`, {
    token,
    method: 'PATCH',
    body: document,
  });
}

/** Submit a draft → review. */
export function submitProcess(token, id) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/submit/`, {
    token,
    method: 'POST',
    body: {},
  });
}

/** Publish a review → active (server refuses self-publish with 403). */
export function publishProcess(token, id) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/publish/`, {
    token,
    method: 'POST',
    body: {},
  });
}

/** Deprecate an active → deprecated. */
export function deprecateProcess(token, id) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/deprecate/`, {
    token,
    method: 'POST',
    body: {},
  });
}

/**
 * Recursive diff of the latest draft/review vs the active version.
 * @returns {Promise<object>} {process_id, from_version, to_version, added,
 *   removed, changed} or {diff: null, reason: 'no_active_version'}.
 */
export function getDiff(token, id) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/diff/`, { token });
}

/** Effective autonomy dial per step: {step_id: autonomy}. */
export function getAutonomy(token, id) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/autonomy/`, { token });
}

/**
 * Set the autonomy dial. `dial` is a flat {step_id: autonomy} map.
 * autonomy ∈ observe|propose|act_confirm|act_notify|act_silent|human_only.
 */
export function setAutonomy(token, id, dial) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/autonomy/`, {
    token,
    method: 'PATCH',
    body: { dial },
  });
}

/** Set the kill switch: {enabled: bool}. */
export function setKillSwitch(token, id, enabled) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/kill/`, {
    token,
    method: 'POST',
    body: { enabled: Boolean(enabled) },
  });
}

/** Reject a review → draft with persisted reason. */
export function rejectProcess(token, id, reason) {
  return apiFetch(`${BASE}${encodeURIComponent(id)}/reject/`, {
    token,
    method: 'POST',
    body: { reason },
  });
}
