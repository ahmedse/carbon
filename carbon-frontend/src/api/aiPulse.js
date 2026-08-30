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
