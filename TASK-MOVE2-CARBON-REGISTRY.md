# TASK: Move 2 — Manifest Registry (Shell Wiring + Isolation Proof)

> Reference: `docs/PLATFORM_APP_MODEL.md` §8 — Move 2 scope

## Goal

Make the platform shell **data-driven from manifests** — navigation items and studio entries come
from `src/apps/registry.js`, not hardcoded switch statements. Prove the pattern works by
registering a second trivial app with **zero changes to Shell files**.

---

## Architecture Rule (inviolable)

```
Shell files (Shell.jsx, ShellSidebar.jsx, useShellState.js)
  ↓ import from
src/apps/registry.js
  ↓ import from
src/apps/carbon/manifest.js, src/apps/stub/manifest.js, …
```

**Core never imports from a single app directly.** Shell imports from the registry only.

---

## Two Tracks — Sequential (G2 starts after G1 is merged)

```
G1 ── Shell Registry Wiring ──> merge
                                  └── G2 ── Stub App Isolation Proof ──> merge
```

---

## G1 — Shell Registry Wiring

### Worker constraints
- Only touch the files listed below.
- Do not break existing studios (home, emissions, dataschema, catalog, admin, settings, help).
- No new npm packages. MUI icons already present in the codebase.

### Files to read before starting
1. `carbon-frontend/src/apps/carbon/manifest.js` — understand manifest structure
2. `carbon-frontend/src/shell/useShellState.js` — understand DEFAULT_STUDIOS + useMemo
3. `carbon-frontend/src/shell/Shell.jsx` lines 24–43 — STUDIO_PATHS and studioFromPath
4. `carbon-frontend/src/shell/ShellSidebar.jsx` lines 1–114 — getSidebarItems + getStudioTitle

---

### G1.1 — Create `carbon-frontend/src/apps/registry.js` (NEW FILE)

```js
// src/apps/registry.js
// Platform App Registry — list all installed domain apps here.
// Shell reads this file at startup.
// RULE: never import from Shell or platform core into this file.

import carbonManifest from './carbon/manifest.js';
import LayersIcon from '@mui/icons-material/Layers'; // stub icon (Move 3: move icon to manifest)
// ── Add new app imports below this line ──

export const APP_REGISTRY = [
  carbonManifest,
  // ── G2 will add stubManifest here ──
];

/** Look up a manifest by app id. */
export const APP_BY_ID = Object.fromEntries(
  APP_REGISTRY.map(m => [m.id, m])
);
```

---

### G1.2 — Update `carbon-frontend/src/shell/useShellState.js`

#### 1. Add import after existing icon imports (after line 12)

**BEFORE** (line 12 is the last icon import):
```js
import HelpIcon from '@mui/icons-material/Help';
```

**AFTER**:
```js
import HelpIcon from '@mui/icons-material/Help';
import LayersIcon from '@mui/icons-material/Layers';
import { APP_REGISTRY } from '../apps/registry';
```

#### 2. Replace `DEFAULT_STUDIOS` constant with `PLATFORM_STUDIOS` + icon map

**BEFORE** (lines 14–60):
```js
// Studio definitions (can be extended per user role)
const DEFAULT_STUDIOS = [
  { 
    id: 'home', 
    label: 'Dashboard', 
    icon: DashboardIcon, 
    path: '/dashboard' 
  },
  { 
    id: 'emissions', 
    label: 'Emissions', 
    icon: Co2Icon, 
    path: '/emissions' 
  },
  {
    id: 'dataschema',
    label: 'Data Hub',
    icon: StorageIcon,
    path: '/dataschema'
  },
  {
    id: 'catalog',
    label: 'Catalog Studio',
    icon: CatalogIcon,
    path: '/catalog/domains'
  },
  {
    id: 'admin',
    label: 'Admin',
    icon: AdminPanelSettingsIcon,
    path: '/admin/users'
  },
  { 
    id: 'settings', 
    label: 'Settings', 
    icon: SettingsIcon, 
    path: '/settings', 
    bottom: true 
  },
  { 
    id: 'help', 
    label: 'Help', 
    icon: HelpIcon, 
    path: '/help', 
    bottom: true 
  },
];
```

**AFTER**:
```js
// Platform studios — shell-owned, NOT app-manifest-driven.
// App studios are injected dynamically from APP_REGISTRY below.
const PLATFORM_STUDIOS = [
  { id: 'home',       label: 'Dashboard',      icon: DashboardIcon,          path: '/dashboard'       },
  // ── App studios injected here at runtime ──
  { id: 'emissions',  label: 'Emissions',       icon: Co2Icon,                path: '/emissions'       },
  { id: 'dataschema', label: 'Data Hub',        icon: StorageIcon,            path: '/dataschema'      },
  { id: 'catalog',    label: 'Catalog Studio',  icon: CatalogIcon,            path: '/catalog/domains' },
  { id: 'admin',      label: 'Admin',           icon: AdminPanelSettingsIcon, path: '/admin/users'     },
  { id: 'settings',   label: 'Settings',        icon: SettingsIcon,           path: '/settings',  bottom: true },
  { id: 'help',       label: 'Help',            icon: HelpIcon,               path: '/help',      bottom: true },
];

// Icon lookup for manifest-declared apps.
// Move 3: replace with a full MUI dynamic icon loader.
const MANIFEST_ICON_MAP = {
  Co2:    Co2Icon,
  Layers: LayersIcon,
};
```

#### 3. Replace the `studios` useMemo (lines 81–86)

**BEFORE**:
```js
  const studios = useMemo(() => {
    if (!availablePerspectives?.includes('admin')) {
      return DEFAULT_STUDIOS.filter((studio) => studio.id !== 'admin');
    }
    return DEFAULT_STUDIOS;
  }, [availablePerspectives]);
```

**AFTER**:
```js
  const studios = useMemo(() => {
    // Derive app studios from the manifest registry.
    const appStudios = APP_REGISTRY.map(m => ({
      id:   m.id,
      label: m.name,
      icon: MANIFEST_ICON_MAP[m.icon] || Co2Icon,   // fallback to Co2Icon
      path: m.navigation.items.find(i => i.role === '*')?.path
            || m.navigation.items[0]?.path
            || `/${m.id}`,
    }));

    // Splice app studios in after 'home' (before 'emissions').
    const homeIdx = PLATFORM_STUDIOS.findIndex(s => s.id === 'home');
    const combined = [
      ...PLATFORM_STUDIOS.slice(0, homeIdx + 1),
      ...appStudios,
      ...PLATFORM_STUDIOS.slice(homeIdx + 1),
    ];

    if (!availablePerspectives?.includes('admin')) {
      return combined.filter(s => s.id !== 'admin');
    }
    return combined;
  }, [availablePerspectives]);
```

---

### G1.3 — Update `carbon-frontend/src/shell/Shell.jsx`

#### 1. Add `carbon` to STUDIO_PATHS (lines 24–32)

**BEFORE**:
```js
const STUDIO_PATHS = {
  home: '/dashboard',
  emissions: '/emissions',
  dataschema: '/dataschema',
  catalog: '/catalog/domains',
  admin: '/admin/users',
  settings: '/settings',
  help: '/help',
};
```

**AFTER**:
```js
const STUDIO_PATHS = {
  home:       '/dashboard',
  carbon:     '/carbon/owner/portal',   // app studio: default to owner portal
  emissions:  '/emissions',
  dataschema: '/dataschema',
  catalog:    '/catalog/domains',
  admin:      '/admin/users',
  settings:   '/settings',
  help:       '/help',
};
```

#### 2. Add `/carbon` branch to `studioFromPath` (lines 35–43)

**BEFORE**:
```js
function studioFromPath(pathname) {
  if (pathname.startsWith('/emissions')) return 'emissions';
  if (pathname.startsWith('/dataschema') || pathname.startsWith('/schema-admin')) return 'dataschema';
  if (pathname.startsWith('/catalog')) return 'catalog';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/help') || pathname.startsWith('/feedback')) return 'help';
  return 'home';
}
```

**AFTER**:
```js
function studioFromPath(pathname) {
  if (pathname.startsWith('/carbon')) return 'carbon';  // app studio — checked first
  if (pathname.startsWith('/emissions')) return 'emissions';
  if (pathname.startsWith('/dataschema') || pathname.startsWith('/schema-admin')) return 'dataschema';
  if (pathname.startsWith('/catalog')) return 'catalog';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/help') || pathname.startsWith('/feedback')) return 'help';
  return 'home';
}
```

---

### G1.4 — Update `carbon-frontend/src/shell/ShellSidebar.jsx`

#### 1. Add registry import after existing imports (after line 28)

**BEFORE** (line 28):
```js
import { useAuth } from '../auth/AuthContext';
```

**AFTER**:
```js
import { useAuth } from '../auth/AuthContext';
import { APP_REGISTRY } from '../apps/registry';
```

#### 2. Replace the `default` case in `getSidebarItems` (lines 98–100)

**BEFORE**:
```js
    default:
      return [];
  }
}
```

**AFTER**:
```js
    default: {
      // Dynamic lookup: if this studioId is a manifest app, return its nav items.
      // This makes ALL future apps work with zero additional changes here.
      const manifest = APP_REGISTRY.find(m => m.id === studioId);
      if (manifest) {
        return manifest.navigation.items.map(item => ({
          label: item.label,
          path:  item.path,
          icon:  DashboardIcon,   // Move 3: add iconName to manifest nav items
        }));
      }
      return [];
    }
  }
}
```

#### 3. Update `getStudioTitle` fallback (lines 103–114)

**BEFORE** (the `return` line):
```js
  return titles[studioId] || 'Carbon';
```

**AFTER**:
```js
  return titles[studioId]
    || APP_REGISTRY.find(m => m.id === studioId)?.name
    || 'Carbon';
```

---

### G1 Definition of Done

- [ ] `src/apps/registry.js` exists and exports `APP_REGISTRY` (array) + `APP_BY_ID` (map)
- [ ] Navigating to `/carbon/owner/portal` highlights the Carbon activity-bar icon
- [ ] Carbon sidebar shows 7 nav items (Dashboard, My Portal, My Dashboard, My Assets, Analytics, Reporting Periods, Emission Factors) — pulled from manifest, not hardcoded
- [ ] Existing studios (home, emissions, dataschema, catalog, admin) are unchanged
- [ ] `getSidebarItems('home')` still returns the 3 home items
- [ ] `getSidebarItems('catalog')` still returns all catalog items unchanged
- [ ] No new npm packages added
- [ ] No import of `apps/carbon/manifest.js` directly from Shell.jsx, ShellSidebar.jsx, or useShellState.js

---

## G2 — Stub App (Isolation Proof)

### Prerequisite: G1 merged and verified

### Worker constraints
- Zero changes to `Shell.jsx`, `ShellSidebar.jsx`, `useShellState.js`.
- The stub app wires itself via manifest + registry only.
- Minimal code — this is a proof, not a real feature.

### Files to read before starting
1. `carbon-frontend/src/apps/registry.js` (created by G1)
2. `carbon-frontend/src/apps/carbon/manifest.js` (template to follow)
3. `carbon-frontend/src/App.jsx` lines 160–170 (carbon routes pattern to follow)

---

### G2.1 — Create `carbon-frontend/src/apps/stub/manifest.js` (NEW FILE)

```js
// apps/stub/manifest.js
// Stub App — minimal isolation proof for the Platform App Model.
// Purpose: prove a second app registers with ZERO changes to any Shell file.

export default {
  id:          'stub',
  name:        'Stub App',
  version:     '0.1.0',
  description: 'Minimal isolation proof for the platform manifest registry',
  icon:        'Layers',
  color:       '#7b1fa2',

  routePrefix: '/stub',
  apiPrefix:   '/api/v1/stub',

  ontology:   { entities: [], relationships: [] },
  roles:      [],

  navigation: {
    section: 'Stub',
    items: [
      { label: 'Stub Home', path: '/stub', role: '*' },
    ],
  },

  requires:  ['auth'],
  aiSkills:  [],
  hooks:     {},
};
```

---

### G2.2 — Create `carbon-frontend/src/apps/stub/StubPage.jsx` (NEW FILE)

```jsx
// apps/stub/StubPage.jsx
// Stub App placeholder page — isolation proof only.

export default function StubPage() {
  return (
    <div style={{ padding: 32, fontFamily: 'sans-serif' }}>
      <h2>Stub App</h2>
      <p>
        This page proves a second domain app can register on the platform
        via <code>apps/registry.js</code> with <strong>zero changes</strong> to
        Shell.jsx, ShellSidebar.jsx, or useShellState.js.
      </p>
    </div>
  );
}
```

---

### G2.3 — Add stub to `carbon-frontend/src/apps/registry.js`

**BEFORE**:
```js
import carbonManifest from './carbon/manifest.js';
// ── Add new app imports below this line ──

export const APP_REGISTRY = [
  carbonManifest,
  // ── G2 will add stubManifest here ──
];
```

**AFTER**:
```js
import carbonManifest from './carbon/manifest.js';
import stubManifest   from './stub/manifest.js';    // ← G2: stub isolation proof
// ── Add new app imports below this line ──

export const APP_REGISTRY = [
  carbonManifest,
  stubManifest,    // ← G2: stub isolation proof
];
```

---

### G2.4 — Add stub route to `carbon-frontend/src/App.jsx`

#### 1. Add import near the carbon data-owner imports (after DataOwnerAssetsPage import)

**Find the block** (around line 50–65, where data-owner page imports are):
```js
import DataOwnerAssetsPage from './pages/data-owner/DataOwnerAssetsPage';
```

**Add after it**:
```js
import StubPage from './apps/stub/StubPage';
```

#### 2. Add route after the carbon routes block (after line 168)

**BEFORE**:
```js
                {/* Legacy redirects — remove in Move 2 */}
                <Route path="/data-owner" element={<Navigate to="/carbon/owner/portal" replace />} />
```

**AFTER**:
```js
                {/* Stub App — platform isolation proof (Move 2) */}
                <Route path="/stub" element={<StubPage />} />
                {/* Legacy redirects — remove in Move 3 */}
                <Route path="/data-owner" element={<Navigate to="/carbon/owner/portal" replace />} />
```

---

### G2 Definition of Done

- [ ] `src/apps/stub/manifest.js` exists
- [ ] `src/apps/stub/StubPage.jsx` exists
- [ ] `src/apps/registry.js` `APP_REGISTRY` array has 2 entries (carbon + stub)
- [ ] Navigating to `/stub` renders StubPage inside the Shell
- [ ] A "Stub App" studio icon appears in the ActivityBar
- [ ] Clicking the Stub App studio icon shows "Stub Home" in the sidebar (pulled from stub manifest)
- [ ] **Zero lines changed** in `Shell.jsx`, `ShellSidebar.jsx`, or `useShellState.js`
- [ ] Carbon studio and all existing studios still work correctly

---

## Files touched by Move 2 (complete list)

| File | Worker | Change type |
|---|---|---|
| `carbon-frontend/src/apps/registry.js` | G1 (create) → G2 (extend) | NEW + modified |
| `carbon-frontend/src/shell/useShellState.js` | G1 | Modified |
| `carbon-frontend/src/shell/Shell.jsx` | G1 | Modified (4 lines) |
| `carbon-frontend/src/shell/ShellSidebar.jsx` | G1 | Modified (8 lines) |
| `carbon-frontend/src/apps/stub/manifest.js` | G2 | NEW |
| `carbon-frontend/src/apps/stub/StubPage.jsx` | G2 | NEW |
| `carbon-frontend/src/App.jsx` | G2 | Modified (2 lines) |

---

## Do NOT change

- `carbon-frontend/src/apps/carbon/manifest.js` — already correct from Move 1
- Any existing page component files
- Any backend files
- Any existing routes (carbon owner routes are already registered from Move 1)
- The `emissions` studio and its hardcoded sidebar items — that refactor is Move 3+
- The legacy `/data-owner/*` redirects — keep them until Move 3 cleanup
