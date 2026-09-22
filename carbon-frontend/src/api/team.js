// src/api/team.js
// API helpers for the Team (manager approvals inbox) app.
// Endpoints: GET correspondence/inbox/, GET correspondence/{id}/, and the
// POST action endpoints. Every call goes through apiFetch — never raw fetch().

import { apiFetch } from './api';

const INBOX_ROOT = 'correspondence/inbox/';
const CORRESPONDENCE_ROOT = 'correspondence/';

/**
 * Actionable items for the current manager (GET correspondence/inbox/).
 * Robust to both a plain JSON array and a paginated { count, results } envelope.
 * Returns { items, count, routing_orphans }.
 */
export async function fetchInbox(token) {
  const data = await apiFetch(`${INBOX_ROOT}`, { token });
  if (Array.isArray(data)) {
    return { items: data, count: data.length, routing_orphans: 0 };
  }
  return {
    items: Array.isArray(data?.results) ? data.results : [],
    count: data?.count ?? 0,
    routing_orphans: Number(data?.routing_orphans) || 0,
  };
}

/**
 * Decisions by the current user — any type / any outcome (GET correspondence/history/).
 * Returns { items, count }.
 */
export async function fetchHistory(token) {
  const data = await apiFetch(`${CORRESPONDENCE_ROOT}history/`, { token });
  if (Array.isArray(data)) {
    return { items: data, count: data.length };
  }
  return {
    items: Array.isArray(data?.results) ? data.results : [],
    count: data?.count ?? 0,
  };
}

/** Single correspondence record incl. events + approver chain (GET correspondence/{id}/). */
export function fetchCorrespondenceDetail(token, id) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/`, { token });
}

/** POST correspondence/{id}/approve/ — comment OPTIONAL. */
export function approveCorrespondence(token, id, { comment } = {}) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/approve/`, {
    method: 'POST',
    body: { comment: comment || '' },
    token,
  });
}

/** POST correspondence/{id}/acknowledge/ — comment OPTIONAL (memo/circular intents). */
export function acknowledgeCorrespondence(token, id, { comment } = {}) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/acknowledge/`, {
    method: 'POST',
    body: { comment: comment || '' },
    token,
  });
}

/** POST correspondence/{id}/review/ — comment OPTIONAL. */
export function reviewCorrespondence(token, id, { comment } = {}) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/review/`, {
    method: 'POST',
    body: { comment: comment || '' },
    token,
  });
}

/** POST correspondence/{id}/reject/ — comment REQUIRED. */
export function rejectCorrespondence(token, id, { comment } = {}) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/reject/`, {
    method: 'POST',
    body: { comment },
    token,
  });
}

/** POST correspondence/{id}/send-back/ — comment REQUIRED. */
export function sendBackCorrespondence(token, id, { comment } = {}) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/send-back/`, {
    method: 'POST',
    body: { comment },
    token,
  });
}

/**
 * Direct reports for the current manager (Team Directory).
 * GET people/me/direct-reports/
 */
export function fetchDirectReports(token) {
  return apiFetch('people/me/direct-reports/', { token });
}

/**
 * Leave overlapping a calendar month for direct reports (Who's Out).
 * GET people/me/team-leave/?year=&month=
 * Returns { year, month, items }.
 */
export function fetchTeamLeave(token, { year, month } = {}) {
  const params = new URLSearchParams();
  if (year != null) params.set('year', String(year));
  if (month != null) params.set('month', String(month));
  const qs = params.toString();
  return apiFetch(`people/me/team-leave/${qs ? `?${qs}` : ''}`, { token });
}
