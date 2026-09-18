// src/pages/admin/ai/pulseFormat.js
// Pure formatters for the Pulse read-only console. Kept dependency-free so
// they are unit-testable without pulling in MUI DataGrid / auth / API deps.

// AppScopeMixin columns — collapsed into a single compact "scope" column.
export const SCOPE_FIELDS = ['app_identifier', 'org_unit_id', 'host_user_id', 'visibility'];

/**
 * Curated primary columns per PulseDataPanel dataKey (thin-grid deepen).
 * Fields absent on a row render as "—"; unknown keys fall back to dynamic.
 */
export const COLUMN_PRESETS = Object.freeze({
  tools: ['name', 'tool_name', 'status', 'run_id', 'plan_id', 'created_at', 'error'],
  monitoring: ['kind', 'title', 'status', 'summary', 'created_at'],
  feedback: ['signal_type', 'rating', 'status', 'run_id', 'created_at'],
  learning: ['status', 'run_id', 'plan_id', 'name', 'created_at'],
  logs: ['model', 'status', 'run_id', 'conversation_id', 'total_tokens', 'created_at'],
});

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

/** Distinct `_type` values present in a result set (for filter chips). */
export function listRowTypes(rows) {
  if (!Array.isArray(rows) || !rows.length) return [];
  const types = new Set();
  rows.forEach((row) => {
    if (row?._type) types.add(String(row._type));
  });
  return [...types].sort();
}

/**
 * Build Evidence Explorer deep-link when a row carries a reconstructable id.
 * Prefers run_id / plan_id, then conversation_id.
 */
export function buildEvidenceHref(row) {
  if (!row || typeof row !== 'object') return null;
  const runId = row.run_id || row.plan_id || row.request_id;
  const conversationId = row.conversation_id;
  if (runId) {
    return `/admin/ai/evidence?tab=explorer&run_id=${encodeURIComponent(String(runId))}`;
  }
  if (conversationId) {
    return `/admin/ai/evidence?tab=explorer&conversation_id=${encodeURIComponent(String(conversationId))}`;
  }
  return null;
}

/**
 * Ordered field names for the grid: preset fields that appear in any row,
 * then remaining non-scope keys (capped) so we never invent columns.
 */
export function resolveColumnFields(dataKey, rows, { maxExtra = 4 } = {}) {
  const preset = COLUMN_PRESETS[dataKey] || [];
  const present = new Set();
  (rows || []).forEach((row) => {
    Object.keys(row || {}).forEach((key) => {
      if (key !== '_type' && !SCOPE_FIELDS.includes(key)) present.add(key);
    });
  });
  const preferred = preset.filter((key) => present.has(key));
  const extras = [...present]
    .filter((key) => !preferred.includes(key))
    .sort()
    .slice(0, preferred.length ? maxExtra : 12);
  return preferred.length ? [...preferred, ...extras] : extras;
}
