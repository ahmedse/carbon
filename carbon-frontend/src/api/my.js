// src/api/my.js
// API helpers for the My (employee self-service) app.
// Endpoints: GET people/me/, GET people/me/leave-balance/, GET correspondence/inbox/.
// Every call goes through apiFetch (JWT refresh + error normalization) — never raw fetch().

import { apiFetch } from './api';

const PROFILE_ROOT = 'people/me/';
const INBOX_ROOT = 'correspondence/inbox/';
const CORRESPONDENCE_ROOT = 'correspondence/';

/** Current employee identity (GET people/me/). */
export function fetchMyProfile(token) {
  return apiFetch(`${PROFILE_ROOT}`, { token });
}

/** Current employee leave balance (GET people/me/leave-balance/). */
export function fetchLeaveBalance(token) {
  return apiFetch(`${PROFILE_ROOT}leave-balance/`, { token });
}

/**
 * Current employee committed payslips (GET people/me/payslips/).
 * Returns an array of payslip-line objects, or `[]` when none exist.
 */
export function fetchMyPayslips(token) {
  return apiFetch(`${PROFILE_ROOT}payslips/`, { token });
}

/**
 * Normalize GET people/me/loan/ payloads (plain array or paginated envelope).
 * Exported for unit tests / list helpers (NSR-3B).
 */
export function normalizeMyLoans(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

/**
 * Current employee loans (GET people/me/loan/).
 * Returns an array of loan objects (id, loan_type, principal, status, …).
 */
export async function fetchMyLoans(token) {
  const data = await apiFetch(`${PROFILE_ROOT}loan/`, { token });
  return normalizeMyLoans(data);
}

/**
 * Count of inbox items requiring action (GET correspondence/inbox/).
 * Robust to both a plain JSON array and a paginated { count, ... } envelope.
 */
export async function fetchInboxCount(token) {
  const data = await apiFetch(`${INBOX_ROOT}`, { token });
  return Array.isArray(data) ? data.length : (data?.count ?? 0);
}

/** Current employee leave request history (GET people/me/leave/). Returns an array. */
export function fetchMyLeave(token) {
  return apiFetch(`${PROFILE_ROOT}leave/`, { token });
}

/**
 * Submit a leave request (POST people/me/leave/).
 * On success returns the Correspondence detail object (NOT a leave record).
 * On error, apiFetch propagates an Error carrying `.status` (number) and
 * `.data` (the raw response body, e.g. `{ detail, remaining }` for a 400).
 */
export function submitLeaveRequest(token, payload) {
  return apiFetch(`${PROFILE_ROOT}leave/`, { method: 'POST', body: payload, token });
}

/**
 * Current user's own correspondence (GET correspondence/), self-scoped.
 * Optional filters: { status, corrType } — both omitted when falsy.
 * Returns { items, count }, normalized from a paginated { count, results }
 * envelope OR a plain JSON array.
 */
export async function fetchMyCorrespondence(token, { status, corrType } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (corrType) params.set('corr_type', corrType);
  const qs = params.toString();
  const endpoint = qs ? `${CORRESPONDENCE_ROOT}?${qs}` : CORRESPONDENCE_ROOT;
  const data = await apiFetch(endpoint, { token });
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

/** Requester cancels a non-terminal request (POST correspondence/{id}/cancel/). */
export function cancelCorrespondence(token, id) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/cancel/`, { method: 'POST', token });
}

/**
 * Requester edits payload while sent_back (POST correspondence/{id}/edit/).
 * Body: { payload, title? }. Status stays sent_back.
 */
export function editCorrespondence(token, id, { payload, title } = {}) {
  const body = { payload };
  if (title != null) body.title = title;
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/edit/`, {
    method: 'POST',
    body,
    token,
  });
}

/** Requester resubmits a sent-back request (POST correspondence/{id}/resubmit/). */
export function resubmitCorrespondence(token, id) {
  return apiFetch(`${CORRESPONDENCE_ROOT}${id}/resubmit/`, { method: 'POST', token });
}

/**
 * Submit a loan request (POST people/me/loan/).
 * On success returns the Correspondence detail object (NOT a loan record).
 * On error, apiFetch propagates an Error carrying `.status` and `.data`.
 */
export function submitLoanRequest(token, payload) {
  return apiFetch(`${PROFILE_ROOT}loan/`, { method: 'POST', body: payload, token });
}

/**
 * Current employee attendance permissions (GET people/me/attendance-permissions/).
 * Returns an array (or empty).
 */
export function fetchMyAttendancePermissions(token) {
  return apiFetch(`${PROFILE_ROOT}attendance-permissions/`, { token });
}

/**
 * Submit a short-hours attendance permission (POST people/me/attendance-permissions/).
 * On success returns the Correspondence detail object.
 */
export function submitAttendancePermission(token, payload) {
  return apiFetch(`${PROFILE_ROOT}attendance-permissions/`, {
    method: 'POST',
    body: payload,
    token,
  });
}

/**
 * Submit a profile-change request (POST people/me/profile-change/).
 * Payload: { changes: { <field>: { from?, to } } }.
 */
export function submitProfileChange(token, payload) {
  return apiFetch(`${PROFILE_ROOT}profile-change/`, { method: 'POST', body: payload, token });
}

/**
 * Submit a generic payload-only correspondence (POST correspondence/).
 * Payload: { corr_type, title, payload, org_unit? } for internal_memo,
 * circular and decision types.
 */
export function submitGenericCorrespondence(token, payload) {
  return apiFetch(`${CORRESPONDENCE_ROOT}`, { method: 'POST', body: payload, token });
}
