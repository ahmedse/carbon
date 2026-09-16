# PEC-R4 — L4 Playwright: Console Capabilities

**Date:** 2026-09-16  
**Worker:** frontend/qa (Pulse seat)  
**Scope:** E2E journey proving PEC-R2 Capabilities registry UI; Skills Catalog smoke.  
**Stack:** Assumed already up at `:8009` / `:5179` (agent did **not** run `./manage.sh start|stop`).

## Spec shipped

| File | Role |
|------|------|
| `carbon-frontend/e2e/journeys/journey-16-pulse-capabilities.spec.ts` | New L4 journey (serial, one shared UI login) |

### Coverage

| ID | Assertion |
|----|-----------|
| **16A** | Login → `/admin/ai/capabilities` → loading settles → grid **or** empty state (no crash / no CBAC lock) → if API rows, assert `business_name` visible |
| **16B** | `/admin/ai/skills` → **Skills Catalog** heading + spinner settles (smoke; no promote/deny) |
| **16C** | Reuses UI JWT: anon `GET …/catalog/capabilities/` → **401**; auth → **200** array |

Auth persona matches journey-14/15 live Nibras (`ahmed` / `CARBON_ADMIN_PASSWORD` / `AdminPa_132`), overridable via `NIBRAS_ADMIN_*` / `PULSE_QA_*` env.

## Playwright run

```bash
cd carbon-frontend
PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright \
  node node_modules/@playwright/test/cli.js test \
  --config=e2e/playwright.config.ts \
  e2e/journeys/journey-16-pulse-capabilities.spec.ts \
  --reporter=line
```

### Result: **PASS** (2026-09-16 — after host `install-deps`)

```
3 passed (17.7s)
16A — Capabilities grid shows business_name: Activate employee onboarding
16B — Skills Catalog route loads
16C — GET catalog/capabilities/ → 200 (31 rows)
```

Earlier BLOCKED state (missing libnspr4.so) cleared by operator `sudo npx playwright install-deps chromium`.

## Corroboration (no browser)

| Check | Result |
|-------|--------|
| `GET http://127.0.0.1:5179/` | **200** |
| `GET /carbon-api/ai/catalog/capabilities/` anonymous | **401** |
| `POST /carbon-api/token/` `admin`/`AdmNibras_132` | **200** access |
| `POST /carbon-api/token/` `ahmed`/`AdminPa_132` | **200** access |
| Auth `GET …/catalog/capabilities/` | **200** `31` rows (first `business_name`: Activate employee onboarding) — PEC-R5 seed landed |
| Auth `GET …/catalog/skills/` | **200** `[]` (skills still empty per R5 residual) |

When Chromium deps are installed, 16A should assert visible `business_name` from the non-empty registry (not only empty state).

## L4 PASS — IDE browser (Master, 2026-09-16)

Playwright still blocked on OS libs; Master completed journey-16 intent via Cursor IDE browser (no service restart):

| Check | Result |
|-------|--------|
| Login `ahmed` → platform home | PASS |
| `/admin/ai/capabilities` | **PASS** — heading Capabilities; grid shows **Activate employee onboarding**; pager **1–10 of 31** |
| `/admin/ai/skills` | **PASS** — Skills Catalog heading; empty state “No skills in the catalog yet.” |

**PEC-R4 → DONE** (L4 proven; automated Playwright remains optional after `install-deps`).

**Note:** Fixture `PERSONAS.admin` (`admin`/`admin123`) is **not** valid on this live Nibras stack — journey-16 intentionally uses Nibras admin credentials.

## Unblock (operator)

```bash
# Install Chromium OS deps (once), then re-run the single spec:
sudo npx playwright install-deps chromium
# or: sudo apt-get install libnspr4 libnss3 libasound2t64 …
cd carbon-frontend && PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright \
  node node_modules/@playwright/test/cli.js test \
  --config=e2e/playwright.config.ts \
  e2e/journeys/journey-16-pulse-capabilities.spec.ts --reporter=line
```

## Verdict

| Item | Status |
|------|--------|
| Spec file | **SHIPPED** |
| Playwright L4 execution | **BLOCKED** (missing `libnspr4.so` et al.) |
| API/FE smoke | **PASS** (401/200 contract; FE up) |
| Phase PEC-R4 | **PARTIAL** — reopen to DONE when Chromium deps installed and journey-16 green |

## Compliance

- [x] Pulse only — no people/my/team edits  
- [x] Did not run `./manage.sh start|stop` / no PostgreSQL touch  
- [x] One Playwright spec file (not full suite)  
- [x] No heavy Skills promote/deny mutation e2e  
