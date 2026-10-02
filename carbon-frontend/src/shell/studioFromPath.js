/**
 * Studio route registry — the ONE mapping from a frontend path to the
 * ActivityBar studio (and therefore the sidebar) that owns it.
 *
 * RULE_15 — an app-scoped route prefix MUST resolve its studio through this
 * registry. Adding a path prefix to App.jsx WITHOUT registering it here is a
 * defect: an unregistered app-scoped prefix silently falls back to "home" and
 * the domain app's sidebar empties (the /guide/carbon and /journey/carbon bugs).
 *
 * Two registration points:
 *   1. `APP_SCOPED_ROUTE_PREFIXES` — routers whose SECOND segment is an app id
 *      (`/journey/<appId>`, `/guide/<appId>`, `/apps/<appId>`). Add a router
 *      here the moment a new app-scoped route type is introduced.
 *   2. Each app's `routePrefix` in `src/apps/<id>/manifest.js` — the app's own
 *      studio namespace (`/carbon/**`, `/people/**`). No code change needed for
 *      a new app; registering the manifest is enough.
 * Platform (shell-owned) prefixes live in `PLATFORM_ROUTE_STUDIOS` below.
 * `studioFromPath.test.js` scans App.jsx and fails on any unregistered prefix.
 */
import { APP_REGISTRY } from '../apps/registry';

// Routers of the form `/<router>/<appId>/…`; the app id names the studio.
export const APP_SCOPED_ROUTE_PREFIXES = ['journey', 'guide', 'apps'];

// Shell-owned studios that are not app manifests. Longest prefix wins.
export const PLATFORM_ROUTE_STUDIOS = {
  apps: 'apps',
  catalog: 'catalog',
  dq: 'catalog',
  modules: 'catalog',
  'schema-admin': 'catalog',
  emissions: 'carbon',
  dataschema: 'carbon',
  scopes: 'carbon',
  'data-owner': 'carbon',
  'admin/ai': 'ai-admin',
  admin: 'admin',
  settings: 'settings',
  help: 'help',
  feedback: 'help',
};

// Routes that intentionally resolve to the platform Home studio.
export const HOME_ROUTE_PREFIXES = [
  'login', 'embed', 'forgot-password', 'reset-password', 'change-password',
  'dashboard', 'dashboards',
];

const APP_IDS = new Set(APP_REGISTRY.map((m) => m.id));

function firstSegment(value) {
  return String(value || '').split('/').filter(Boolean)[0] || '';
}

// App studios derived from the manifest registry (single source of truth).
export const APP_ROUTE_STUDIOS = APP_REGISTRY.reduce((map, manifest) => {
  const base = firstSegment(manifest.routePrefix || `/${manifest.id}`);
  // `/apps/<appId>` is resolved by app id via APP_SCOPED_ROUTE_PREFIXES.
  if (base && !APP_SCOPED_ROUTE_PREFIXES.includes(base)) map[base] = manifest.id;
  return map;
}, {});

const MATCHERS = [
  ...Object.entries(PLATFORM_ROUTE_STUDIOS),
  ...Object.entries(APP_ROUTE_STUDIOS),
]
  .map(([prefix, studio]) => ({ segments: prefix.split('/').filter(Boolean), studio }))
  .sort((a, b) => b.segments.length - a.segments.length);

/** Every top-level prefix this registry knows about (used by the coverage test). */
export const REGISTERED_ROUTE_PREFIXES = new Set([
  ...Object.keys(PLATFORM_ROUTE_STUDIOS).map(firstSegment),
  ...Object.keys(APP_ROUTE_STUDIOS),
  ...APP_SCOPED_ROUTE_PREFIXES,
  ...HOME_ROUTE_PREFIXES,
]);

/**
 * Resolve the studio that owns `pathname`.
 * `/journey/carbon`, `/guide/carbon` and `/carbon/**` all resolve to `carbon`;
 * a truly platform route resolves to `home`.
 */
export function studioFromPath(pathname) {
  const parts = String(pathname || '/').split('/').filter(Boolean);
  if (parts.length === 0) return 'home';

  // `/<router>/<appId>/…` — the app id names the studio.
  if (APP_SCOPED_ROUTE_PREFIXES.includes(parts[0]) && parts[1]) {
    return APP_IDS.has(parts[1]) ? parts[1] : 'home';
  }

  // Longest registered prefix wins (`/admin/ai` before `/admin`).
  const match = MATCHERS.find(({ segments }) => segments.every((seg, i) => parts[i] === seg));
  return match ? match.studio : 'home';
}
