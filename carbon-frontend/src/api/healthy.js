// src/api/healthy.js
// API helpers for the Healthy Foods Factory app (backend/healthy/*).
// All endpoints live under /carbon-api/healthy/ (see backend/healthy/urls.py).
// Every call goes through apiFetch (JWT refresh + error normalization) — never raw fetch().

import { apiFetch } from './api';

const ROOT = 'healthy/';

/** List ERP snapshots. */
export function fetchHealthySnapshots(token) {
  return apiFetch(`${ROOT}snapshots/`, { token });
}

/** Trigger a new ERP snapshot / pipeline run (healthy:manage). */
export function triggerHealthySnapshot(data, token) {
  return apiFetch(`${ROOT}snapshots/`, { method: 'POST', body: data, token });
}

/** List loadout sheets, optionally filtered by `week`. */
export function fetchLoadoutSheets({ week } = {}, token) {
  const query = week ? `?week=${encodeURIComponent(week)}` : '';
  return apiFetch(`${ROOT}loadout/${query}`, { token });
}

/** Full loadout for a single week (all reps). */
export function fetchLoadoutWeek(week, token) {
  return apiFetch(`${ROOT}loadout/${encodeURIComponent(week)}/`, { token });
}

/** Single rep's loadout sheet for a week. */
export function fetchLoadoutRep(week, rep, token) {
  return apiFetch(`${ROOT}loadout/${encodeURIComponent(week)}/${encodeURIComponent(rep)}/`, { token });
}

/** Submit actual loadout outcomes for a rep/week (healthy:manage). */
export function submitLoadoutActuals(week, rep, actuals, token) {
  return apiFetch(`${ROOT}loadout/${encodeURIComponent(week)}/${encodeURIComponent(rep)}/actuals/`, {
    method: 'POST',
    body: actuals,
    token,
  });
}

/** List rep health cards, optionally filtered by `week`. */
export function fetchRepHealth({ week } = {}, token) {
  const query = week ? `?week=${encodeURIComponent(week)}` : '';
  return apiFetch(`${ROOT}rep-health/${query}`, { token });
}

/** Single rep health card for a week. */
export function fetchRepHealthDetail(week, rep, token) {
  return apiFetch(`${ROOT}rep-health/${encodeURIComponent(week)}/${encodeURIComponent(rep)}/`, { token });
}

/** Aggregated dashboard KPIs across all pipelines. */
export function fetchHealthySummary(token) {
  return apiFetch(`${ROOT}dashboards/summary/`, { token });
}

/** AR collections priority queue. */
export function fetchARQueue(token) {
  return apiFetch(`${ROOT}dashboards/ar-queue/`, { token });
}

/** Dead-stock / slow-mover alert table. */
export function fetchSlowMovers(token) {
  return apiFetch(`${ROOT}dashboards/slow-movers/`, { token });
}
