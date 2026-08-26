// src/api/profiling.js
// DQ profile + scorecard + freshness API wrappers (EPH-3A / EPH-3B).
// All endpoints are RELATIVE — apiFetch handles JWT refresh + base URL.
// Do NOT prepend any base URL here.

import { apiFetch } from './api';

/**
 * Fetch the latest table profile and its per-field profiles.
 * GET dq/tables/{tableId}/profile/
 * 404 with body { detail: 'No profile yet for this table.' } = "no profile yet".
 */
export function getTableProfile(tableId, token) {
  return apiFetch(`dq/tables/${tableId}/profile/`, { token });
}

/**
 * Trigger an (async, but inline when Celery is absent) re-profile.
 * POST dq/tables/{tableId}/profile/run/ → 202 { task_id, job_id, status, table_id }.
 * Admin-only (backend requires dq:manage_rules).
 */
export function runTableProfile(tableId, token) {
  return apiFetch(`dq/tables/${tableId}/profile/run/`, { method: 'POST', token });
}

/**
 * Fetch the quality scorecard for a table.
 * GET dq/tables/{tableId}/scorecard/
 * All scores (quality_score + dimensions[].score) are 0..1 floats.
 */
export function getTableScorecard(tableId, token) {
  return apiFetch(`dq/tables/${tableId}/scorecard/`, { token });
}

/**
 * Fetch the freshness policy + last-data-updated timestamp for a table.
 * GET catalog/tables/{tableId}/freshness/
 * 404 when no FreshnessPolicy exists (callers should handle gracefully).
 */
export function getTableFreshness(tableId, token) {
  return apiFetch(`catalog/tables/${tableId}/freshness/`, { token });
}

/**
 * Create/update the freshness policy for a table.
 * POST catalog/tables/{tableId}/freshness/ with { max_age_hours, alert_level, enabled }.
 * Read-only chip in this phase — exposed for completeness.
 */
export function saveFreshnessPolicy(tableId, payload, token) {
  return apiFetch(`catalog/tables/${tableId}/freshness/`, {
    method: 'POST',
    token,
    body: payload,
  });
}
