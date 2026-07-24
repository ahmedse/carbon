// src/apps/registry.js
// Platform App Registry — list all installed domain apps here.
// Shell reads this file at startup.
// RULE: never import from Shell or platform core into this file.

import carbonManifest from './carbon/manifest.js';
// ── Add new app imports below this line ──

export const APP_REGISTRY = [
  carbonManifest,
];

/** Look up a manifest by app id. */
export const APP_BY_ID = Object.fromEntries(
  APP_REGISTRY.map(m => [m.id, m])
);
