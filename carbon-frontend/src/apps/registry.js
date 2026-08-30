// src/apps/registry.js
// Platform App Registry — list all installed domain apps here.
// Shell reads this file at startup.
// RULE: never import from Shell or platform core into this file.

import carbonManifest from './carbon/manifest.js';
import healthyManifest from './healthy/manifest.js';
import peopleManifest from './people/manifest.js';
import stubManifest from './stub/manifest.js';

// Registration policy: REGISTER-ALL + ENABLE-PER-INSTANCE.
// Every installed app manifest is imported and registered here so the shell,
// Platform Home, and admin tooling can discover it uniformly. Per-instance
// visibility is NOT decided here — it is gated by backend
// PlatformAppConfig.is_enabled (consumed via useEnabledApps()/isAppEnabled)
// plus hasAppAccess at render time.

export const APP_REGISTRY = [
  carbonManifest,
  healthyManifest,
  peopleManifest,
  stubManifest,
];

/** Look up a manifest by app id. */
export const APP_BY_ID = Object.fromEntries(
  APP_REGISTRY.map(m => [m.id, m])
);
