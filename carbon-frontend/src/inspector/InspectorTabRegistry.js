// src/inspector/InspectorTabRegistry.js
// Contextual Inspector tab registry (contribution-point pattern — see ADR-0019).
//
// Domain tabs (Health, Governance, Activity, Lineage, Impact, …) register
// declaratively here. The global drawer composes its tab bar as:
//   [ fixed "Notes" tab ] + [ every registered tab whose `matches(context)` is true ]
//
// A tab is self-contained: it fetches its own data from `context` (entityType /
// entityId / label / payload) and must never rely on page-propped data.
//
// Singleton, mirroring the platform app registry precedent. RULE: never import
// from Shell or platform core into this file.

const registry = new Map(); // id -> provider

// ── Reactivity ─────────────────────────────────────────────────────────────
// The registry is a plain singleton Map, so it is NOT reactive by itself. We add a
// tiny external-store contract (subscribe + version snapshot) so `useSyncExternalStore`
// can re-render the drawer whenever a tab registers/unregisters at runtime.
let version = 0;
const listeners = new Set();

function notify() {
  version += 1;
  listeners.forEach((listener) => listener());
}

/** Subscribe to registry changes. Returns an unsubscribe function. */
export function subscribeInspectorTabs(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Snapshot: a monotonically increasing version number (changes on register/unregister). */
export function getInspectorTabsVersion() {
  return version;
}

/**
 * Register an inspector tab provider.
 *
 * provider shape:
 *   id:      string  — stable, unique tab id (also used as the persisted active-tab value)
 *   label:   string | (t) => string — display label; `t` is the drawer's i18n `t`
 *   icon:    React component — optional, rendered inline before the label
 *   order:   number — ascending sort key (default 100; Notes is always first)
 *   matches: (context) => boolean — optional; default true (tab always shows)
 *   render:  (context) => ReactNode — REQUIRED; the active tab's body
 *
 * Returns an unregister function (usable as a React effect cleanup).
 */
export function registerInspectorTab(provider) {
  if (!provider || typeof provider.id !== 'string' || !provider.id) {
    console.warn('[InspectorTabRegistry] rejected provider without a valid `id`', provider);
    return () => {};
  }
  if (typeof provider.render !== 'function') {
    console.warn(`[InspectorTabRegistry] rejected provider "${provider.id}" without a render()`);
    return () => {};
  }
  registry.set(provider.id, provider);
  notify();
  return () => {
    if (registry.get(provider.id) === provider) {
      registry.delete(provider.id);
      notify();
    }
  };
}

/** All tabs matching the given context, sorted by `order` (Notes tab is added separately). */
export function tabsFor(context) {
  return [...registry.values()]
    .filter((provider) => !provider.matches || provider.matches(context))
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
}

/** Resolve a provider's label (string or t-factory) with the given i18n `t`. */
export function tabLabel(provider, t) {
  if (!provider) return '';
  if (typeof provider.label === 'function') return provider.label(t);
  return provider.label ?? provider.id;
}

/** Number of registered tabs (mainly for diagnostics/tests). */
export function inspectorTabCount() {
  return registry.size;
}

/** Test-only: clear the registry so tests are isolated. */
export function _resetInspectorTabRegistry() {
  registry.clear();
  notify();
}
