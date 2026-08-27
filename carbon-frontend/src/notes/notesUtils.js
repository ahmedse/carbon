// src/notes/notesUtils.js
// Small pure helpers for the Notes drawer: time formatting, reaction merging,
// avatar initials, stable note keys.

/** Format a note/comment timestamp for display. */
export function formatNoteTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const now = Date.now();
  const diffMs = now - date.getTime();

  // Relative for < 24h, absolute afterwards.
  const oneMin = 60_000;
  const oneHour = 3_600_000;
  const oneDay = 86_400_000;
  if (diffMs >= 0 && diffMs < oneMin) return "just now";
  if (diffMs >= 0 && diffMs < oneHour) return `${Math.floor(diffMs / oneMin)}m ago`;
  if (diffMs >= 0 && diffMs < oneDay) return `${Math.floor(diffMs / oneHour)}h ago`;

  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** ISO timestamp for title/tooltip (full precision). */
export function formatNoteTimeIso(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString();
}

/** Initials for the avatar, from an author payload ({ full_name?, username? }). */
export function authorInitials(author) {
  if (!author) return "?";
  const name = author.full_name || author.username || "";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Display name for the author line. */
export function authorDisplayName(author) {
  if (!author) return "Unknown";
  return author.full_name || author.username || "Unknown";
}

/** Reaction choices — order + i18n keys (must match backend choices). */
export const REACTION_CHOICES = [
  { value: "like", icon: "👍", labelKey: "notes:reactions.like" },
  { value: "question", icon: "❓", labelKey: "notes:reactions.question" },
  { value: "star", icon: "⭐", labelKey: "notes:reactions.star" },
];

/** Empty reaction counts map (matches backend response shape). */
export const EMPTY_REACTION_COUNTS = { like: 0, question: 0, star: 0 };

/**
 * Merge a reaction toggle response into existing counts.
 * `toggleResult` = { reaction_counts, my_reaction }.
 * Returns a new counts object (immutable).
 */
export function mergeReactionCounts(current, toggleResult) {
  const base = current || { ...EMPTY_REACTION_COUNTS };
  if (!toggleResult || !toggleResult.reaction_counts) return base;
  return { ...base, ...toggleResult.reaction_counts };
}

/** Stable cache key for an entity context. */
export function entityKey(entityType, entityId) {
  if (!entityType || entityId === undefined || entityId === null) return "global";
  return `${entityType}:${entityId}`;
}

/**
 * Build the query key used by the notes list cache.
 * Accepts a single context (backward compat) or an array of contexts —
 * multiple anchors share one merged feed, keyed by sorted anchor pairs.
 */
export function notesListKey(contexts) {
  const list = Array.isArray(contexts) ? contexts : [contexts];
  const anchors = list
    .filter((c) => c && c.entityType && c.entityId !== undefined && c.entityId !== null)
    .map((c) => entityKey(c.entityType, c.entityId))
    .sort();
  return anchors.length ? anchors.join("|") : "global";
}
