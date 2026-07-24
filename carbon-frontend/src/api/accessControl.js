// src/api/accessControl.js
// API calls for user role assignments (ScopedRole). Admin-gated on the server.
import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function fetchUsers(token) {
  return unwrap(await apiFetch(API_ROUTES.users, { token }));
}

export async function fetchGroups(token) {
  return unwrap(await apiFetch(API_ROUTES.groups, { token }));
}

export async function fetchScopedRoles(token) {
  return unwrap(await apiFetch(API_ROUTES.scopedRoles, { token }));
}

/** data = { user, group, org_unit, module, is_active } using IDs. */
export function createScopedRole(token, data) {
  return apiFetch(API_ROUTES.scopedRoles, { method: "POST", token, body: data });
}

export function deleteScopedRole(token, id) {
  return apiFetch(`${API_ROUTES.scopedRoles}${id}/`, { method: "DELETE", token });
}

export function updateScopedRole(token, id, data) {
  return apiFetch(`${API_ROUTES.scopedRoles}${id}/`, { method: "PATCH", token, body: data });
}
