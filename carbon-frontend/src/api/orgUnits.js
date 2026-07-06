// src/api/orgUnits.js
// API calls for OrgUnit management (MDM). Admin-gated on the server.
import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

/** List all org units. Returns an array (unwraps DRF pagination if present). */
export async function fetchOrgUnits(token) {
  const data = await apiFetch(API_ROUTES.orgUnits, { token });
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

/** Create an org unit. `data` = { name, org_type, parent, code, description }. */
export function createOrgUnit(token, data) {
  return apiFetch(API_ROUTES.orgUnits, { method: "POST", token, body: data });
}

/** Update an org unit (partial). */
export function updateOrgUnit(token, id, data) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { method: "PATCH", token, body: data });
}

/** Delete an org unit. */
export function deleteOrgUnit(token, id) {
  return apiFetch(`${API_ROUTES.orgUnits}${id}/`, { method: "DELETE", token });
}
