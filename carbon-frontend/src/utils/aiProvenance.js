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
