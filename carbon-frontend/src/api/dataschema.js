// File: src/api/dataschema.js

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

// Fetch rows for a table, with optional filters
export function fetchDataRows(token, tableId, filters = {}, context_id) {
  const params = { data_table: tableId, ...filters };
  const esc = encodeURIComponent;
  const query = Object.keys(params)
    .filter(k => params[k] !== undefined && params[k] !== null && params[k] !== "")
    .map(k => esc(k) + "=" + esc(params[k]))
    .join("&");
  return apiFetch(`/api/dataschema/rows/?${query}`, { token, context_id });
}

// Create new row
export function createDataRow(token, values, tableId, context_id) {
  return apiFetch(`/api/dataschema/rows/`, {
    method: "POST",
    token,
    context_id,
    body: { data_table: tableId, values }
  });
}

// Edit row (use PATCH for partial update)
export function updateDataRow(token, rowId, values, context_id, usePatch = false) {
  return apiFetch(`/api/dataschema/rows/${rowId}/`, {
    method: usePatch ? "PATCH" : "PUT",
    token,
    context_id,
    body: values
  });
}

// Delete row(s)
export function deleteDataRow(token, rowId, context_id) {
  return apiFetch(`/api/dataschema/rows/${rowId}/`, {
    method: "DELETE",
    token,
    context_id
  });
}

// Bulk delete: call deleteDataRow for each selected row
export function bulkDeleteDataRows(token, rowIds, context_id) {
  return Promise.all(rowIds.map(id => deleteDataRow(token, id, context_id)));
}

// Download CSV (client-side)
export function exportRowsToCsv(rows, fields, filename = "export.csv") {
  const csvRows = [];
  // Header
  csvRows.push(fields.map(f => `"${f.label.replace(/"/g, '""')}"`).join(","));
  // Body
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

export async function uploadRowFile(token, rowId, fieldName, file, context_id) {
  if (!rowId) throw new Error("Row must be created before uploading a file.");
  const url = `/api/dataschema/rows/${rowId}/upload/` + (context_id ? `?context_id=${encodeURIComponent(context_id)}` : "");
  const formData = new FormData();
  formData.append("field", fieldName);
  formData.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      // Do NOT set Content-Type to multipart/form-data; browser will set it
    },
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "File upload failed");
  }
  return await res.json(); // { url: ... }
}