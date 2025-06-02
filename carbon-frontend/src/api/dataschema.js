// src/api/dataschema.js

import { apiFetch } from "./api";

// Tables
export function fetchDataSchemaTables(token, context_id, module_id) {
  const query = module_id ? `?module_id=${encodeURIComponent(module_id)}` : "";
  return apiFetch(`/api/dataschema/tables/${query}`, { token, context_id });
}
export function createDataSchemaTable(token, data, context_id) {
  return apiFetch(`/api/dataschema/tables/`, { method: "POST", token, body: data, context_id });
}
export function updateDataSchemaTable(token, id, data, context_id) {
  return apiFetch(`/api/dataschema/tables/${id}/`, { method: "PUT", token, body: data, context_id });
}
export function deleteDataSchemaTable(token, id, context_id) {
  return apiFetch(`/api/dataschema/tables/${id}/`, { method: "DELETE", token, context_id });
}

// Fields
export function fetchDataSchemaFields(token, table_id, context_id) {
  return apiFetch(`/api/dataschema/tables/${table_id}/fields/`, { token, context_id });
}
export function createDataSchemaField(token, data, context_id) {
  return apiFetch(`/api/dataschema/fields/`, { method: "POST", token, body: data, context_id });
}
export function updateDataSchemaField(token, id, data, context_id) {
  return apiFetch(`/api/dataschema/fields/${id}/`, { method: "PUT", token, body: data, context_id });
}
export function deleteDataSchemaField(token, id, context_id) {
  return apiFetch(`/api/dataschema/fields/${id}/`, { method: "DELETE", token, context_id });
}

// Batch reorder, now unified with apiFetch
export function updateDataSchemaFieldOrder(token, tableId, fields, context_id) {
  return apiFetch(`/api/dataschema/fields/reorder/`, {
    method: "POST",
    token,
    body: {
      data_table: tableId,
      fields: fields.map(f => ({ id: f.id, order: f.order })),
    },
    context_id,
  });
}