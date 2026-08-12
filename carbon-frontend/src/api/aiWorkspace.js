// src/api/aiWorkspace.js
// API layer for AI Workspace — conversation CRUD + messaging.
// All calls go through Carbon backend → AI Heart → AI provider. Never direct.
import { apiFetch } from './api';

const BASE = 'ai/workspace/';

/**
 * Create a new AI conversation.
 * @param {string} token - JWT access token
 * @param {object} params - { conversation_type, title?, app_identifier?, task_payload? }
 * @returns {Promise<object>} Serialized AIConversation
 */
export function createConversation(token, { conversation_type, title, app_identifier, task_payload }) {
  const body = { conversation_type };
  if (title) body.title = title;
  if (app_identifier) body.app_identifier = app_identifier;
  if (task_payload) body.task_payload = task_payload;
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
