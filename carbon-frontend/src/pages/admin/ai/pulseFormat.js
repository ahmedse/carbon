// src/pages/admin/ai/pulseFormat.js
// Pure formatters for the Pulse read-only console. Kept dependency-free so
// they are unit-testable without pulling in MUI DataGrid / auth / API deps.

// AppScopeMixin columns — collapsed into a single compact "scope" column.
export const SCOPE_FIELDS = ['app_identifier', 'org_unit_id', 'host_user_id', 'visibility'];

/** Defensive cell formatting: null/undefined -> '—', nested values -> JSON. */
export function formatCellValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value) || typeof value === 'object') {
    const text = JSON.stringify(value);
    return text.length > 80 ? `${text.slice(0, 80)}…` : text;
  }
  return String(value);
}

/** Compact one-line scope summary for a row (replaces 4 wide columns). */
export function buildScopeLabel(row) {
  const parts = [];
  if (row.app_identifier) parts.push(String(row.app_identifier));
  if (row.org_unit_id != null) parts.push(`org:${row.org_unit_id}`);
  if (row.host_user_id) parts.push(`user:${row.host_user_id}`);
  if (row.visibility) parts.push(String(row.visibility));
  return parts.length ? parts.join(' · ') : '—';
}

/** Human-friendly key list for a row, skipping internal/scope helper columns. */
export function buildDetailFields(row) {
  return Object.entries(row)
    .filter(([key]) => key !== '_type' && !SCOPE_FIELDS.includes(key))
    .map(([key, value]) => ({ key, value: formatCellValue(value) }));
}
