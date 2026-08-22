// src/api/aiCatalog.js
// W3-G — AI Admin catalog + topology + run timeline API wrappers (admin
// OBSERVE + MANAGE surface). Thin read/write wrappers over the federated
// agent catalog, the declared topology graph, the skill catalog and the
// durable run timeline — all through apiFetch (RULE_10, JWT auto-refresh).
//
// Surface rule: this module is consumed ONLY by pages/admin/ai/** — never by
// the AI Workspace (src/shell/**). Catalog writes (create/update/delete) are
// staff-gated server-side ({error:'admin_required'} → 403); replay is a
// RULE_21 consent gate ({confirm: true}).
import { apiFetch } from './api';

const BASE_CATALOG = 'ai/catalog/';
const BASE_RUNS = 'ai/runs/';

/**
 * List catalog agents, optionally filtered by role.
 * @param {string} token
 * @param {{role?: string}} [opts]
 * @returns {Promise<Array>} agent catalog rows
 */
export function listAgents(token, { role } = {}) {
  const qs = role ? `?role=${encodeURIComponent(role)}` : '';
  return apiFetch(`${BASE_CATALOG}${qs}`, { token });
}

/**
 * One agent: metadata, incoming/outgoing handoffs, admitted skills,
 * last admission log.
 * @param {string} token
 * @param {string} id
 * @returns {Promise<object>}
 */
export function getAgent(token, id) {
  return apiFetch(`${BASE_CATALOG}${encodeURIComponent(id)}/`, { token });
}

/**
 * Register a new agent (admin-gated). `name` is the engine upsert key.
 * @param {string} token
 * @param {{name: string, role: string, tool_set?: string[], playbook_blocks?: string[], model_override?: string, max_turns?: number}} body
 * @returns {Promise<object>} created agent
 */
export function createAgent(token, body) {
  return apiFetch(`${BASE_CATALOG}`, { token, method: 'POST', body });
}

/**
 * Update an agent in place (admin-gated). NOTE: `name` is intentionally NOT
 * sent — the backend update serializer omits it (rename = delete + create).
 * @param {string} token
 * @param {string} id
 * @param {{role?: string, tool_set?: string[], playbook_blocks?: string[], model_override?: string, max_turns?: number}} body
 * @returns {Promise<object>} updated agent
 */
export function updateAgent(token, id, body) {
  return apiFetch(`${BASE_CATALOG}${encodeURIComponent(id)}/`, {
    token,
    method: 'PATCH',
    body,
  });
}

/**
 * Soft-delete an agent (admin-gated).
 * @param {string} token
 * @param {string} id
 * @returns {Promise<{id: string, deleted: boolean}>}
 */
export function deleteAgent(token, id) {
  return apiFetch(`${BASE_CATALOG}${encodeURIComponent(id)}/`, {
    token,
    method: 'DELETE',
  });
}

/**
 * The system's DECLARED graph (ADR-001): agents + declared handoffs.
 * @param {string} token
 * @returns {Promise<{nodes: Array<{id, name, role, status}>, edges: Array<{from, to, description, max_parallel}>}>}
 */
export function getTopology(token) {
  return apiFetch(`${BASE_CATALOG}topology/`, { token });
}

/**
 * Skill catalog with each skill's latest admission-gate verdict.
 * @param {string} token
 * @returns {Promise<Array>} skill rows
 */
export function listSkills(token) {
  return apiFetch(`${BASE_CATALOG}skills/`, { token });
}

/**
 * Request-time federated index: DB agents (source of truth) + plugin
 * discovery. Read-only.
 * @param {string} token
 * @param {{role?: string}} [opts]
 * @returns {Promise<{source: string, db_is_source_of_truth: boolean, agents: Array, plugins: Array}>}
 */
export function getFederatedIndex(token, { role } = {}) {
  const qs = role ? `?role=${encodeURIComponent(role)}` : '';
  return apiFetch(`${BASE_CATALOG}index/${qs}`, { token });
}

/**
 * Ordered event log for a run (read-only, fail-visible).
 * @param {string} token
 * @param {string} runId
 * @returns {Promise<{run_id: string, status: string, events: Array<{t, kind, step_id?, detail?}>}>}
 */
export function getRunTimeline(token, runId) {
  return apiFetch(`${BASE_RUNS}${encodeURIComponent(runId)}/timeline/`, { token });
}

/**
 * Crash-safe resume (reconcile + re-enter). POST with no body.
 * @param {string} token
 * @param {string} runId
 * @returns {Promise<object>}
 */
export function resumeRun(token, runId) {
  return apiFetch(`${BASE_RUNS}${encodeURIComponent(runId)}/resume/`, {
    token,
    method: 'POST',
  });
}

/**
 * Consent-gated replay staging (RULE_21 — explicit {confirm: true}). Stages
 * only — replay never auto-executes.
 * @param {string} token
 * @param {string} runId
 * @returns {Promise<object>}
 */
export function replayRun(token, runId) {
  return apiFetch(`${BASE_RUNS}${encodeURIComponent(runId)}/replay/`, {
    token,
    method: 'POST',
    body: { confirm: true },
  });
}

/**
 * Side-by-side diff of two runs' step ledgers (read-only).
 * @param {string} token
 * @param {string} runAId
 * @param {string} runBId
 * @returns {Promise<{a: object, b: object, status_changed: boolean, step_diff: Array, diverged_steps: Array}>}
 */
export function compareRuns(token, runAId, runBId) {
  const qs = new URLSearchParams({ a: runAId, b: runBId });
  return apiFetch(`${BASE_RUNS}compare/?${qs.toString()}`, { token });
}
