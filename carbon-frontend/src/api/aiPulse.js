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
