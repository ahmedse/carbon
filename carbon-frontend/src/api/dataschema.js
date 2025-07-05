// src/api/dataschema.js

import { apiFetch } from "./api";
import { API_ROUTES } from "../config";

// Tables
export function fetchDataSchemaTables(token, project_id, module_id) {
  // project_id is required, module_id is optional
  return apiFetch(API_ROUTES.tables, { token, project_id, module_id });
}
export function createDataSchemaTable(token, data, project_id, module_id) {
  // Send both project_id and module_id
  return apiFetch(API_ROUTES.tables, { method: "POST", token, body: data, project_id, module_id });
}
export function updateDataSchemaTable(token, id, data, project_id, module_id) {
  return apiFetch(`${API_ROUTES.tables}${id}/`, { method: "PUT", token, body: data, project_id, module_id });
}
export function deleteDataSchemaTable(token, id, project_id, module_id) {
  return apiFetch(`${API_ROUTES.tables}${id}/`, { method: "DELETE", token, project_id, module_id });
}

// Fields
export function fetchDataSchemaFields(token, table_id, project_id, module_id) {
  return apiFetch(`${API_ROUTES.tables}${table_id}/fields/`, { token, project_id, module_id });
}
export function createDataSchemaField(token, data, project_id, module_id) {
  return apiFetch(API_ROUTES.fields, { method: "POST", token, body: data, project_id, module_id });
}
export function updateDataSchemaField(token, id, data, project_id, module_id) {
  return apiFetch(`${API_ROUTES.fields}${id}/`, { method: "PUT", token, body: data, project_id, module_id });
}
export function deleteDataSchemaField(token, id, project_id, module_id) {
  return apiFetch(`${API_ROUTES.fields}${id}/`, { method: "DELETE", token, project_id, module_id });
}

// Batch reorder
export function updateDataSchemaFieldOrder(token, tableId, fields, project_id, module_id) {
  return apiFetch(`${API_ROUTES.fields}reorder/`, {
    method: "POST",
    token,
    body: {
      data_table: tableId,
      fields: fields.map(f => ({ id: f.id, order: f.order })),
    },
    project_id,
    module_id,
  });
}

// Fetch rows for a table, with optional filters
export function fetchDataRows(token, tableId, filters = {}, project_id, module_id) {
  const params = new URLSearchParams();
  params.set("data_table", tableId);

  if (filters._search) params.set("search", filters._search);

  Object.entries(filters).forEach(([key, value]) => {
    if (key !== "_search" && value != null && value !== "") {
      params.set(`field__${key}`, value);
    }
  });

  const endpoint = `${API_ROUTES.rows}?${params.toString()}`;
  return apiFetch(endpoint, { token, project_id, module_id })
    .then(data => (Array.isArray(data) ? data : []));
}

// Create new row
export function createDataRow(token, values, tableId, project_id, module_id) {
  return apiFetch(API_ROUTES.rows, {
    method: "POST",
    token,
    project_id,
    module_id,
    body: { data_table: tableId, values }
  });
}

// Edit row (use PATCH for partial update)
export function updateDataRow(token, rowId, values, project_id, module_id, usePatch = false) {
  return apiFetch(`${API_ROUTES.rows}${rowId}/`, {
    method: usePatch ? "PATCH" : "PUT",
    token,
    project_id,
    module_id,
    body: values
  });
}

// Delete row(s)
export function deleteDataRow(token, rowId, project_id, module_id) {
  return apiFetch(`${API_ROUTES.rows}${rowId}/`, {
    method: "DELETE",
    token,
    project_id,
    module_id
  });
}

// Bulk delete: call deleteDataRow for each selected row
export function bulkDeleteDataRows(token, rowIds, project_id, module_id) {
  return Promise.all(rowIds.map(id => deleteDataRow(token, id, project_id, module_id)));
}

// Download CSV (client-side)
export function exportRowsToCsv(rows, fields, filename = "export.csv") {
  const csvRows = [];
  csvRows.push(fields.map(f => `"${f.label.replace(/"/g, '""')}"`).join(","));
  for (const row of rows) {
    csvRows.push(fields.map(f => {
      let val = row.values?.[f.name] ?? "";
      if (Array.isArray(val)) val = val.join("; ");
      if (typeof val === "object" && val !== null) val = JSON.stringify(val);
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(","));
  }
  const csvContent = csvRows.join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Robust file upload
export async function uploadRowFile(token, rowId, field, file, project_id, module_id) {
  const formData = new FormData();
  formData.append("field", field);
  formData.append("file", file);

  const params = [];
  if (project_id) params.push(`project_id=${encodeURIComponent(project_id)}`);
  if (module_id) params.push(`module_id=${encodeURIComponent(module_id)}`);
  const url = `${API_ROUTES.rows}${rowId}/upload/${params.length ? "?" + params.join("&") : ""}`;

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!resp.ok) {
    const errorText = await resp.text();
    throw new Error(`File upload failed (${resp.status}): ${errorText}`);
  }

  return await resp.json();
}