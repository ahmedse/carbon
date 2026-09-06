// src/api/team.js
// API helpers for the Team (manager approvals inbox) app.
// Endpoints: GET correspondence/inbox/, GET correspondence/{id}/, and the
// POST action endpoints approve/reject/send-back. Every call goes through
// apiFetch (JWT refresh + error normalization) — never raw fetch().

import { apiFetch } from './api';

const INBOX_ROOT = 'correspondence/inbox/';
const CORRESPONDENCE_ROOT = 'correspondence/';

/**
 * Actionable items for the current manager (GET correspondence/inbox/).
 * Robust to both a plain JSON array and a paginated { count, results } envelope.
 * Returns { items, count }.
 */
export async function fetchInbox(token) {
  const data = await apiFetch(`${INBOX_ROOT}`, { token });
  if (Array.isArray(data)) return { items: data, count: data.length };
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
