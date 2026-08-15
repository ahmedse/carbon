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
 * @param {object} params - { status?, limit? }
 * @returns {Promise<Array>} List of conversation summaries
 */
export function listConversations(token, { status, limit } = {}) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (limit) params.append('limit', String(limit));
  const qs = params.toString();
  return apiFetch(`${BASE}conversations/${qs ? `?${qs}` : ''}`, { token });
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
 * Send a message in a conversation and get AI response.
 * @param {string} token - JWT access token
 * @param {string} conversationId - UUID
 * @param {string} content - User message text
 * @returns {Promise<object>} Updated conversation + new messages
 */
export function sendMessage(token, conversationId, content) {
  return apiFetch(`${BASE}conversations/${conversationId}/messages/`, {
    token,
    method: 'POST',
    body: { content },
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
 * @param {object} handlers - { onChunk(delta), onDone(conversation), onError(message) }
 */
export async function sendMessageStream(token, conversationId, content, { onChunk, onDone, onError }) {
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
  const path = `${BASE}conversations/${conversationId}/messages/stream/`.replace(/^\/+/, '');
  const url = `${base}/${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({ content }),
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
    } else if (frame.type === 'done') {
      onDone?.(frame.conversation);
    } else if (frame.type === 'error') {
      onError?.(frame.error || 'Stream failed');
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
