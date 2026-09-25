// Durable shell session pointers (RULE_17). Pulse chat/mode already have
// their own keys; this module covers last Task plan + last brand route so
// reopen lands on the working surface, not the empty landing.
//
// Session expiry / logout must NOT wipe those pointers. Tokens die;
// last Nibras page + last Pulse thread survive, scoped per username.

export const ACTIVE_PLAN_KEY = 'carbon-ai-active-plan';
export const LAST_PATH_KEY = 'carbon-last-path';
export const BOUND_USER_KEY = 'carbon-workspace-user';
export const WORKSPACE_BY_USER_KEY = 'carbon-workspace-by-user';

export const COPILOT_VISIBLE_KEY = 'carbon-copilot-visible';
export const COPILOT_EXPANDED_KEY = 'carbon-copilot-expanded';
export const COPILOT_PANE_SIZE_KEY = 'carbon-copilot-pane-size';
export const ACTIVE_CONVERSATION_KEY = 'carbon-ai-active-conversation';
export const AI_MODE_KEY = 'carbon-ai-mode';
export const COMPOSER_PROCESS_KEY = 'carbon-ai-composer-process';
export const AGENT_VIEW_KEY = 'carbon-ai-agent-view';
export const TASK_TAB_KEY = 'carbon-ai-task-tab';
export const SIDEBAR_MODE_KEY = 'carbon-sidebar-mode';
export const DRAWER_WIDTH_KEY = 'carbon-drawer-width';

const AUTH_PATH_RE = /^\/(login|forgot-password|reset-password|select-project)(\/|$)/i;

/** Tokens and identity — these die with the session. Workspace pointers do not. */
export const AUTH_STORAGE_KEYS = Object.freeze([
  'access',
  'refresh',
  'user',
  'user_id',
  'projects',
  'context',
  'shell_employee',
  'user_capabilities',
  'is_global_admin',
  'available_perspectives',
  'org_units',
  'pulse_key',
]);

/** Live keys that travel with the operator (Nibras route + Pulse surface). */
export const WORKSPACE_LIVE_KEYS = Object.freeze([
  LAST_PATH_KEY,
  ACTIVE_PLAN_KEY,
  COPILOT_VISIBLE_KEY,
  COPILOT_EXPANDED_KEY,
  COPILOT_PANE_SIZE_KEY,
  ACTIVE_CONVERSATION_KEY,
  AI_MODE_KEY,
  COMPOSER_PROCESS_KEY,
  'carbon-ai-process-by-conv',
  'carbon-ai-process-last',
  AGENT_VIEW_KEY,
  TASK_TAB_KEY,
  SIDEBAR_MODE_KEY,
  DRAWER_WIDTH_KEY,
]);

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key, value) {
  try {
    if (value == null || value === '') localStorage.removeItem(key);
    else localStorage.setItem(key, String(value));
  } catch {
    /* ignore quota / private mode */
  }
}

function readJson(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

/** Username on the current (or just-expired) session. */
export function readStoredUsername() {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const name = parsed?.username;
    return typeof name === 'string' && name.trim() ? name.trim() : null;
  } catch {
    return null;
  }
}

/** Last Task plan the operator had open in Pulse Agent. */
export function readActivePlanId() {
  const id = safeGet(ACTIVE_PLAN_KEY);
  return id && id.trim() ? id.trim() : null;
}

export function writeActivePlanId(planId) {
  safeSet(ACTIVE_PLAN_KEY, planId || null);
}

export function clearActivePlanId() {
  safeSet(ACTIVE_PLAN_KEY, null);
}

/**
 * Paths that must never become a post-login landing.
 * `/dashboard` is a redirect alias to Home — remembering it clobbers People/My.
 */
export function isEphemeralPath(pathname) {
  if (!pathname) return true;
  if (pathname === '/dashboard') return true;
  return AUTH_PATH_RE.test(pathname);
}

/**
 * Remember the in-app route so login / hard refresh can return here.
 * Home (`/`) is allowed — it is a real studio for Nibras and every brand.
 */
export function rememberLastPath(pathname, search = '') {
  if (!pathname || isEphemeralPath(pathname)) return;
  const qs = search && search !== '?' ? search : '';
  safeSet(LAST_PATH_KEY, `${pathname}${qs}`);
  const username = readStoredUsername() || safeGet(BOUND_USER_KEY);
  if (username) snapshotWorkspace(username);
}

export function readLastPath() {
  const raw = safeGet(LAST_PATH_KEY);
  if (!raw || isEphemeralPath(raw.split('?')[0])) return null;
  return raw;
}

/**
 * Prefer the operator's last in-app route over the brand default landing
 * (`/dashboard` → Home). Invalid / auth paths fall through to `fallback`.
 */
export function resolveLandingPath(fallback = '/') {
  const last = readLastPath();
  if (!last) return fallback || '/';
  return last;
}

/** Park live Nibras + Pulse pointers under this username. */
export function snapshotWorkspace(username) {
  if (!username) return;
  const store = readJson(WORKSPACE_BY_USER_KEY) || {};
  const snap = {};
  for (const key of WORKSPACE_LIVE_KEYS) {
    snap[key] = safeGet(key);
  }
  store[username] = snap;
  try {
    localStorage.setItem(WORKSPACE_BY_USER_KEY, JSON.stringify(store));
  } catch {
    /* ignore quota */
  }
  safeSet(BOUND_USER_KEY, username);
}

/**
 * Bind live workspace keys to `username`.
 * Same user: keep whatever survived the token wipe.
 * Different user: restore that operator's snapshot, never the previous one.
 */
export function applyWorkspaceForUser(username) {
  if (!username) return;
  const bound = safeGet(BOUND_USER_KEY);
  if (bound === username) {
    snapshotWorkspace(username);
    return;
  }
  if (bound) snapshotWorkspace(bound);
  const store = readJson(WORKSPACE_BY_USER_KEY) || {};
  const snap = store[username];
  if (!snap) {
    if (bound && bound !== username) {
      for (const key of WORKSPACE_LIVE_KEYS) safeSet(key, null);
    }
    snapshotWorkspace(username);
    return;
  }
  for (const key of WORKSPACE_LIVE_KEYS) {
    safeSet(key, snap[key] ?? null);
  }
  safeSet(BOUND_USER_KEY, username);
}

/**
 * Drop tokens and identity. Keep last path, Pulse thread, mode, and pane
 * so re-login returns to the same Nibras page and Pulse surface.
 */
export function clearAuthStorage() {
  const username = readStoredUsername() || safeGet(BOUND_USER_KEY);
  if (username) snapshotWorkspace(username);
  for (const key of AUTH_STORAGE_KEYS) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  }
}
