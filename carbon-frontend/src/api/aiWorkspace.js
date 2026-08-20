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
 * List a conversation's named checkpoints, newest first (checkpoint picker).
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @returns {Promise<object>} { checkpoints: [{ id, name, note, snapshot, created_at, updated_at }] }
 */
export function listCheckpoints(token, conversationId) {
  return apiFetch(`${BASE}conversations/${conversationId}/checkpoints/`, {
    token,
  });
}

/**
 * Save a named snapshot of the conversation's working context. Idempotent:
 * re-saving the same ``name`` overwrites that checkpoint.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {object} params - { name, note? }
 * @returns {Promise<object>} Serialized checkpoint
 */
export function checkpointConversation(token, conversationId, { name, note = '' } = {}) {
  return apiFetch(`${BASE}conversations/${conversationId}/checkpoint/`, {
    token,
    method: 'POST',
    body: { name, note },
  });
}

/**
 * Re-seed a conversation's *working* context from a saved checkpoint.
 * The durable message log is NOT overwritten.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} checkpointId - UUID
 * @returns {Promise<object>} Serialized AIConversation
 */
export function restoreConversation(token, conversationId, checkpointId) {
  return apiFetch(`${BASE}conversations/${conversationId}/restore/`, {
    token,
    method: 'POST',
    body: { checkpoint_id: checkpointId },
  });
}

/**
 * Clone the conversation into a NEW conversation seeded from a checkpoint.
 * Returns the new conversation's id — never aliases the source row.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} checkpointId - UUID
 * @returns {Promise<object>} Serialized AIConversation (the fork)
 */
export function forkConversation(token, conversationId, checkpointId) {
  return apiFetch(`${BASE}conversations/${conversationId}/fork/`, {
    token,
    method: 'POST',
    body: { checkpoint_id: checkpointId },
  });
}

/**
 * Reset a conversation's working context (summary + context snapshot). The
 * conversation row, its message log, and learned facts are all kept.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @returns {Promise<object>} Serialized AIConversation
 */
export function clearContext(token, conversationId) {
  return apiFetch(`${BASE}conversations/${conversationId}/clear-context/`, {
    token,
    method: 'POST',
  });
}

/**
 * Confirm a staged tool execution (e.g. a proposed create_dq_rule) so it
 * actually runs as the current user. The response carries the created
 * entity + a navigate action the UI can follow.
 *
 * Pass ``body`` to confirm an EDITED version of the proposal: the backend
 * replaces the staged POST body with it before executing, so "modify then
 * confirm" is one atomic call.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} executionId - staged ToolExecution id
 * @param {object} [body] - optional replacement for the staged host POST body
 * @returns {Promise<object>} { status, rule_id?, rule_name?, action? }
 */
export function confirmToolExecution(token, conversationId, executionId, body) {
  const payload = { execution_id: executionId };
  if (body && typeof body === 'object') payload.body = body;
  return apiFetch(
    `${BASE}conversations/${conversationId}/tool-executions/confirm/`,
    { token, method: 'POST', body: payload },
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
 * Fetch the current user's AI preferences (Phase 22-A).
 * Endpoint lives under /carbon-api/ai/profile/ (not the workspace BASE).
 * @param {string} token - JWT access token
 * @returns {Promise<object>} { default_model_id, resolved_model_id, temperature,
 *   auto_title, memory_enabled, usage_alert_threshold }
 */
export function getProfile(token) {
  return apiFetch('ai/profile/', { token });
}

/**
 * Update the current user's AI preferences (Phase 22-A).
 * `default_model_id` accepts a catalog slug, or null/'' to clear the override.
 * @param {string} token - JWT access token
 * @param {object} [fields] - { default_model_id?, temperature?, auto_title?,
 *   memory_enabled?, usage_alert_threshold? }
 * @returns {Promise<object>} Updated profile
 */
export function patchProfile(token, fields = {}) {
  const body = { ...fields };
  // '' from a cleared Select means "no override" — normalize to null so the
  // backend clears the FK instead of trying to resolve an empty slug.
  if (body.default_model_id === '') body.default_model_id = null;
  return apiFetch('ai/profile/', { token, method: 'PATCH', body });
}

/**
 * Usage & cost summary for the current project over a period.
 * Endpoint lives under /carbon-api/ai/usage/ (not the workspace BASE).
 * @param {string} token - JWT access token
 * @param {object} [opts]
 * @param {string} [opts.period='30d'] - 7d | 30d | 90d | <n>w | plain days
 * @returns {Promise<object>} { period_days, total_tokens, prompt_tokens,
 *   completion_tokens, total_cost, total_generations, by_tier, by_model, quota }
 */
export function getUsageSummary(token, { period = '30d' } = {}) {
  return apiFetch(`ai/usage/summary/?period=${encodeURIComponent(period)}`, { token });
}

/**
 * Per-conversation usage for the current project over a period.
 * @param {string} token - JWT access token
 * @param {object} [opts]
 * @param {string} [opts.period='30d'] - 7d | 30d | 90d | <n>w | plain days
 * @returns {Promise<object>} { period_days, conversations: [{ conversation_id,
 *   title, total_tokens, total_cost, generation_count, message_count }] }
 */
export function getUsageByConversation(token, { period = '30d' } = {}) {
  return apiFetch(`ai/usage/by-conversation/?period=${encodeURIComponent(period)}`, { token });
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
 * @param {object} handlers - { onChunk, onProgress, onDone, onStopped, onError, onFrame }
 *   ``onFrame`` receives every parsed SSE frame object before the typed
 *   callbacks dispatch — the escape hatch used by the clustered action-run
 *   stream (turn-* / tool-* frames) without forking this reader.
 */
async function streamJsonPost(token, path, body, { onChunk, onProgress, onDone, onStopped, onError, onFrame }) {
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
    onFrame?.(frame);
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
 * Stream a user-initiated agent/tool action run (Sprint W2-A frontend of W1-A).
 * Reuses the shared streamJsonPost auth + SSE reader — the clustered
 * ``turn_*`` / ``tool_*`` frames are dispatched via ``onFrame``; ``done``,
 * ``stopped`` and ``error`` flow through the existing typed callbacks.
 *
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {object} spec - { action_type: 'tool'|'agent', tool?, agent?, args?, verbosity? }
 *   ``tool`` is required for action_type='tool', ``agent`` for 'agent'.
 *   ``verbosity`` ∈ 'concise'|'full' (default 'concise').
 * @param {object} handlers - { onTurnStart, onToolStart, onToolArg, onToolResult,
 *   onToolEnd, onTurnEnd, onDone, onStopped, onError }
 *   Frame shapes (design §2.5, W1-A):
 *     turn_start  { turn_id, label, verbosity }
 *     tool_start  { turn_id, step_id, tool, category }   category ∈ agent|mcp|tool
 *     tool_arg    { step_id, args }                       full verbosity only
 *     tool_result { step_id, result }                     full verbosity only (redacted)
 *     tool_end    { step_id, status, execution_id? }      completed|failed|stopped|needs_confirmation
 *     turn_end    { turn_id, status, summary }            completed|failed|stopped
 */
export async function runActionStream(
  token,
  conversationId,
  { action_type, tool, agent, args, verbosity },
  { onTurnStart, onToolStart, onToolArg, onToolResult, onToolEnd, onTurnEnd, onDone, onStopped, onError },
) {
  const path = `${BASE}conversations/${conversationId}/actions/stream/`;
  const body = { action_type, args: args || {} };
  if (tool) body.tool = tool;
  if (agent) body.agent = agent;
  if (verbosity) body.verbosity = verbosity;

  await streamJsonPost(token, path, body, {
    onFrame: (frame) => {
      switch (frame.type) {
        case 'turn_start': onTurnStart?.(frame); break;
        case 'tool_start': onToolStart?.(frame); break;
        case 'tool_arg': onToolArg?.(frame); break;
        case 'tool_result': onToolResult?.(frame); break;
        case 'tool_end': onToolEnd?.(frame); break;
        case 'turn_end': onTurnEnd?.(frame); break;
        default: break; // done / stopped / error handled by streamJsonPost
      }
    },
    onDone,
    onStopped,
    onError,
  });
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

// ── Phase 23-A — Memory & learnt facts ──────────────────────────────────
// Endpoints live under /carbon-api/ai/memory/ (NOT the workspace BASE).

/**
 * List durable learnt facts (long-term memory) — newest first.
 * @param {string} token - JWT access token
 * @param {object} [opts] - { category?, limit? (cap 500) }
 * @returns {Promise<object>} { count, results: [{ id, category, content,
 *   confidence, provenance: { source, created_at, last_used }, use_count,
 *   visibility, valid_from, valid_to }] }
 */
export function listFacts(token, { category, limit } = {}) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (limit) params.append('limit', String(limit));
  const qs = params.toString();
  return apiFetch(`ai/memory/facts/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * List episodic memory rows (events/milestones from past work) — newest first.
 * @param {string} token - JWT access token
 * @param {object} [opts] - { event_type?, limit? (cap 500) }
 * @returns {Promise<object>} { count, results: [{ id, event_type, summary,
 *   details, caused_by_episode_id, relevance_score, occurred_at, learned_at,
 *   visibility }] }
 */
export function listEpisodes(token, { event_type, limit } = {}) {
  const params = new URLSearchParams();
  if (event_type) params.append('event_type', event_type);
  if (limit) params.append('limit', String(limit));
  const qs = params.toString();
  return apiFetch(`ai/memory/episodes/${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Relationship summary — what the assistant remembers about this user,
 * computed per request (never persisted server-side).
 * @param {string} token - JWT access token
 * @returns {Promise<object>} { memory_enabled, memory: { fact_count,
 *   episode_count, top_categories: [{ category, count }], avg_confidence,
 *   total_uses }, usage: {...}, profile: {...}, computed_at }
 */
export function getRelationship(token) {
  return apiFetch('ai/memory/relationship/', { token });
}

/**
 * Forget a learnt fact (owner-only). Hard delete + cascade to derived facts;
 * the backend audits every forget. Resolves on 204.
 * @param {string} token - JWT access token
 * @param {string} id - fact id (UUID)
 * @returns {Promise<void>}
 */
export function forgetFact(token, id) {
  return apiFetch(`ai/memory/facts/${encodeURIComponent(id)}/`, {
    token,
    method: 'DELETE',
  });
}

// ── Sprint 23 W3-A — Agentic task orchestration (plans) ─────────────────
// Endpoints live under /carbon-api/ai/plans/ — reviewable plan lifecycle:
// create (planning only) → approve → SSE streamed run → per-step consent
// (confirm/decline) → durable audit ledger.

const PLANS_BASE = 'ai/plans/';

/**
 * Create a reviewable plan from a brief. Planning only — NOTHING executes
 * until the plan is approved and run (RULE_21: review before mutation).
 * @param {string} token - JWT access token
 * @param {object} params - { brief, conversation_id? }
 * @returns {Promise<object>} Plan payload (status 'pending_approval')
 */
export function createPlan(token, { brief, conversation_id = '' }) {
  return apiFetch(PLANS_BASE, {
    token,
    method: 'POST',
    body: { brief, conversation_id },
  });
}

/**
 * Fetch a plan + its steps (owner-scoped).
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Plan payload
 */
export function getPlan(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/`, { token });
}

/**
 * List the requesting user's plans, newest first.
 * @param {string} token - JWT access token
 * @param {object} [opts] - { limit? (default 50) }
 * @returns {Promise<object>} { plans: Array, count }
 */
export function listPlans(token, { limit } = {}) {
  const params = new URLSearchParams();
  if (limit) params.append('limit', String(limit));
  const qs = params.toString();
  return apiFetch(`${PLANS_BASE}${qs ? `?${qs}` : ''}`, { token });
}

/**
 * Approve a pending plan for execution (plan-level consent gate, RULE_21).
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Plan payload (status 'approved')
 */
export function approvePlan(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/approve/`, { token, method: 'POST' });
}

/**
 * Decline a pending plan — nothing is executed.
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Plan payload (status 'cancelled')
 */
export function declinePlan(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/decline/`, { token, method: 'POST' });
}

/**
 * Stream a plan run over SSE (POST .../plans/{id}/run/). Reuses the shared
 * streamJsonPost auth + SSE reader; plan frames are dispatched through
 * ``onFrame`` (plan_start / step_start / step_confirm / step_result /
 * step_end), and the terminal ``done`` / ``error`` frames flow through the
 * typed callbacks (done carries the whole frame — the plan stream has no
 * ``conversation`` key like the chat stream).
 *
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @param {object} handlers - { onFrame(frame), onDone(frame), onError(message) }
 *   Frame shapes (W3-A backend):
 *     plan_start  { plan_id, status, plan: { brief, pattern, source, steps } }
 *     step_start  { plan_id, step_id, intent }
 *     step_confirm{ plan_id, step_id, intent, message }   consent gate
 *     step_result { plan_id, step_id, intent, status, verdict, draft_text,
 *                   tool_output, error }
 *     step_end    { plan_id, step_id, status }
 *     done        { plan_id, status: completed|paused|stopped|failed,
 *                   final_response }
 *     error       { error }
 */
export async function runPlanStream(token, planId, { onFrame, onDone, onError }) {
  const path = `${PLANS_BASE}${planId}/run/`;

  await streamJsonPost(token, path, {}, {
    onFrame: (frame) => {
      onFrame?.(frame);
      if (frame.type === 'done') onDone?.(frame);
    },
    onError: (message) => onError?.(message),
  });
}

/**
 * Confirm a paused consent step — executes the staged mutation as the user.
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @param {number} stepId - step_index
 * @returns {Promise<object>} { status: 'confirmed', plan_id, step_id }
 */
export function confirmPlanStep(token, planId, stepId) {
  return apiFetch(`${PLANS_BASE}${planId}/steps/confirm/`, {
    token,
    method: 'POST',
    body: { step_id: stepId },
  });
}

/**
 * Decline a paused consent step — the staged mutation is discarded.
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @param {number} stepId - step_index
 * @returns {Promise<object>} { status: 'declined', plan_id, step_id }
 */
export function declinePlanStep(token, planId, stepId) {
  return apiFetch(`${PLANS_BASE}${planId}/steps/decline/`, {
    token,
    method: 'POST',
    body: { step_id: stepId },
  });
}

/**
 * Request cancellation of a plan run (idempotent).
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Plan payload (status 'cancelled')
 */
export function stopPlan(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/stop/`, { token, method: 'POST' });
}

/**
 * Audit ledger for a plan: steps, confirmations, replans, latency, tokens,
 * provenance, actor.
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Ledger payload
 */
export function getPlanLedger(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/ledger/`, { token });
}

// ── W3-C — plan controls (edit / pause / resume / fork) ──────────────────
// Editing never auto-approves (RULE_21): the response carries a step diff
// ({added, removed, changed}) + replan_gate; the Workspace shows the diff
// review gate before the revised plan is re-approved.

/**
 * Edit a plan's brief (replan). Returns the plan + `diff` + `replan_gate`.
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @param {object} params - { brief?, step_deltas? }
 * @returns {Promise<object>} Plan payload with { diff, replan_gate }
 */
export function editPlan(token, planId, { brief, step_deltas } = {}) {
  const body = {};
  if (brief !== undefined) body.brief = brief;
  if (step_deltas !== undefined) body.step_deltas = step_deltas;
  return apiFetch(`${PLANS_BASE}${planId}/`, { token, method: 'PATCH', body });
}

/**
 * Edit a single plan step (title/instructions/depends_on) — same diff-review
 * rule as editPlan.
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @param {number} stepId - step_index
 * @param {object} params - { title?, instructions?, depends_on? }
 * @returns {Promise<object>} Plan payload with { diff, replan_gate }
 */
export function editPlanStep(token, planId, stepId, { title, instructions, depends_on } = {}) {
  const body = {};
  if (title !== undefined) body.title = title;
  if (instructions !== undefined) body.instructions = instructions;
  if (depends_on !== undefined) body.depends_on = depends_on;
  return apiFetch(`${PLANS_BASE}${planId}/steps/${stepId}/`, { token, method: 'PATCH', body });
}

/**
 * Pause a running plan (ledger-level; consent steps untouched).
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Plan payload (status 'paused')
 */
export function pausePlan(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/pause/`, { token, method: 'POST' });
}

/**
 * Fork a plan into a NEW reviewable copy (pending_approval).
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @returns {Promise<object>} Forked plan payload
 */
export function forkPlan(token, planId) {
  return apiFetch(`${PLANS_BASE}${planId}/fork/`, { token, method: 'POST' });
}

/**
 * Resume a paused/approved plan over SSE (POST .../plans/{id}/resume/).
 * Same frame protocol as runPlanStream (step_start / step_confirm /
 * step_result / step_end / done / error).
 * @param {string} token - JWT access token
 * @param {string} planId - UUID
 * @param {object} handlers - { onFrame(frame), onDone(frame), onError(message) }
 */
export async function resumePlanStream(token, planId, { onFrame, onDone, onError }) {
  const path = `${PLANS_BASE}${planId}/resume/`;
  await streamJsonPost(token, path, {}, {
    onFrame: (frame) => {
      onFrame?.(frame);
      if (frame.type === 'done') onDone?.(frame);
    },
    onError: (message) => onError?.(message),
  });
}
