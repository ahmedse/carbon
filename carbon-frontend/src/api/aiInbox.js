// src/api/aiInbox.js
// Human Task Inbox API wrappers (P3-09). Thin read/write + SSE wrappers over
// the /carbon-api/ai/inbox/ endpoints — all through apiFetch / apiFetchStream
// (RULE_10, JWT auto-refresh). Consumed ONLY by pages/admin/ai/**.
//
// Approve/Decline are POST actions; the *per-task* required_authority is
// enforced server-side (fail-closed) — a 403 surfaces as {detail: '…'}.
import { apiFetch, apiFetchStream } from './api';

const BASE_INBOX = 'ai/inbox/';
const BASE_TASKS = `${BASE_INBOX}tasks/`;

/**
 * List inbox tasks, optionally filtered by status (default: all).
 * @param {string} token
 * @param {{status?: string}} [opts]
 * @returns {Promise<Array>}
 */
export function listInbox(token, { status } = {}) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiFetch(`${BASE_TASKS}${qs}`, { token });
}

/**
 * One inbox task (full dimensions).
 * @param {string} token
 * @param {string} id
 * @returns {Promise<object>}
 */
export function getInboxItem(token, id) {
  return apiFetch(`${BASE_TASKS}${encodeURIComponent(id)}/`, { token });
}

/**
 * Approve a task — mints an ApprovalGrant server-side.
 * @param {string} token
 * @param {string} id
 * @returns {Promise<object>} updated task
 */
export function approveTask(token, id) {
  return apiFetch(`${BASE_TASKS}${encodeURIComponent(id)}/approve/`, {
    token,
    method: 'POST',
    body: {},
  });
}

/**
 * Decline a task — no grant is minted.
 * @param {string} token
 * @param {string} id
 * @returns {Promise<object>} updated task
 */
export function declineTask(token, id) {
  return apiFetch(`${BASE_TASKS}${encodeURIComponent(id)}/decline/`, {
    token,
    method: 'POST',
    body: {},
  });
}

/**
 * Subscribe to the inbox SSE stream and deliver newly-created tasks.
 *
 * Uses fetch + ReadableStream (NOT EventSource, which cannot send an
 * Authorization header). Returns a cleanup function that aborts the stream.
 *
 * @param {string} token - JWT access token
 * @param {{onTask?: (task: object) => void, onError?: (message: string) => void, signal?: AbortSignal}} [handlers]
 * @returns {() => void} cleanup
 */
export function subscribeInboxStream(token, { onTask, onError, signal } = {}) {
  const controller = signal ? null : new AbortController();
  const abortSignal = signal || controller.signal;

  (async () => {
    try {
      const response = await apiFetchStream(`${BASE_INBOX}stream/`, {
        token,
        signal: abortSignal,
      });
      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split('\n\n');
        buffer = frames.pop();

        for (const frame of frames) {
          const line = frame.trim();
          if (!line.startsWith('data:')) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try {
            onTask?.(JSON.parse(payload));
          } catch {
            // ignore malformed frames
          }
        }
      }
    } catch (err) {
      if (err?.name === 'AbortError') return;
      onError?.(err?.message || 'Inbox stream unavailable');
    }
  })();

  return () => controller?.abort();
}
