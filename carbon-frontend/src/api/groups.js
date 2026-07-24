// src/api/groups.js
// API calls for role groups and group detail data.
import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function fetchGroups(token) {
  return unwrap(await apiFetch(API_ROUTES.groups, { token }));
}

export async function fetchGroupDetail(token, groupId) {
  return apiFetch(`${API_ROUTES.groups}${groupId}/`, { token });
}

export async function fetchGroupMembers(token, groupId) {
  return unwrap(await apiFetch(`${API_ROUTES.groups}${groupId}/members/`, { token }));
}

export async function fetchGroupScopedAssignments(token, groupId) {
  return unwrap(await apiFetch(`${API_ROUTES.groups}${groupId}/scoped_assignments/`, { token }));
}

export async function createGroup(token, data) {
  return apiFetch(API_ROUTES.groups, { method: "POST", token, body: data });
}

export async function updateGroup(token, groupId, data) {
  return apiFetch(`${API_ROUTES.groups}${groupId}/`, { method: "PATCH", token, body: data });
}

export async function deleteGroup(token, groupId) {
  return apiFetch(`${API_ROUTES.groups}${groupId}/`, { method: "DELETE", token });
}
