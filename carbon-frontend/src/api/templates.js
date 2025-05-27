// File: src/api/templates.js

import { apiFetch } from "./api";
const BASE = "/api/datacollection/templates/";

// Helper to build query string
function buildQuery(params) {
  const esc = encodeURIComponent;
  return (
    Object.keys(params)
      .map((k) => esc(k) + "=" + esc(params[k]))
      .join("&")
  );
}

export async function fetchTemplates(token, context_id, params = {}) {
  const query = buildQuery({ context_id, ...params });
  return apiFetch(`${BASE}?${query}`, { token });
}

export async function createTemplate(token, context_id, data) {
  return apiFetch(BASE, { method: "POST", token, body: { ...data, context_id } });
}

export async function updateTemplate(token, id, context_id, data) {
  return apiFetch(`${BASE}${id}/`, { method: "PUT", token, body: { ...data, context_id } });
}

export async function deleteTemplate(token, id, context_id) {
  return apiFetch(`${BASE}${id}/?context_id=${encodeURIComponent(context_id)}`, { method: "DELETE", token });
}

export async function fetchTemplateUsage(token, id, context_id) {
  return apiFetch(`${BASE}${id}/usage/?context_id=${encodeURIComponent(context_id)}`, { token });
}