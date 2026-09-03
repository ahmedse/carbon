// src/api/aiPulse.js
// API layer for the Pulse admin read-only panels (inventory, data, archetypes).
// All calls go through the shared apiFetch helper (RULE_10) — never raw fetch.
import { apiFetch } from './api';

const BASE = 'ai/pulse/';

/**
 * List the 13 Pulse console panels with model-backed row counts.
 * @param {string} token - JWT access token
 * @returns {Promise<{panels: Array<{key, label, count, models}>}>}
 */
export function getPulseInventory(token) {
  return apiFetch(`${BASE}inventory/`, { token });
}

/**
 * Fetch merged, redacted rows for one panel.
 * @param {string} token - JWT access token
 * @param {string} key - panel key (e.g. "knowledge", "logs")
 * @returns {Promise<{key, label, count, models, results}>}
 */
export function getPulseData(token, key) {
  return apiFetch(`${BASE}data/${encodeURIComponent(key)}/`, { token });
}

/**
 * List the vendored engine archetype bundles (filesystem read-only).
 * @param {string} token - JWT access token
 * @returns {Promise<{bundles: Array<{name, kind}>}>}
 */
export function getPulseArchetypes(token) {
  return apiFetch(`${BASE}archetypes/`, { token });
}

/**
 * Fetch the daily output-quality trend + drift flags (read-only).
 * @param {string} token - JWT access token
 * @returns {Promise<{current: {avg, count}, by_day: Array<{date, avg, count}>,
 *                    by_signal: Array<{signal, avg, count}>, drift: Array<{date, delta, avg}>}>}
 */
export function getQualityTrend(token) {
  return apiFetch(`${BASE}quality-trend/`, { token });
}

/**
 * Fetch LLM usage aggregates (budget, spend, tokens, per-model, 7-day).
 * @param {string} token - JWT access token
 * @returns {Promise<{budget_usd, spent_today_usd, tokens_today, calls_today,
 *                    tokens_total, calls_total, cost_total, remaining_usd,
 *                    budget_exceeded, by_model, by_day}>}
 */
export function getUsage(token) {
  return apiFetch(`${BASE}usage/`, { token });
}

/**
 * Fetch the effective engine config + capability inventory (redacted).
 * @param {string} token - JWT access token
 * @returns {Promise<{llm, limits, cache, rate_limit, routing, mcp_servers,
 *                    tools_catalog, agents}>}
 */
export function getSettings(token) {
  return apiFetch(`${BASE}settings/`, { token });
}

/**
 * Fetch the normalized knowledge-graph (nodes + edges + stats) for the
 * force-directed "Knowledge Graph" panel.
 * @param {string} token - JWT access token
 * @returns {Promise<{nodes: Array, edges: Array, stats: {node_count,
 *                    edge_count, truncated, node_types, relationship_counts}}>}
 */
export function getPulseGraph(token) {
  return apiFetch(`${BASE}graph/`, { token });
}

/**
 * Fetch the learning-flywheel status (durable backend, pending/processed
 * judged messages, outcome breakdown, recent long-term-memory facts, and the
 * feedback-record ledger).
 * @param {string} token - JWT access token
 * @returns {Promise<{backend, durable, pending, processed, by_outcome,
 *                    facts: {counts, recent},
 *                    feedback_records: {count, recent}}>}
 */
export function getLearningStatus(token) {
  return apiFetch(`${BASE}learning-status/`, { token });
}

/**
 * Trigger an on-demand learning sweep and return the refreshed status.
 * @param {string} token - JWT access token
 * @returns {Promise<{sweep: {processed, accepted, rejected, corrected, errors},
 *                    status: object}>}
 */
export function runLearningSweep(token) {
  return apiFetch(`${BASE}learning-status/run/`, { method: 'POST', token });
}

/**
 * List manifests for all registered domain apps.
 * @param {string} token - JWT access token
 * @returns {Promise<{apps: Array, count: number}>}
 */
export function listDomainManifests(token) {
  return apiFetch(`${BASE}apps/`, { token });
}

/**
 * List skill lifecycle records (drafted → promoted → reused progression).
 * Read-only, admin-only (ai:view_console), CBAC-scoped. Returns a top-level
 * array (not a {results} envelope).
 * @param {string} token - JWT access token
 * @returns {Promise<Array<{name, kind, status, usage_count, success_rate,
 *                    avg_latency_ms, last_executed_at, promoted_at}>>}
 */
export function getPulseSkills(token) {
  return apiFetch(`${BASE}skills/`, { token });
}

const BASE2 = 'ai/audit/';

/**
 * Fetch the read-only AI audit trail with optional filters + pagination.
 * @param {string} token - JWT access token
 * @param {object} [params] - filter/pagination params
 * @param {string} [params.action] - action type filter (e.g. "ai.tool_call")
 * @param {string} [params.actor] - actor id filter
 * @param {string} [params.start] - ISO start date/datetime
 * @param {string} [params.end] - ISO end date/datetime
 * @param {number} [params.page] - 1-based page number
 * @param {number} [params.pageSize] - rows per page (cap 200)
 * @returns {Promise<{count: number, page: number, page_size: number,
 *                    results: Array<{id, timestamp, actor, action, target, detail}>}>}
 */
export function getAuditTrail(token, { action, actor, start, end, page, pageSize } = {}) {
  const params = new URLSearchParams();
  if (action) params.set('action', action);
  if (actor) params.set('actor', actor);
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  if (page) params.set('page', String(page));
  if (pageSize) params.set('page_size', String(pageSize));

  const qs = params.toString();
  return apiFetch(qs ? `${BASE2}?${qs}` : BASE2, { token });
}

const BASE3 = 'ai/watches/';

/**
 * List anomaly watches (DRF-paginated, default page_size 20, max 100).
 * @param {string} token - JWT access token
 * @param {object} [params]
 * @param {number} [params.page] - 1-based page number
 * @param {number} [params.pageSize] - rows per page
 * @returns {Promise<{count: number, next: string|null, previous: string|null,
 *                    results: Array<{id, name, kpi_expression, condition,
 *                    threshold, comparison_window_days, enabled, last_fired_at,
 *                    fire_count, recipients, instance_id}>}>}
 */
export function listWatches(token, { page, pageSize } = {}) {
  const params = new URLSearchParams();
  if (page) params.set('page', String(page));
  if (pageSize) params.set('page_size', String(pageSize));
  const qs = params.toString();
  return apiFetch(qs ? `${BASE3}?${qs}` : BASE3, { token });
}

/**
 * Create an anomaly watch. Requires ai:manage_console on the server.
 * @param {string} token - JWT access token
 * @param {object} payload - {name, kpi_expression, condition, threshold,
 *                           comparison_window_days, recipients, enabled}
 * @returns {Promise<object>} the created watch row
 */
export function createWatch(token, payload) {
  return apiFetch(BASE3, { method: 'POST', token, body: payload });
}

/**
 * Update an anomaly watch. Requires ai:manage_console (or owner) on the server.
 * @param {string} token - JWT access token
 * @param {number|string} id - watch id
 * @param {object} payload - partial watch fields
 * @returns {Promise<object>} the updated watch row
 */
export function updateWatch(token, id, payload) {
  return apiFetch(`${BASE3}${id}/`, { method: 'PATCH', token, body: payload });
}

/**
 * Delete an anomaly watch. Requires ai:manage_console (or owner) on the server.
 * @param {string} token - JWT access token
 * @param {number|string} id - watch id
 * @returns {Promise<void>} resolves on 204
 */
export function deleteWatch(token, id) {
  return apiFetch(`${BASE3}${id}/`, { method: 'DELETE', token });
}
