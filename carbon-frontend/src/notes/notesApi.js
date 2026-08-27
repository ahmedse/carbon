// src/notes/notesApi.js
// Thin API wrapper for the centralized Notes / Comments / Reactions layer.
// Reuses the platform's `apiFetch` (JWT refresh, timeout, error normalization).

import { apiFetch } from "../api/api";
import { API_ROUTES } from "../config";

const NOTES = "catalog/notes/";

function notesUrl(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) {
      v.forEach((item) => qs.append(k, item)); // repeated params (e.g. anchor=…)
    } else {
      qs.set(k, v);
    }
  });
  const q = qs.toString();
  return q ? `${NOTES}?${q}` : NOTES;
}

function commentsUrl(noteId, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, v);
  });
  const q = qs.toString();
  return q ? `${NOTES}${noteId}/comments/?${q}` : `${NOTES}${noteId}/comments/`;
}

/** Flatten entity contexts into `anchor=et:ei` pairs (repeated params). */
function anchorParams(contexts) {
  if (!Array.isArray(contexts) || contexts.length === 0) return {};
  return { anchor: contexts.map((c) => `${c.entityType}:${c.entityId}`) };
}

/**
 * List notes — filtered by ANY of the given entity anchors (the drawer context
 * can be multiple entities, e.g. domain app + reporting year), or by a single
 * entity pair for backward compatibility, or unfiltered for the global feed.
 * Paginated (page_size 20).
 */
export function fetchNotes({ contexts, entityType, entityId, page = 1, pageSize = 20 } = {}) {
  return apiFetch(notesUrl({
    ...anchorParams(contexts),
    entity_type: entityType,
    entity_id: entityId,
    page,
    page_size: pageSize,
  }));
}

/**
 * Create a note anchored to one or more entities.
 * The FIRST context becomes the primary anchor (entity_type/entity_id); the
 * rest are stored as extra anchors so the note surfaces in every thread.
 * Visibility is implicit — the server derives it from the author's scope.
 */
export function createNote({ entityType, entityId, contexts, body }) {
  const extras = (Array.isArray(contexts) ? contexts : [])
    .filter((c) => !(c.entityType === entityType && c.entityId === entityId));
  const payload = {
    entity_type: entityType,
    entity_id: entityId,
    body,
    ...(extras.length ? { anchors: extras.map((c) => ({ entity_type: c.entityType, entity_id: c.entityId })) } : {}),
  };
  return apiFetch(NOTES, { method: "POST", body: payload });
}

/** Update a note body. Returns the full note payload. */
export function updateNote(noteId, { body }) {
  return apiFetch(`${NOTES}${noteId}/`, { method: "PATCH", body: { body } });
}

/** Soft-delete a note. */
export function deleteNote(noteId) {
  return apiFetch(`${NOTES}${noteId}/`, { method: "DELETE" });
}

/** Toggle a reaction on a note. Returns { reaction_counts, my_reaction }. */
export function toggleNoteReaction(noteId, reaction) {
  return apiFetch(`${NOTES}${noteId}/reactions/`, {
    method: "POST",
    body: { reaction },
  });
}

/** List comments for a note (chronological, 1-level). Paginated. */
export function fetchComments(noteId, { page = 1, pageSize = 50 } = {}) {
  return apiFetch(commentsUrl(noteId, { page, page_size: pageSize }));
}

/** Add a comment to a note. Returns the full comment payload. */
export function addComment(noteId, body) {
  return apiFetch(commentsUrl(noteId), { method: "POST", body: { body } });
}

/** Update a comment body. */
export function updateComment(noteId, commentId, { body }) {
  return apiFetch(`${commentsUrl(noteId)}${commentId}/`, {
    method: "PATCH",
    body: { body },
  });
}

/** Soft-delete a comment. */
export function deleteComment(noteId, commentId) {
  return apiFetch(`${commentsUrl(noteId)}${commentId}/`, { method: "DELETE" });
}

/** Toggle a reaction on a comment. Returns { reaction_counts, my_reaction }. */
export function toggleCommentReaction(noteId, commentId, reaction) {
  return apiFetch(`${commentsUrl(noteId)}${commentId}/reactions/`, {
    method: "POST",
    body: { reaction },
  });
}

export const NOTES_API = {
  fetchNotes,
  createNote,
  updateNote,
  deleteNote,
  toggleNoteReaction,
  fetchComments,
  addComment,
  updateComment,
  deleteComment,
  toggleCommentReaction,
};

// Keep API_ROUTES referenced for config parity (e.g., future dynamic route use).
export { API_ROUTES };
