/**
 * Ask and Plan are different chat sessions (not one thread with a toggle).
 *
 * ConversationState (slots, intent, decisions) is keyed by conversation_id.
 * Flipping Ask↔Plan on the same thread mixed a loan clarify with a Plan brief.
 * This module keeps a durable map: which Process dial owns which thread, and
 * the last active thread per dial so the switch can jump sessions.
 */

export const PROCESS_BY_CONV_KEY = 'carbon-ai-process-by-conv';
export const PROCESS_LAST_KEY = 'carbon-ai-process-last';

export function normalizePulseProcess(value) {
  return value === 'plan' ? 'plan' : 'ask';
}

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota / private mode */
  }
}

/** Read process from API payload (task_payload / task_payload_json) or local map. */
export function processForConversation(conversation) {
  if (!conversation) return 'ask';
  const payload = conversation.task_payload
    || conversation.task_payload_json
    || {};
  const fromPayload = payload.pulse_process || payload.pulse_mode;
  if (fromPayload === 'ask' || fromPayload === 'plan') {
    return fromPayload;
  }
  const map = readJson(PROCESS_BY_CONV_KEY, {});
  return normalizePulseProcess(map[conversation.id]);
}

export function rememberConversationProcess(conversationId, process) {
  if (!conversationId) return;
  const dial = normalizePulseProcess(process);
  const byConv = readJson(PROCESS_BY_CONV_KEY, {});
  byConv[conversationId] = dial;
  writeJson(PROCESS_BY_CONV_KEY, byConv);
  const last = readJson(PROCESS_LAST_KEY, {});
  last[dial] = conversationId;
  writeJson(PROCESS_LAST_KEY, last);
}

export function lastConversationForProcess(process, knownIds = null) {
  const dial = normalizePulseProcess(process);
  const last = readJson(PROCESS_LAST_KEY, {});
  const id = last[dial] || null;
  if (!id) return null;
  if (Array.isArray(knownIds) && knownIds.length > 0 && !knownIds.includes(id)) {
    return null;
  }
  return id;
}

/** Prefer an open thread tagged for this dial; else localStorage last. */
export function findConversationForProcess(process, conversations = []) {
  const dial = normalizePulseProcess(process);
  const tagged = conversations.find((c) => processForConversation(c) === dial);
  if (tagged?.id) return tagged.id;
  const knownIds = conversations.map((c) => c.id).filter(Boolean);
  return lastConversationForProcess(dial, knownIds);
}

export function processCreatePayload(process, title) {
  const dial = normalizePulseProcess(process);
  return {
    conversation_type: 'chat',
    title,
    task_payload: { pulse_process: dial },
  };
}
