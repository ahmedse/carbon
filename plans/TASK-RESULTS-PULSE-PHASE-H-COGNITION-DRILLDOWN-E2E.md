# TASK RESULTS — Pulse Phase H: Cognition Sweeps + Scheduler Hardening + Drill-downs + E2E (2026-08-14)

Follow-on phase to **Phase G (live analytics grounding + DQ write gate)**. Phase G was implemented
and gated but not yet committed; Phase H closes the four remaining "next" candidate items and this
batch is committed together with Phase G (surgical staging, see git commit).

| ID | Item | Outcome |
|----|------|---------|
| H1 | LLM-heavy cognition sweeps actually run (consolidation) | ✅ wired + gated; 3 tests |
| H2 | Scheduler supervisor hardening (heartbeat + graceful stop) | ✅ liveness file + docker healthcheck + stop grace |
| H3 | Per-row detail drill-downs in the Pulse panels | ✅ pure formatters + generic drawer; 8 tests |
| H4 | Browser E2E of the AI admin console + CBAC | ✅ journey-09; 4 tests |
| H5 | All gates | ✅ all green (see below) |
| H6 | Results + repo memory | ✅ this doc + `carbon-platform.md` updated |

---

## H1 — LLM-heavy cognition sweeps (consolidation) wired + gated

**File**: `backend/ai/engine/cognition/consolidation.py` (wired in Phase D, activated now) +
`backend/ai/tests/test_consolidation_sweep.py` (NEW).

The sleep-time **Extract → Reflect → Curate** pipeline is proven to be wired and correctly gated:

- `run_consolidation_sweep` **short-circuits (0 LLM calls)** when `CONSOLIDATION_SWEEP_ENABLED=false`
  (the default — LLM-heavy sweeps stay off until a POE-compatible `LLM_COGNITION_MODEL` is set).
- With a seeded active instance + repeated successful tool sequence, the sweep invokes
  `route_chat(task="cognition")` and curates a draft `Skill` row with `gate_status="pending"`.
- `extract_candidates` returns **no candidates** for a single trajectory row (the ≥2-row floor), so
  a cold instance never burns LLM budget.

The LLM is stubbed at `ai.engine.llm.router.route_chat` (imported locally inside
`reflect_on_candidates` at call time), so no live provider is hit. Engine models (`Instance`,
`Skill`, `Trajectory`) are imported from `ai.models.core` (Django ORM) — the SQLAlchemy-era
`ai.engine.core.models` classes have no `.objects` manager.

## H2 — Scheduler supervisor hardening (heartbeat + graceful stop)

**Files**: `backend/ai/engine/core/config.py`, `backend/ai/engine/cognition/loop.py`,
`docker-compose.yml`.

- New config: `COGNITION_HEARTBEAT_INTERVAL = 60` (s), `COGNITION_HEARTBEAT_FILE = /tmp/cognition_loop.heartbeat`.
- `loop.py` adds `_write_heartbeat()` (never raises — a healthcheck must not crash the scheduler) and
  `_run_heartbeat()`; `start_scheduler()` writes the heartbeat **first** and registers an
  interval job `id="heartbeat"` at `COGNITION_HEARTBEAT_INTERVAL`.
- `docker-compose.yml`: `stop_grace_period: 60s` (lets `stop_scheduler()` → `shutdown(wait=False)`
  finish in-flight jobs on SIGTERM) + a `healthcheck` that asserts the heartbeat file is < 180s old
  (restart policy recovers a wedged loop).

## H3 — Per-row detail drill-downs in the Pulse panels

**Files**: `carbon-frontend/src/pages/admin/ai/pulseFormat.js` (NEW, pure),
`carbon-frontend/src/pages/admin/ai/PulseDataPanel.jsx`.

- `pulseFormat.js` = dependency-free formatters so they are unit-testable without pulling in MUI
  DataGrid / auth / API deps: `SCOPE_FIELDS`, `formatCellValue` (null→`—`, JSON stringify + 80-char
  truncate), `buildScopeLabel` (app/org/user/visibility → one line), `buildDetailFields` (row key/value
  list minus internal `_type` + scope helper columns).
- `PulseDataPanel.jsx` = generic read-only panel (props `title`/`description`/`dataKey`/`emptyHint`);
  adds an eye (`_actions`) column opening `PulseDetailDrawer` that shows the full row via
  `buildDetailFields`/`buildScopeLabel`. The `Knowledge Base` route renders through this generic panel.

> Note: the `KnowledgeBasePanel.jsx` wrapper, `App.jsx` routes, `AdminRoute.jsx`
> `requiredCapability`, and `sweeps_api.py` already landed in the Phase F commit (`06f942e`). This
> phase extracted the pure formatters and added the generic drill-down drawer + tests.

## H4 — Browser E2E of the AI admin console + CBAC

**File**: `carbon-frontend/e2e/journeys/journey-09-ai-console.spec.ts` (NEW). Run with
`npx playwright test --config e2e/playwright.config.ts journey-09-ai-console` (NOT the root cjs config).

- **9A** — anonymous → **401** on all 10 gated `/carbon-api/ai/pulse/*` read paths.
- **9B** — global admin → **200** on the 9 payload-returning panels (incl. `/sweeps/`).
- **9C** — plain branch data owner (no capability) → **403** — CBAC gating.
- **9D** — admin logs in and opens `/admin/ai` (Pulse Overview) then drills into
  `/admin/ai/knowledge` (Knowledge Base panel) with **no "Not authorized"** and no hard error.

**E2E lesson (fixed during this phase)**: Playwright gives each `test()` a **fresh browser context**
(isolated localStorage), so a UI login in one test does NOT persist into the next. The drill-down was
merged into a single test (login → navigate → drill) to keep one authenticated session. Also, the
E2E journey uses `serial` mode + one-time token acquisition in `beforeAll` to stay under the
5-logins/min throttle.

---

## Tests added

- `backend/ai/tests/test_consolidation_sweep.py` (NEW, 3): disabled-short-circuit, reflect+curate
  skill, cold-instance-no-candidates.
- `backend/ai/tests/test_cognition_scheduler.py` (+1 → 9): `test_heartbeat_writes_fresh_file`.
- `carbon-frontend/src/__tests__/PulseDataPanel.test.jsx` (NEW, 8): formatter unit tests (imports from
  `pulseFormat.js`, not `PulseDataPanel.jsx`, to avoid the @mui/x-data-grid CSS import failure under
  vitest `css:false`).
- `carbon-frontend/e2e/journeys/journey-09-ai-console.spec.ts` (NEW, 4).

## H5 — Gates (all green)

| Gate | Result |
|------|--------|
| `manage.py check` | 0 issues |
| `makemigrations --check --dry-run` | No changes detected |
| `pytest ai dq accounts` | **741 passed** |
| `npm test` (vitest) | **330 passed** |
| `npm run build` | ✅ (chunk-size warning pre-existing) |
| Playwright `journey-09-ai-console` | **4 passed** |

---

## Committed together (surgical staging)

Phase H shares the commit with the still-uncommitted Phase G work (live analytics grounding + DQ
write gate), since the user directive was "git all" but staging must remain surgical. Test artifacts
(`carbon-frontend/e2e/e2e-report/`, `e2e/e2e-results.json`) and `raw/*.xlsx` / `dataschema_uploads/` /
`mediafiles/` / secrets are excluded.
