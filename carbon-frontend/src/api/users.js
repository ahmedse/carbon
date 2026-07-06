// src/api/users.js
// API calls for user account management. Admin-gated on the server.
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

/** data = { username, email, password, is_active } */
export function createUser(token, data) {
  return apiFetch(API_ROUTES.users, { method: "POST", token, body: data });
}

/** data = partial, e.g. { email } or { is_active } or { password } */
export function updateUser(token, id, data) {
  return apiFetch(`${API_ROUTES.users}${id}/`, { method: "PATCH", token, body: data });
}

export function deleteUser(token, id) {
  return apiFetch(`${API_ROUTES.users}${id}/`, { method: "DELETE", token });
}
