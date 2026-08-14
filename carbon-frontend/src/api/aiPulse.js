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
