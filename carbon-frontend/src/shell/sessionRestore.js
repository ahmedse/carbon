// Durable shell session pointers (RULE_17). Pulse chat/mode already have
// their own keys; this module covers last Task plan + last brand route so
// reopen lands on the working surface, not the empty landing.

export const ACTIVE_PLAN_KEY = 'carbon-ai-active-plan';
export const LAST_PATH_KEY = 'carbon-last-path';

const AUTH_PATH_RE = /^\/(login|forgot-password|reset-password|select-project)(\/|$)/i;

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

/** Paths that must never become a post-login landing. */
export function isEphemeralPath(pathname) {
  if (!pathname || pathname === '/') return false;
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
