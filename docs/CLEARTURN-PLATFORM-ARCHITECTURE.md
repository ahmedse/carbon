# ClearTurn Trust Platform + Pulse — Product-Line Architecture
## One Codebase · Many Instances · Many Apps

> **Status:** Living document (v0.1 — 2026-08-30).
> **Owner:** ClearTurn (parent company). This document is the umbrella over every
> instance and app, including Nibras (see `docs/NIBRAS-MASTER-STRATEGY.md`).
> **Core asset:** the ClearTurn Trust Platform (Carbon Data Trust core) + Pulse (in-hand AI engine).

---

## 1. THE ONE-LINE ARCHITECTURE

> **One codebase = the ClearTurn Trust Platform + Pulse.**
> It is deployed as **multiple isolated instances**, each carrying its own **brand**,
> its own **enabled apps**, and its own **database**. Domain **apps** are hosted on the
> platform and are shared across the codebase but enabled per-instance.

Three nouns, kept strictly distinct:

| Noun | Definition | Examples |
|------|-----------|----------|
| **Platform** | The shared, app-agnostic core: Catalog, MDM, DQ, Evidence, Connections, RBAC/OrgUnit, AI/Pulse, shell. Owned by ClearTurn. | one, shared |
| **Instance** | A deployment for a customer/brand: its own env config, branding, enabled apps, isolated DB. | AASTMT · GOFSCO Nibras · ClearTurn Tectona |
| **App** | A hosted domain app that plugs into the platform (imports core, never imported by it, never imports a sibling app). | Carbon, Nibras HRMS, Healthy, … |

**Customers get a deployed instance, not the codebase.** Co-locating all apps in one repo
is invisible to customers — each instance shows only its brand, its apps, its data.

---

## 2. THE INSTANCE → APP MATRIX

> This is the product line. New instances and apps are added over time.

### Instance: **AASTMT Data Trust**
Customer: Arab Academy for Science, Technology & Maritime Transport (academic).
Brand: "AASTMT · Data Trust Platform".

| App | Purpose | Status |
|-----|---------|--------|
| **Carbon** | GHG / carbon emissions accounting (GHG Protocol) | LIVE |
| **Performarc** | Academic KPI management | FUTURE |
| **Research Lifecycler** | Research project lifecycle | FUTURE |
| **Facilities & Labs Manager** | Facilities and laboratory management | FUTURE |
| **Sustainability Goals Lifecycler** | Sustainability goal tracking | FUTURE |

### Instance: **GOFSCO Nibras**
Customer: Gas & Oil Field Services Company (Kuwait, oilfield services).
Brand: "Nibras / نبراس". Anchor customer for the commercial product.

| App | Purpose | Status |
|-----|---------|--------|
| **Nibras HRMS (People)** | KLL/GOSI/WPS-compliant HR + payroll | IN DESIGN (Phase 1 wedge) |
| **Stores** | Inventory / MIV-MRV / 4-store network | PLANNED (Phase 2) |
| **Finance** | Treasury, BRS, documents (layer on Sage) | PLANNED (Phase 3) |
| **(later)** | Procurement, Assets/Fleet, Projects | PLANNED |

See `docs/NIBRAS-MASTER-STRATEGY.md` for the full Nibras strategy.

### Instance: **ClearTurn Tectona**
Owner: ClearTurn's own flagship AI-platform instance (showcase + first-party apps).
Brand: "ClearTurn Tectona".

| App | Purpose | Status |
|-----|---------|--------|
| **Healthy** | Factory AI apps (health/ops intelligence) | IN CODEBASE |
| **(future)** | Additional first-party AI apps | FUTURE |

### Future instances
More customer/brand instances added as the product line grows. Each is env config +
enabled apps + isolated DB — **no fork, no new codebase.**

---

## 3. WHY ONE CODEBASE (AND NOT FORKS)

- **Shared platform evolves once.** Every Pulse fix, DQ engine improvement, and catalog
  feature lands once and benefits every instance. Forking mid-development would impose a
  perpetual, diverging port tax between repos.
- **Apps are already multi-tenanted in code.** The repo already hosts `carbon`, `healthy`,
  and `stub` apps side by side via manifests + an app registry. Nibras apps are more of
  the same pattern.
- **Isolation is a deployment concern, not a codebase concern.** Instances are separated by
  env config, app enablement, and separate databases — not by separate source trees.
- **IP stays consolidated.** All platform + app IP is ClearTurn's, in one governed repo.

---

## 4. HOW AN INSTANCE IS ISOLATED

| Axis | Mechanism | State today |
|------|-----------|-------------|
| **Branding** | `carbon-frontend/src/config/branding.js` — env-driven (`VITE_INSTANCE_NAME`, `VITE_PLATFORM_NAME`, `VITE_PLATFORM_TITLE`, `INSTANCE_LOGO`, `PLATFORM_TAGLINE`, `PLATFORM_TAGLINE`, `PLATFORM_DESCRIPTION`, `CANONICAL_URL`) | ✅ Done — wired through header, login, home, status bar, doc title, `<meta>` |
| **Enabled apps** | Backend `appregistry/` + `/accounts/platform-apps/` + frontend `useEnabledApps()` / `isAppEnabled()` | ✅ Exists — per-instance enable/disable works |
| **App registration** | `carbon-frontend/src/apps/registry.js` (`APP_REGISTRY`) + `src/apps/<app>/manifest.js` | ⚠️ Static (only `carbon` registered) — needs instance-aware or register-all-enable-per-instance |
| **Data** | Separate database per deployment | ✅ By deployment (see `docs/` deployment notes) |
| **Code boundaries** | Core never imports apps (RULE_3); apps never import sibling apps | ✅ Both gates in `.ai-toolkit/scripts/audit-imports.sh` — engine boundary (I1) + app-to-app boundary (I2); excludes tests/management tooling |
| **Instance .env presets** | Per-instance preset files deployers copy to `.env` | ✅ `carbon-frontend/.env.instance.{aastmt,nibras,tectona}` |
| **Theme** | `theme/carbonTheme.js` (name is cosmetic; palette is config) | ⚠️ Optional: generalize name/palette per instance |

---

## 5. WORK ITEMS TO FULLY PRODUCTIONIZE MULTI-INSTANCE

None are blockers; the model works today. Items marked ✅ are already done.

1. ✅ **App-to-app import guard.** Extended `audit-imports.sh` with gate I2: hosted apps
   may not import sibling apps; core apps may not import hosted apps. Tests and management
   commands are excluded (tooling exemption). Wired into `verify.sh`.
2. ✅ **Per-instance branding presets.** `carbon-frontend/.env.instance.{aastmt,nibras,tectona}`
   — deployers `cp` the relevant preset to `.env` and adjust API URL/ports.
3. ⚠️ **Instance-aware app registration.** Make `apps/registry.js` register the app set
   for the active instance (env-driven list), or register all apps and rely on backend
   `appregistry` enablement to gate them. Decide one and document it.
4. ⚠️ **DB isolation checklist.** Document the deploy guarantee that each instance uses
   its own database and cannot reach another instance's data.
5. ⚠️ **Theme per instance (deferred).** Allow palette/logo overrides per instance
   (rename `carbonTheme` → `platformTheme` when convenient; not urgent).
6. ⚠️ **Naming-debt cleanup (deferred).** "Carbon" doubles as platform name and app name.
   Decouple as the product line grows.

---

## 6. PLAYBOOK — ADDING A NEW APP

1. Create backend Django app `backend/<app>/` — imports `core`/`catalog`/`mdm`/`dq`/
   `evidence`/`connections`; **never** imported by them; **never** imports a sibling app.
2. Register Pulse domain ops in `ai/domain/<app>.py` (per RULE_19 — domain isolation).
3. Create frontend `src/apps/<app>/manifest.js` (identity, route/api namespace, ontology,
   RBAC roles) and add it to `apps/registry.js`.
4. Register the app in `appregistry/` so instances can enable/disable it.
5. Add routes to `App.jsx` + `studioFromPath()` (RULE_15) + index route (RULE_22).
6. Follow the design system (tokens, density, 4 data states) for all UI.

## 7. PLAYBOOK — ADDING A NEW INSTANCE

1. Create the deployment (its own DB, its own env).
2. Set branding env: `VITE_INSTANCE_NAME`, `VITE_PLATFORM_NAME`/`VITE_PLATFORM_TITLE`,
   `INSTANCE_LOGO`, `PLATFORM_TAGLINE`.
3. Enable the instance's apps via `appregistry` (and the registration approach from §5.1).
4. Seed instance-specific MDM reference data.
5. Deploy. No code fork — same codebase, different configuration.

---

## 8. RELATIONSHIP TO OTHER DOCS

| Doc | Scope |
|-----|-------|
| **This doc** | ClearTurn platform product line — instances, apps, isolation |
| `docs/NIBRAS-MASTER-STRATEGY.md` | The Nibras instance (GOFSCO) — strategy, compliance, roadmap |
| `ARCHITECTURE.md` / `.ai-toolkit/` | Platform internals, rules, conventions |
| `backend/appregistry/` | The app registry implementation |
| `carbon-frontend/src/config/branding.js` | Per-instance branding source of truth |
