# DESIGN — Multi-Brand Architecture & Nibras Branding
## One Codebase · Many Instances · Many Apps · One Switch

> **Status:** Plan (v0.1). Not yet implemented.
> **Owner:** Master Architect.
> **Supersedes/extends:** `docs/CLEARTURN-PLATFORM-ARCHITECTURE.md`, `docs/NIBRAS-MASTER-STRATEGY.md`.
> **Goal:** Make the ClearTurn Trust Platform rebrand-able **per instance with a single switch**,
> ship an **amazing Nibras logo**, and make "disable all apps except the Nibras apps" a one-line,
> reproducible operation.

---

## 0. TL;DR

The platform **already** has 80% of the multi-brand plumbing: env-driven branding
(`config/branding.js`), per-instance `.env` presets, a runtime app enable/disable
mechanism (`PlatformAppConfig` → `useEnabledApps()`), and a frontend app registry.

What's **missing** to hit the ask:

1. **One-switch brand selection** — today you copy a `.env.instance.*` file; the theme
   palette, favicon, and app-enablement preset are *not* tied to that switch.
2. **Per-brand palette** — `carbonTheme.js` hardcodes blue `#2563eb`.
3. **Per-brand logos** — only one generic "data-mesh hexagon" mark exists; no Nibras mark.
4. **A brand → enabled-apps preset** — `bootstrap_platform.py` turns *everything* on;
   "Nibras = People only" is not encoded anywhere.

This plan introduces a **brand registry** (`src/brands/`) keyed by a single
`VITE_BRAND` env var, a **per-brand theme palette**, a **Nibras beacon logo**, and a
**brand → app-enablement preset** so switching is `VITE_BRAND=nibras` and rebuild.

---

## 1. AUDIT — WHAT EXISTS TODAY

### 1.1 Already env-driven (keep, don't rebuild)

| Surface | Mechanism | File |
|---------|-----------|------|
| Platform name / short / tagline / description / title | `VITE_*` env | `src/config/branding.js` |
| Instance (org) name | `VITE_INSTANCE_NAME` | `src/config/branding.js` |
| Header logo + title | `INSTANCE_LOGO`, `PLATFORM_TITLE` | `src/components/HeaderEnhanced.jsx` |
| Browser title + SEO/OG tags | `%VITE_*%` tokens | `index.html` |
| Instance presets | `.env.instance.{aastmt,nibras,tectona}` | `carbon-frontend/` |
| App enable/disable (runtime) | `PlatformAppConfig.is_enabled` | `backend/accounts/models.py` |
| Enablement API | `GET/PUT /accounts/platform-apps/` | `backend/accounts/views.py` |
| Frontend gating | `useEnabledApps()` + `isAppEnabled()` | `src/hooks/useEnabledApps.js` |
| App registry (frontend) | `APP_REGISTRY` (carbon, healthy, people, stub) | `src/apps/registry.js` |
| App registry (backend) | `settings.APP_REGISTRY` + `bootstrap_platform.APP_DEFS` | backend |

### 1.2 Gaps (what this plan fixes)

| # | Gap | Impact |
|---|-----|--------|
| G1 | **No single brand switch.** Branding is spread across 5+ `VITE_*` vars. | Error-prone; a logo change means editing 3 vars + rebuild. |
| G2 | **Theme palette hardcoded** blue in `carbonTheme.js`. | Nibras can't get amber/beacon colors without code change. |
| G3 | **No per-brand logo set.** Only generic blue hexagon + `aast_carbon_logo_.jpg`. | "Amazing representative logos" missing. |
| G4 | **No brand → app preset.** `bootstrap_platform.py` enables people + healthy + carbon + core. | "Disable all except Nibras apps" is manual admin toggling. |
| G5 | **Favicon hardcoded** to `/favicon.svg` in `index.html` (env `INSTANCE_FAVICON` exists but is not wired to `<link>`). | Favicon won't follow the brand. |
| G6 | **Registry drift.** Backend `settings.APP_REGISTRY` lacks `stub`; `bootstrap_platform.APP_DEFS` has it. | `isAppEnabled('stub')` falls back to `true`. |
| G7 | **`medOS` is undefined.** User named it as an intended system; no preset/doc/apps exist. | Needs a brand slot (assumptions documented below). |

### 1.3 Current app-enablement flow (for reference)

```
bootstrap_platform.py APP_DEFS ──seed──▶ PlatformAppConfig (is_enabled, display_order)
                                              │
settings.APP_REGISTRY ──▶ AppManifestService.load_manifests() ──▶ GET /accounts/platform-apps/
                                              │
        (frontend) useEnabledApps() ──fetch──┘
                                              │
   isAppEnabled(id) ──▶ useShellState (studios)  +  PlatformHome (cards)
```

Key rule: **an app is hidden only when `PlatformAppConfig.is_enabled=False` AND the app
is listed** (unknown ids default to visible). So "disable" must set the flag on the
*listed* app id in all three registries consistently.

---

## 2. TARGET ARCHITECTURE — CONFIG-DRIVEN BRAND REGISTRY

### 2.1 The single switch

Frontend (`carbon-frontend/.env`):

```
VITE_BRAND=nibras          # aastmt | nibras | medos | tectona
```

Backend (`backend/.env` / instance env):

```
DJANGO_BRAND=nibras        # drives app-enablement preset + Pulse instance id + email sender
```

One var on each side. Everything else (name, palette, logo, favicon, tagline, enabled
apps) resolves from a **brand registry** keyed by that var.

### 2.2 Brand registry shape (frontend `src/brands/`)

```
src/brands/
  index.js            # BRANDS map + resolveBrand(VITE_BRAND) + default fallback
  aastmt.js
  nibras.js
  medos.js
  tectona.js
```

```js
// src/brands/nibras.js
export default {
  id: 'nibras',
  // identity
  platformName: 'Nibras',
  platformShort: 'نبراس',
  instanceName: 'GOFSCO',
  title: 'GOFSCO · Nibras',            // optional override
  tagline: 'AI-Native Enterprise Platform for Oilfield Services',
  description: 'Nibras is an AI-native enterprise platform built on the ClearTurn Trust Platform…',
  canonicalUrl: 'https://nibras.clearturn.tech',
  // assets
  logo: '/logos/nibras.svg',
  favicon: '/logos/nibras-favicon.svg',
  // theme
  palette: {
    primary:   { main: '#f59e0b', light: '#fbbf24', dark: '#d97706', contrastText: '#0b1220' },
    secondary: { main: '#334155', light: '#475569', dark: '#1e293b', contrastText: '#ffffff' },
    // success/warning/error/info kept platform-wide
  },
  // enablement (informational mirror of backend preset)
  enabledAppIds: ['people'],
  // pulse
  pulseInstanceId: 'nibras',
};
```

`config/branding.js` becomes a thin resolver:

```js
import { resolveBrand } from '../brands';
const b = resolveBrand(import.meta.env.VITE_BRAND);
export const PLATFORM_NAME = b.platformName;
export const PLATFORM_SHORT = b.platformShort;
export const INSTANCE_NAME = b.instanceName;
export const INSTANCE_LOGO = b.logo;
export const INSTANCE_FAVICON = b.favicon;
export const PLATFORM_TITLE = b.title || (b.instanceName ? `${b.instanceName} · ${b.platformName}` : b.platformName);
export const PLATFORM_TAGLINE = b.tagline;
export const PLATFORM_DESCRIPTION = b.description;
export const BRAND_PALETTE = b.palette;
export const CANONICAL_URL = b.canonicalUrl;
export const PULSE_INSTANCE_ID = b.pulseInstanceId;
```

**Backwards compat:** if `VITE_BRAND` is unset, `resolveBrand` falls back to the current
individual `VITE_*` env vars (so nothing breaks until presets are migrated).

### 2.3 Per-brand theme

`getTheme(mode, direction)` gains a brand param; `carbonTheme.js` reads the brand
palette instead of hardcoded blue:

```js
// ThemedApp.jsx
const brand = resolveBrand(import.meta.env.VITE_BRAND);
const theme = getTheme(mode, isRtl ? 'rtl' : 'ltr', brand.palette);
```

Only `primary`/`secondary` change per brand; `success/warning/error/info` stay
platform-wide so status semantics never flip (red stays error, green stays success).

---

## 3. THE INTENDED BRANDS (identity + logo + palette + apps)

### 3.1 AASTMT Data Trust Platform
- **Customer:** Arab Academy for Science, Technology & Maritime Transport.
- **Brand:** "AASTMT · Data Trust Platform".
- **Palette:** current blue `#2563eb` (keep) — trust/authority.
- **Logo:** existing blue "data-mesh hexagon" mark (keep as-is; optionally add navy
  variant for light backgrounds).
- **Apps:** `carbon` (live); future `performarc`, `research-lifecycler`, `facilities-labs`, `sustainability-goals`.
- **Enabled:** `['carbon']`.

### 3.2 Nibras — نبراس (the focus)
- **Customer:** GOFSCO (Gas & Oil Field Services Company, Kuwait) — anchor customer.
- **Brand:** "GOFSCO · Nibras" / "نبراس".
- **Name meaning:** *beacon / lantern* — "the light that shows the way."
- **Palette (proposed):**
  - Primary **Beacon Amber** `#f59e0b` (light) / `#d97706` (dark) — the flame.
  - Secondary **Nibras Navy** `#0f172a` / `#1e293b` — the night sky / trust.
  - Contrast text on amber = navy (dark-on-light for accessibility).
- **Logo:** the **beacon/lantern** mark (Section 4.1) — navy tile, gold rays, amber flame.
- **Apps:** `people` (Nibras HRMS — live wedge); future `stores`, `fintrust` (finance),
  `procurement`, `assets`, `projects`.
- **Enabled:** `['people']` today.

### 3.3 ClearTurn medOS *(assumption — confirm)*
- **Customer:** ClearTurn's healthcare/medical-operations line (name implies "medical OS").
- **Brand:** "ClearTurn · medOS".
- **Palette:** teal/cyan `#0d9488` → `#06b6d4` (clinical + OS/tech).
- **Logo concept:** a rounded **cross** fused with a **circuit node/terminal** — health +
  operating system.
- **Apps:** none in codebase yet (future `clinical`, `claims`, `ops`…). Brand slot ships
  **empty** (only platform shell) until first app lands.

### 3.4 ClearTurn Tectona / Healthy AI
- **Customer:** ClearTurn's own flagship AI instance (showcase + first-party apps).
- **Brand:** "ClearTurn · Tectona" (*Tectona grandis* = teak).
- **Palette:** green `#059669` → `#10b981` (growth/teak).
- **Logo concept:** a **teak leaf** whose veins are **circuit traces** — nature + intelligence.
- **Apps:** `healthy` (factory AI); future first-party AI apps.
- **Enabled:** `['healthy']`.

### 3.5 (Parent) ClearTurn
- Optional 5th brand for ClearTurn's own umbrella site. Logo: a **turning arrow/spiral**
  (the "turn"). Palette: neutral zinc + one accent. Not required now — listed for completeness.

---

## 4. LOGO DESIGN — AMAZING, REPRESENTATIVE, REPRODUCIBLE

Design rules (apply to all marks):
- **Square SVG, 128×128 viewBox**, works at 16px favicon → 512px hero.
- **One tile + one glyph**, no text in the mark (wordmark lives in the header separately).
- **Family consistency:** every mark is a glyph on a dark rounded tile, echoing the
  current DTP tile — so all ClearTurn brands read as one product line with distinct identity.
- **Accessible contrast** and works in light + dark mode.

### 4.1 Nibras — the beacon/lantern mark (READY — SVG below)

Concept: a **flame of light rising from a lantern base, radiating rays into the dark** —
literally نبراس ("beacon/lantern"). Navy = night/trust, amber-gold = the guiding light.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" fill="none" role="img" aria-label="Nibras">
  <defs>
    <linearGradient id="nb-bg" x1="0" y1="0" x2="128" y2="128" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0b1220"/>
      <stop offset="1" stop-color="#16283f"/>
    </linearGradient>
    <linearGradient id="nb-flame" x1="64" y1="34" x2="64" y2="86" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#fde68a"/>
      <stop offset="0.5" stop-color="#f59e0b"/>
      <stop offset="1" stop-color="#d97706"/>
    </linearGradient>
    <linearGradient id="nb-gold" x1="0" y1="0" x2="128" y2="128" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#fbbf24"/>
      <stop offset="1" stop-color="#f59e0b"/>
    </linearGradient>
  </defs>

  <rect width="128" height="128" rx="28" fill="url(#nb-bg)"/>

  <!-- beacon light rays -->
  <g stroke="url(#nb-gold)" stroke-width="3" stroke-linecap="round" opacity="0.85">
    <line x1="64" y1="28" x2="64" y2="11"/>
    <line x1="64" y1="28" x2="90" y2="16"/>
    <line x1="64" y1="28" x2="104" y2="36"/>
    <line x1="64" y1="28" x2="38" y2="16"/>
    <line x1="64" y1="28" x2="24" y2="36"/>
  </g>

  <!-- flame / lantern body -->
  <path d="M64 34 C73 46 79 54 79 65 C79 77 71 85 64 85 C57 85 49 77 49 65 C49 54 55 46 64 34 Z" fill="url(#nb-flame)"/>

  <!-- inner flame core -->
  <path d="M64 52 C69 58 72 63 72 69 C72 75 68 79 64 79 C60 79 56 75 56 69 C56 63 59 58 64 52 Z" fill="#fff7ed" opacity="0.95"/>

  <!-- lantern base -->
  <path d="M52 91 H76" stroke="url(#nb-gold)" stroke-width="4" stroke-linecap="round"/>
  <path d="M57 96 H71" stroke="url(#nb-gold)" stroke-width="3" stroke-linecap="round"/>
</svg>
```

Delivery files:
- `carbon-frontend/public/logos/nibras.svg` (full mark, above)
- `carbon-frontend/public/logos/nibras-favicon.svg` (same mark; also referenced as favicon)
- Optional `nibras-wordmark.svg` (mark + "نبراس NIBRAS" lockup) for login/marketing.

### 4.2 Other marks (concepts — implement on approval)

| Brand | Glyph concept | Palette |
|-------|---------------|---------|
| AASTMT DTP | Data-mesh hexagon (keep current) | blue `#2563eb` |
| medOS | Rounded cross ⊕ fused with circuit terminal | teal `#0d9488` → cyan `#06b6d4` |
| Tectona | Teak leaf with circuit-trace veins | green `#059669` → `#10b981` |
| ClearTurn | Turning arrow / spiral | zinc + accent |

---

## 5. DISABLE ALL APPS EXCEPT NIBRAS APPS

### 5.1 Mechanism (already exists; needs a preset, not new code)

Visibility is gated by `PlatformAppConfig.is_enabled` (backend) → `useEnabledApps()` →
`isAppEnabled()` (frontend). To make "Nibras = People only" reproducible, add a
**brand → enabled-apps preset** and apply it in `bootstrap_platform`.

### 5.2 File-level changes

1. **`backend/config/settings.py`** — add:
   ```python
   DJANGO_BRAND = get_env("DJANGO_BRAND", "aastmt")
   ```
   and a `BRAND_APP_PRESETS` dict:
   ```python
   BRAND_APP_PRESETS = {
       "aastmt":  {"carbon": True,  "people": False, "healthy": False, "stub": False},
       "nibras":  {"carbon": False, "people": True,  "healthy": False, "stub": False},
       "medos":   {"carbon": False, "people": False, "healthy": False, "stub": False},
       "tectona": {"carbon": False, "people": False, "healthy": True,  "stub": False},
   }
   ```
   (Core apps `catalog/mdm/dq/connections/importexport/dataschema` remain enabled —
   they are platform capabilities, not domain-app cards; their admin access is still
   role-gated by `isCatalogAdmin`/`isGlobalAdmin`.)

2. **`backend/accounts/management/commands/bootstrap_platform.py`** — make `APP_DEFS`
   read `is_enabled` from `BRAND_APP_PRESETS[DJANGO_BRAND]` instead of the hardcoded
   `True/False`, so seeding a fresh DB yields the right per-brand flags. Keep the
   `display_order` mapping.

3. **Optional runtime command** — `python manage.py apply_brand nibras` to flip an
   already-seeded DB without wiping (idempotent `update_or_create` on `PlatformAppConfig`).

4. **`carbon-frontend/src/apps/registry.js`** — leave as **register-all** (do NOT delete
   manifests). Enablement stays data-driven; this preserves the "later more domain apps
   will be developed" extensibility. (Register-all + enable-per-instance is already the
   documented decision.)

5. **Fix G6 (registry drift)** — add `stub` to `settings.APP_REGISTRY` **or** drop it
   from `bootstrap_platform.APP_DEFS` so the three registries agree; otherwise
   `isAppEnabled('stub')` silently defaults to `true` and the Stub card can leak in.

### 5.3 Result in the Nibras instance

- **Activity bar:** Home · **People** · (Catalog Studio if catalog-admin) · Platform
  Admin (if admin) · AI Admin (if AI console) · Settings · Help.
- **Platform home:** single **People** card (plus future Stores/Finance cards).
- **Hidden:** Carbon, Healthy, Stub (and their nav/routes are no longer surfaced; direct
  deep-links still 404/redirect at the namespace boundary as today).

---

## 6. "EASY TO SWITCH" — THE SWITCHING PLAYBOOK

### 6.1 Build-time switch (recommended now)

Vite bakes `import.meta.env` at build time, so brand is a **build artifact**:

```bash
# switch to Nibras
cp carbon-frontend/.env.instance.nibras carbon-frontend/.env
# ensure the one line that matters:
#   VITE_BRAND=nibras
cd carbon-frontend && npm run build

# backend
export DJANGO_BRAND=nibras
python manage.py bootstrap_platform        # or: python manage.py apply_brand nibras
```

With `VITE_BRAND` set, the other `VITE_PLATFORM_*` vars become optional (resolved from
the registry). The preset files are reduced to `VITE_BRAND` + API URL + ports.

### 6.2 Runtime switch (future, optional)

If "switch without rebuild" is later required, move the brand registry to the backend
and expose `GET /accounts/brand/` (public) returning the resolved brand object; the
frontend fetches it once at startup before rendering `ThemedApp`. This is a natural
evolution but adds a network dependency at first paint — defer until a customer needs
same-URL, server-side brand switching.

### 6.3 Matrix of what changes per switch

| Axis | Where | Switch cost |
|------|-------|-------------|
| Name / tagline / title / SEO | `VITE_BRAND` → registry | rebuild |
| Logo + favicon | registry `logo`/`favicon` → `public/logos/` | rebuild (files static) |
| Theme palette | registry `palette` → `getTheme` | rebuild |
| Enabled apps | `DJANGO_BRAND` → preset → `PlatformAppConfig` | restart + `apply_brand` |
| Pulse instance id | `PULSE_INSTANCE_ID` (brand → env) | restart |
| Database | per-deployment | deploy-time (unchanged) |

---

## 7. IMPLEMENTATION PLAN (phased, file-level)

### Phase A — Brand registry + one-switch (core)
- [ ] `carbon-frontend/src/brands/{index,aastmt,nibras,medos,tectona}.js`
- [ ] Rewire `src/config/branding.js` → resolver (with `VITE_*` fallback)
- [ ] `src/theme/carbonTheme.js` → accept `palette` param; `getTheme.js` + `ThemedApp.jsx` pass brand palette
- [ ] `index.html` → wire `%VITE_INSTANCE_FAVICON%` into `<link rel="icon">` (fix G5)
- [ ] `main.jsx`/`App.jsx` → no change expected (consume resolved constants)
- [ ] Add `VITE_BRAND` to `.env.example` + each `.env.instance.*`

### Phase B — Logos
- [ ] Create `public/logos/nibras.svg` + `nibras-favicon.svg` (Section 4.1)
- [ ] (on approval) `aastmt.svg`, `medos.svg`, `tectona.svg`, `clearturn.svg`
- [ ] Add `public/logos/` + wordmark lockups as needed

### Phase C — App-enablement preset (Nibras = People only)
- [ ] `settings.py`: `DJANGO_BRAND` + `BRAND_APP_PRESETS`
- [ ] `bootstrap_platform.py`: derive `is_enabled` from preset
- [ ] New `apply_brand` management command (idempotent runtime flip)
- [ ] Fix G6 registry drift (`stub`)
- [ ] Verify: Nibras DB shows only `people` enabled; frontend shows only People card/studio

### Phase D — Docs + gates
- [ ] Update `docs/CLEARTURN-PLATFORM-ARCHITECTURE.md` (mark G2/G3/G4 done)
- [ ] Update `README.md` / `deploy/instance/README.md` with the one-line switch playbook
- [ ] Add `.ai-toolkit/scripts` or `verify.sh` check: `VITE_BRAND` ↔ `DJANGO_BRAND` consistency
- [ ] Add `medOS` to the instance matrix (assumption flagged for confirmation)

---

## 8. ACCEPTANCE GATES

1. `VITE_BRAND=nibras && npm run build` produces a UI titled **GOFSCO · Nibras** with the
   beacon logo, amber primary palette, Arabic-capable title (نبراس), and **only** the
   People app visible in the Activity bar + Platform Home.
2. Switching to `VITE_BRAND=tectona` shows **Healthy** only; `VITE_BRAND=aastmt` shows
   **Carbon** only — with zero code edits between the three.
3. `bootstrap_platform` (or `apply_brand nibras`) leaves `PlatformAppConfig` with
   `people.is_enabled=True` and `carbon/healthy/stub.is_enabled=False`.
4. Direct deep-links to hidden apps do not leak: `/carbon/...`, `/apps/healthy`, `/stub`
   are not reachable via nav in the Nibras instance (namespace boundary intact).
5. No manifest was deleted from `apps/registry.js` — adding a future domain app is still
   a manifest + registry line + `App.jsx` route (extensibility preserved).
6. `verify.sh` / import-audit still pass; `audit-imports.sh` app-boundary gates unchanged.

---

## 9. OPEN QUESTIONS (confirm before/while building)

1. **medOS** — confirm identity/palette/apps (Section 3.3 is an assumption).
2. **Wordmark language** — should Nibras show Arabic نبراس, Latin "NIBRAS", or a bilingual
   lockup in the header (the i18n layer already supports RTL + dual lang)?
3. **Runtime vs build-time switching** — build-time is recommended; confirm no
   same-URL/zero-redeploy requirement exists yet.
4. **Core-app visibility** — confirm `catalog/mdm/dq/connections/importexport/dataschema`
   stay enabled as platform capabilities (they don't appear as domain cards today).
