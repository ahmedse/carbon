import { apiFetch } from './api';

export const INSIGHTS_BASE = 'ai/insights/';

/** Fetch a page of proactive AI insights (newest first). */
export function listInsights(token, page = 1) {
  return apiFetch(`${INSIGHTS_BASE}?page=${page}`, { token });
}

/**
 * Update an insight's disposition.
 * @param {string} token
 * @param {string|number} id
 * @param {string} disposition - "read" | "acted_on" | "dismissed"
 * @param {string} reason
 */
export function postDisposition(token, id, disposition, reason) {
  return apiFetch(`${INSIGHTS_BASE}${id}/disposition/`, {
    token,
    method: 'POST',
    body: { disposition, reason },
  });
}
