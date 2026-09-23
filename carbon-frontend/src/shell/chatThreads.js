/**
 * In-session chat threads (Copilot-style) — same conversation_id, many topics.
 * Membership is client-side (localStorage). Sessions accordion and /fork are unchanged.
 * RULE_17: key pattern carbon-pulse-threads-{conversationId}.
 */
const KEY_PREFIX = 'carbon-pulse-threads-';
export const MAIN_THREAD_ID = 'main';

function storageKey(conversationId) {
  return `${KEY_PREFIX}${conversationId}`;
}

function emptyState() {
  return {
    activeId: MAIN_THREAD_ID,
    threads: [
      {
        id: MAIN_THREAD_ID,
        titleKey: 'mainThread',
        title: null,
        fromMessageId: null,
        createdAt: new Date().toISOString(),
      },
    ],
    membership: {},
  };
}

export function loadThreadState(conversationId) {
  if (!conversationId) return emptyState();
  try {
    const raw = window.localStorage.getItem(storageKey(conversationId));
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.threads) || !parsed.threads.length) {
      return emptyState();
    }
    if (!parsed.threads.some((t) => t.id === MAIN_THREAD_ID)) {
      parsed.threads.unshift(emptyState().threads[0]);
    }
    if (!parsed.membership || typeof parsed.membership !== 'object') {
      parsed.membership = {};
    }
    if (!parsed.activeId || !parsed.threads.some((t) => t.id === parsed.activeId)) {
      parsed.activeId = MAIN_THREAD_ID;
    }
    return parsed;
  } catch {
    return emptyState();
  }
}

export function saveThreadState(conversationId, state) {
  if (!conversationId || !state) return;
  try {
    window.localStorage.setItem(storageKey(conversationId), JSON.stringify(state));
  } catch {
    /* quota / private mode */
  }
}

export function titleFromContent(content, max = 42) {
  const line = String(content || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!line) return '';
  if (line.length <= max) return line;
  return `${line.slice(0, max - 1)}…`;
}

export function createThreadId() {
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

/** Assign message ids to a thread. Returns next state. */
export function assignToThread(state, messageIds, threadId) {
  const membership = { ...state.membership };
  for (const id of messageIds) {
    if (id == null) continue;
    membership[String(id)] = threadId;
  }
  return { ...state, membership };
}

/**
 * Messages with no membership join the active thread (or main on first load).
 * Keeps legacy linear logs visible under Main.
 */
export function claimUnassigned(state, messages, fallbackThreadId = MAIN_THREAD_ID) {
  const membership = { ...state.membership };
  let changed = false;
  for (const msg of messages || []) {
    const id = String(msg.id);
    if (membership[id] == null) {
      membership[id] = fallbackThreadId;
      changed = true;
    }
  }
  return changed ? { ...state, membership } : state;
}

export function messagesForThread(messages, state) {
  const active = state?.activeId || MAIN_THREAD_ID;
  const membership = state?.membership || {};
  return (messages || []).filter((m) => {
    const tid = membership[String(m.id)];
    if (tid == null) return active === MAIN_THREAD_ID;
    return tid === active;
  });
}

export function turnCount(state, threadId) {
  const membership = state?.membership || {};
  let n = 0;
  for (const tid of Object.values(membership)) {
    if (tid === threadId) n += 1;
  }
  return n;
}

export function addThread(state, { title, fromMessageId = null } = {}) {
  const id = createThreadId();
  const thread = {
    id,
    title: title || null,
    titleKey: title ? null : 'newThread',
    fromMessageId: fromMessageId ? String(fromMessageId) : null,
    createdAt: new Date().toISOString(),
  };
  return {
    ...state,
    activeId: id,
    threads: [...state.threads, thread],
  };
}

export function setActiveThread(state, threadId) {
  if (!state.threads.some((t) => t.id === threadId)) return state;
  return { ...state, activeId: threadId };
}

export function renameThread(state, threadId, title) {
  return {
    ...state,
    threads: state.threads.map((t) =>
      t.id === threadId ? { ...t, title, titleKey: null } : t,
    ),
  };
}
