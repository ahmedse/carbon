// src/api/aiWorkspace.js
// API layer for AI Workspace — conversation CRUD + messaging.
// All calls go through Carbon backend → AI Heart → AI provider. Never direct.
import { apiFetch, refreshAccessToken } from './api';
import { API_BASE_URL } from '../config';
import { isJwtExpired } from '../jwt';

const BASE = 'ai/workspace/';

/**
 * Create a new AI conversation.
 * @param {string} token - JWT access token
 * @param {object} params - { conversation_type, title?, app_identifier?, task_payload?, workspace_context? }
 * @returns {Promise<object>} Serialized AIConversation
 */
export function createConversation(token, { conversation_type, title, app_identifier, task_payload, workspace_context }) {
  const body = { conversation_type };
  if (title) body.title = title;
  if (app_identifier) body.app_identifier = app_identifier;
  if (task_payload) body.task_payload = task_payload;
  if (workspace_context) body.workspace_context = workspace_context;
  return apiFetch(`${BASE}conversations/`, { token, method: 'POST', body });
}

/**
 * List conversations for the current user.
 * @param {string} token - JWT access token
 * @param {object} params - { status?, limit?, q?, is_archived?, is_pinned?, conversation_type? }
 * @returns {Promise<Array>} List of conversation summaries
 */
export function listConversations(
  token,
  { status, limit, q, is_archived, is_pinned, conversation_type } = {},
) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (limit) params.append('limit', String(limit));
  if (q) params.append('q', q);
  if (is_archived !== undefined) params.append('is_archived', String(is_archived));
  if (is_pinned !== undefined) params.append('is_pinned', String(is_pinned));
  if (conversation_type) params.append('conversation_type', conversation_type);
  const qs = params.toString();
  return apiFetch(`${BASE}conversations/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Find the most recent open (non-archived) conversation of a given type,
 * optionally scoped to an app. Returns null when none exists. Used to resume
 * an existing thread instead of always creating a new one.
 * @param {string} token - JWT access token
 * @param {object} params - { conversation_type, app_identifier? }
 * @returns {Promise<object|null>}
 */
export async function findOpenConversation(
  token,
  { conversation_type, app_identifier } = {},
) {
  const list = await listConversations(token, { conversation_type, limit: 200 });
  const matches = (list || []).filter((c) => {
    if (!c || c.is_archived) return false;
    if (app_identifier != null && c.app_identifier !== app_identifier) return false;
    return true;
  });
  matches.sort((a, b) => {
    const ta = a.updated_at || a.last_message_at || a.created_at || '';
    const tb = b.updated_at || b.last_message_at || b.created_at || '';
    return String(tb).localeCompare(String(ta));
  });
  return matches[0] || null;
}

/**
 * Get a single conversation with all its messages.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @returns {Promise<object>} Full conversation with messages array
 */
export function getConversation(token, conversationId) {
  return apiFetch(`${BASE}conversations/${conversationId}/`, { token });
}

/**
 * Partially update a conversation (title/is_pinned/is_archived/visibility).
 * @param {string} token - JWT access token
 * @param {string} id - UUID
 * @param {object} fields - { title?, is_pinned?, is_archived?, visibility? }
 * @returns {Promise<object>} Serialized AIConversation
 */
export function updateConversation(token, id, fields = {}) {
  return apiFetch(`${BASE}conversations/${id}/`, {
    token,
    method: 'PATCH',
    body: fields,
  });
}

/**
 * Hard-delete a conversation (owner-only).
 * @param {string} token - JWT access token
 * @param {string} id - UUID
 * @returns {Promise<object>} { deleted: id }
 */
export function deleteConversation(token, id) {
  return apiFetch(`${BASE}conversations/${id}/`, { token, method: 'DELETE' });
}

/**
 * List a conversation's messages with cursor pagination.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {object} params - { limit?, before?, after? }
 * @returns {Promise<object>} { messages: Array, has_more: boolean }
 */
export function listMessages(token, conversationId, { limit, before, after } = {}) {
  const params = new URLSearchParams();
  if (limit) params.append('limit', String(limit));
  if (before) params.append('before', before);
  if (after) params.append('after', after);
  const qs = params.toString();
  return apiFetch(
    `${BASE}conversations/${conversationId}/messages/${qs ? `?${qs}` : ''}`,
    { token },
  );
}

/**
 * Request cancellation of a running generation (idempotent).
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @returns {Promise<object>} Serialized AIConversation
 */
export function stopGeneration(token, conversationId) {
  return apiFetch(`${BASE}conversations/${conversationId}/stop/`, {
    token,
    method: 'POST',
  });
}

/**
 * Regenerate an assistant reply (non-streaming).
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} messageId - UUID of the assistant message
 * @returns {Promise<object>} Serialized AIConversation
 */
export function regenerateMessage(token, conversationId, messageId) {
  return apiFetch(
    `${BASE}conversations/${conversationId}/messages/${messageId}/regenerate/`,
    { token, method: 'POST' },
  );
}

/**
 * Edit a user message's content and flag regeneration (REST parity with 19-A).
 * The streaming UI uses `retryMessageStream` with `content` instead, so the new
 * reply is streamed; this PATCH remains the non-streaming REST surface.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} messageId - UUID of the user message
 * @param {string} content - new message text
 * @returns {Promise<object>} Serialized AIConversation
 */
export function editMessage(token, conversationId, messageId, content) {
  return apiFetch(
    `${BASE}conversations/${conversationId}/messages/${messageId}/`,
    { token, method: 'PATCH', body: { content, regenerate: true } },
  );
}

/**
 * Soft-delete a message. Deleting a user turn also soft-deletes its descendant
 * replies (thread-cut); deleting an assistant reply deletes just that reply.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} messageId - UUID
 * @returns {Promise<object>} { deleted: messageId } or serialized AIConversation
 */
export function deleteMessage(token, conversationId, messageId) {
  return apiFetch(
    `${BASE}conversations/${conversationId}/messages/${messageId}/`,
    { token, method: 'DELETE' },
  );
}

/**
 * Export a conversation as JSON or Markdown.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} format - 'json' | 'markdown'
 * @returns {Promise<object>} Export payload
 */
export function exportConversation(token, conversationId, format = 'json') {
  // `fmt` (not `format`): DRF reserves `format` for URL_FORMAT_OVERRIDE.
  return apiFetch(
    `${BASE}conversations/${conversationId}/export/?fmt=${encodeURIComponent(format)}`,
    { token },
  );
}

/**
 * Generate (or refresh) a conversation's rolling summary.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {boolean} force - force refresh
 * @returns {Promise<object>} Serialized AIConversation
 */
export function summarizeConversation(token, conversationId, force = false) {
  return apiFetch(`${BASE}conversations/${conversationId}/summary/`, {
    token,
    method: 'POST',
    body: { force },
  });
}

/**
 * Confirm a staged tool execution (e.g. a proposed create_dq_rule) so it
 * actually runs as the current user. The response carries the created
 * entity + a navigate action the UI can follow.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} executionId - staged ToolExecution id
 * @returns {Promise<object>} { status, rule_id?, rule_name?, action? }
 */
export function confirmToolExecution(token, conversationId, executionId) {
  return apiFetch(
    `${BASE}conversations/${conversationId}/tool-executions/confirm/`,
    { token, method: 'POST', body: { execution_id: executionId } },
  );
}

/**
 * Decline a staged tool execution — nothing is written.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} executionId - staged ToolExecution id
 * @returns {Promise<object>} { status: 'declined' }
 */
export function declineToolExecution(token, conversationId, executionId) {
  return apiFetch(
    `${BASE}conversations/${conversationId}/tool-executions/decline/`,
    { token, method: 'POST', body: { execution_id: executionId } },
  );
}

/**
 * List the selectable chat models for the model picker.
 * @param {string} token - JWT access token
 * @returns {Promise<object>} { models: [{ id, label, description, input_cost_per_1m, output_cost_per_1m, is_default }] }
 */
export function listModels(token) {
  return apiFetch(`${BASE}models/`, { token });
}

/**
 * Send a message in a conversation and get AI response.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} content - User message text
 * @param {string} [model] - Optional model override id
 * @returns {Promise<object>} Updated conversation + new messages
 */
export function sendMessage(token, conversationId, content, model) {
  const body = { content };
  if (model) body.model = model;
  return apiFetch(`${BASE}conversations/${conversationId}/messages/`, {
    token,
    method: 'POST',
    body,
  });
}

/**
 * Stream a chat message over SSE (POST .../messages/stream/) and deliver
 * frames through callbacks. Uses fetch + ReadableStream (NOT EventSource,
 * which cannot send a POST body or an Authorization header).
 *
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} content - user message text
 * @param {object} handlers - { onChunk(delta), onProgress(stage, message), onDone(conversation), onStopped(conversation), onError(message, errorKind), workspaceContext, model }
 */
/**
 * Shared SSE POST: authenticate, POST JSON, then parse `data:` frames into
 * callbacks. Used by both normal sends and retry/regenerate so they share one
 * streaming path.
 *
 * @param {string} token - JWT access token
 * @param {string} path - API path relative to API_BASE_URL (no leading slash)
 * @param {object} body - JSON body
 * @param {object} handlers - { onChunk, onProgress, onDone, onStopped, onError }
 */
async function streamJsonPost(token, path, body, { onChunk, onProgress, onDone, onStopped, onError }) {
  // Replicate apiFetch's auth: supplied token (or stored access token),
  // refreshing it first if expired.
  let accessToken = token || localStorage.getItem('access');
  if (accessToken && isJwtExpired(accessToken)) {
    try {
      accessToken = await refreshAccessToken();
    } catch {
      onError?.('Session expired');
      return;
    }
  }

  const base = API_BASE_URL.replace(/\/+$/, '');
  const url = `${base}/${path.replace(/^\/+/, '')}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
  } catch (err) {
    onError?.(err?.message || 'Network error');
    return;
  }

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const text = await response.text();
      if (text) {
        try {
          const parsed = JSON.parse(text);
          message = parsed?.error || parsed?.detail || parsed?.message || message;
        } catch {
          message = text;
        }
      }
    } catch {
      // ignore — fall back to status-based message
    }
    onError?.(message);
    return;
  }

  if (!response.body) {
    onError?.('Streaming is not supported by this browser');
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const processFrame = (raw) => {
    const line = raw.trim();
    if (!line.startsWith('data:')) return;
    const payload = line.slice(5).trim();
    if (!payload) return;
    let frame;
    try {
      frame = JSON.parse(payload);
    } catch {
      return;
    }
    if (frame.type === 'chunk') {
      onChunk?.(frame.content ?? '');
    } else if (frame.type === 'progress') {
      onProgress?.(frame.stage, frame.message);
    } else if (frame.type === 'done') {
      onDone?.(frame.conversation);
    } else if (frame.type === 'stopped') {
      onStopped?.(frame.conversation);
    } else if (frame.type === 'error') {
      onError?.(frame.error || 'Stream failed', frame.error_kind);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        processFrame(raw);
      }
    }
    buffer += decoder.decode().replace(/\r\n/g, '\n');
    if (buffer.trim()) processFrame(buffer);
  } catch (err) {
    onError?.(err?.message || 'Stream interrupted');
  }
}

export async function sendMessageStream(
  token,
  conversationId,
  content,
  { onChunk, onProgress, onDone, onStopped, onError, workspaceContext, model },
) {
  const path = `${BASE}conversations/${conversationId}/messages/stream/`;
  const body = { content };
  if (workspaceContext) body.workspace_context = workspaceContext;
  if (model) body.model = model;
  await streamJsonPost(token, path, body, { onChunk, onProgress, onDone, onStopped, onError });
}

/**
 * Retry/regenerate the assistant reply for a user turn over SSE (Phase 19-B).
 * Mirrors sendMessageStream; when `content` is supplied, the backend updates
 * the user message text before re-running the pipeline (edit + regenerate).
 *
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} userMessageId - UUID of the USER message whose reply to regenerate
 * @param {object} handlers - { onChunk, onProgress, onDone, onStopped, onError, content, model }
 */
export async function retryMessageStream(
  token,
  conversationId,
  userMessageId,
  { onChunk, onProgress, onDone, onStopped, onError, content, model },
) {
  const path = `${BASE}conversations/${conversationId}/messages/${userMessageId}/retry/`;
  const body = {};
  if (content) body.content = content;
  if (model) body.model = model;
  await streamJsonPost(token, path, body, { onChunk, onProgress, onDone, onStopped, onError });
}

/**
 * Persist user feedback (accept/reject/correct) on an assistant message.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} messageId - UUID of the assistant message
 * @param {string} outcome - 'accepted' | 'rejected' | 'corrected' | 'ignored'
 * @param {string} correctionText - required-in-spirit when outcome === 'corrected'
 * @returns {Promise<object>} Serialized message including outcome + correction_text
 */
export function recordFeedback(token, conversationId, messageId, outcome, correctionText = '') {
  return apiFetch(
    `${BASE}conversations/${conversationId}/messages/${messageId}/feedback/`,
    { token, method: 'POST', body: { outcome, correction_text: correctionText } },
  );
}

/**
 * Accept a DQ suggestion from within AI Workspace.
 * @param {string} token - JWT access token
 * @param {number|string} suggestionId
 */
export function acceptSuggestion(token, suggestionId) {
  return apiFetch(`dq/suggestions/${suggestionId}/accept/`, {
    token,
    method: 'POST',
  });
}

/**
 * Reject a DQ suggestion from within AI Workspace.
 * @param {string} token - JWT access token
 * @param {number|string} suggestionId
 * @param {string} reason
 */
export function rejectSuggestion(token, suggestionId, reason) {
  const body = reason ? { reason } : {};
  return apiFetch(`dq/suggestions/${suggestionId}/reject/`, {
    token,
    method: 'POST',
    body,
  });
}

// ── Artifacts ─────────────────────────────────────────────────────────

export function listArtifacts(token, { conversation_id, artifact_type, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (conversation_id) params.append('conversation_id', conversation_id);
  if (artifact_type) params.append('artifact_type', artifact_type);
  if (limit) params.append('limit', String(limit));
  const qs = params.toString();
  return apiFetch(`${BASE}artifacts/${qs ? `?${qs}` : ''}`, { token });
}

export function createArtifact(token, { conversation_id, message_id, title, artifact_type, content_json }) {
  return apiFetch(`${BASE}artifacts/`, {
    token,
    method: 'POST',
    body: { conversation_id, message_id, title, artifact_type, content_json },
  });
}

export function deleteArtifact(token, artifactId) {
  return apiFetch(`${BASE}artifacts/${artifactId}/`, { token, method: 'DELETE' });
}

// ── Phase 5 — proactive suggestions + resume catch-up ────────────────────

/**
 * Get proactive suggestions (KgProactiveInsight) for a conversation.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {number} limit - 1–50 (default 10)
 * @returns {Promise<object>} { suggestions: Array }
 */
export function getSuggestions(token, conversationId, limit = 10) {
  const params = new URLSearchParams();
  if (limit != null) params.append('limit', String(limit));
  const qs = params.toString();
  return apiFetch(
    `${BASE}conversations/${conversationId}/suggestions/${qs ? `?${qs}` : ''}`,
    { token },
  );
}

/**
 * Mark a conversation as viewed and fetch a resume catch-up when stale (>24h).
 * Idempotency lives server-side (bumps last_viewed_at) — call once per open.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @returns {Promise<object>} { conversation, catch_up|null }
 */
export function resumeConversation(token, conversationId) {
  return apiFetch(`${BASE}conversations/${conversationId}/resume/`, {
    token,
    method: 'POST',
  });
}

/**
 * Accept a proactive suggestion (KgProactiveInsight) in a conversation.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} suggestionId - suggestion id
 * @returns {Promise<object>} Acknowledged suggestion
 */
export function acceptProactiveSuggestion(token, conversationId, suggestionId) {
  return apiFetch(
    `${BASE}conversations/${conversationId}/suggestions/${suggestionId}/accept/`,
    { token, method: 'POST' },
  );
}

/**
 * Dismiss a proactive suggestion (KgProactiveInsight) in a conversation.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} suggestionId - suggestion id
 * @param {string} reason - optional dismiss reason
 * @returns {Promise<object>} Dismissed suggestion
 */
export function dismissProactiveSuggestion(token, conversationId, suggestionId, reason) {
  const body = reason ? { reason } : {};
  return apiFetch(
    `${BASE}conversations/${conversationId}/suggestions/${suggestionId}/dismiss/`,
    { token, method: 'POST', body },
  );
}

/**
 * List pending proactive suggestions across all conversations (for the badge).
 * @param {string} token - JWT access token
 * @param {number} limit - 1–50 (default 50)
 * @returns {Promise<object>} { suggestions: Array }
 */
export function listWorkspaceSuggestions(token, limit = 50) {
  const params = new URLSearchParams();
  params.append('limit', String(limit));
  return apiFetch(`${BASE}conversations/suggestions/?${params.toString()}`, { token });
}
