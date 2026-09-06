// src/utils/aiProvenance.js
// Shared helpers for rendering the per-turn provenance context snapshot.

const CONTEXT_TIER_LABELS = {
  T2_history: 'History',
  T2b_summary: 'Summary',
  T3_retrieval: 'KG Retrieval',
  T4_memory: 'Memory',
};

// Render the per-turn context snapshot (budget tiers + retrieved KG entities)
// into display lines. ``kg_entities`` is an array of objects, so it must be
// flattened to names rather than rendered as "[object Object] tok".
export function formatContextLines(ctxSnap) {
  if (!ctxSnap || typeof ctxSnap !== 'object') return [];
  const lines = [];

  const tierParts = [];
  for (const [key, label] of Object.entries(CONTEXT_TIER_LABELS)) {
    const tok = ctxSnap[key];
    if (typeof tok === 'number' && tok > 0) {
      tierParts.push(`${label} ${tok} tok`);
    }
  }
  if (tierParts.length) lines.push(`Context: ${tierParts.join(' · ')}`);

  const kg = Array.isArray(ctxSnap.kg_entities) ? ctxSnap.kg_entities : [];
  if (kg.length) {
    const names = kg
      .slice(0, 5)
      .map((e) => e?.name)
      .filter(Boolean);
    if (names.length) lines.push(`Knowledge Graph: ${names.join(', ')}`);
  }

  return lines;
}

// ── PAQ-3A — non-envelope provenance sources ────────────────────────────────
// Normalize the "sources" that ground a data-bearing answer into the same
// { tool, rows_returned, truncated, resolved_at } shape the envelope renderer
// consumes. Reads defensively from metadata_json / the provenance payload / a
// top-level sources field; returns [] when nothing is available (never fabricates).

/** Coerce a single source candidate (object or bare tool-name string). */
export function normalizeProvenanceSource(raw) {
  if (typeof raw === 'string') {
    const tool = raw.trim();
    return tool ? { tool, rows_returned: null, truncated: false, resolved_at: null } : null;
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;

  const tool = String(raw.tool || raw.tool_name || raw.name || '').trim();
  const rowsRaw = raw.rows_returned ?? raw.row_count ?? raw.rows ?? raw.result_rows;

  let rowsReturned = null;
  if (Array.isArray(rowsRaw)) {
    rowsReturned = rowsRaw.length;
  } else if (typeof rowsRaw === 'number' && Number.isFinite(rowsRaw)) {
    rowsReturned = rowsRaw;
  } else if (rowsRaw !== null && rowsRaw !== undefined && rowsRaw !== '') {
    const parsed = Number(rowsRaw);
    rowsReturned = Number.isFinite(parsed) ? parsed : null;
  }

  const truncated = Boolean(raw.truncated);
  const resolvedAt = raw.resolved_at || raw.resolvedAt || raw.resolved_at_iso || null;

  if (!tool && rowsReturned === null && !truncated && !resolvedAt) return null;
  return { tool, rows_returned: rowsReturned, truncated, resolved_at: resolvedAt };
}

/**
 * Collect provenance sources for a non-envelope answer. Sources may arrive as
 * an array on metadata_json / the provenance payload / a top-level field, or
 * as flat fields directly on metadata (row_count, tool, truncated, resolved_at).
 */
export function normalizeProvenanceSources(metadata, provenancePayload, topLevelSources) {
  const out = [];
  const seen = new Set();

  const lists = [
    metadata?.sources,
    provenancePayload?.sources,
    topLevelSources,
  ];

  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    for (const raw of list) {
      const src = normalizeProvenanceSource(raw);
      if (!src) continue;
      const key = `${src.tool}::${src.rows_returned}::${src.truncated}::${src.resolved_at}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(src);
    }
  }

  // Flat single-source fallback: the four facts live directly on metadata.
  if (out.length === 0) {
    const flat = normalizeProvenanceSource(metadata);
    if (flat) out.push(flat);
  }

  return out;
}
