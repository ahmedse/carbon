// src/apps/registry.js
// Platform App Registry — list all installed domain apps here.
// Shell reads this file at startup.
// RULE: never import from Shell or platform core into this file.
//
// RULE_15: the shell's studio/sidebar resolution (src/shell/studioFromPath.js)
// derives each app's route prefix from its manifest `routePrefix` below. Register
// the manifest here and STUDIO RESOLUTION FOLLOWS — no per-route string match.
// A new app-scoped ROUTER (/journey, /guide, /apps) must be added to
// APP_SCOPED_ROUTE_PREFIXES in studioFromPath.js at the same time.

import carbonManifest from './carbon/manifest.js';
import healthyManifest from './healthy/manifest.js';
import peopleManifest from './people/manifest.js';
import myManifest from './my/manifest.js';
import teamManifest from './team/manifest.js';
import stubManifest from './stub/manifest.js';
import gradevanceManifest from './gradevance/manifest.js';
import learnManifest from './learn/manifest.js';
import teachManifest from './teach/manifest.js';

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
  myManifest,
  teamManifest,
  stubManifest,
  gradevanceManifest,
  learnManifest,
  teachManifest,
];

/** Look up a manifest by app id. */
export const APP_BY_ID = Object.fromEntries(
  APP_REGISTRY.map(m => [m.id, m])
);
