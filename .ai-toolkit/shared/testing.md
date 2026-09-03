# Testing Strategy — What, How, and When to Test
# Read by: Backend Worker, Frontend Worker, Data/ML Worker, Debugger/Fixer.
# Purpose: consistent, high-value tests. Every bug fix ships with a regression test.

---

## The Test Pyramid (spend effort here)

```
        ╱╲        E2E (few)          — Playwright: critical user journeys only
       ╱  ╲       Integration (some) — API endpoints, service + DB together
      ╱────╲      Unit (many)        — pure logic, services, serializers, utils
```

- **Many** fast unit tests (logic, edge cases, no I/O).
- **Some** integration tests (endpoint → service → DB round-trips).
- **Few** E2E tests (only the highest-value flows — they're slow and brittle).
- NEVER invert the pyramid (all-E2E is slow, flaky, expensive).

---

## This Project's Test Stack (see project.config.md for exact commands)

| Layer | Tool | Location | Run |
|-------|------|----------|-----|
| Backend unit + integration | Django `TestCase` + DRF `APIClient` | `<app>/tests/test_*.py` | `./manage.sh test` |
| Frontend E2E | Playwright | `frontend/e2e/` | `npm run sim` |
| Lint (static) | eslint / `manage.py check` | — | `./.ai-toolkit/scripts/verify.sh` |

Run a single backend test: `./manage.sh test aihub.tests.test_prediction_views`

---

## RULE 1 — Every Bug Fix Ships a Regression Test (non-negotiable)

**This is the mechanism that stops repeated problems.** A fixed bug WITHOUT a test
silently comes back. A fixed bug WITH a test can never regress unnoticed.

The bug-fix order is ALWAYS:
```
1. Reproduce the bug
2. Write a FAILING test that captures it (red)
3. Fix the code until the test passes (green)
4. The test stays forever — the bug can't return
```
See `shared/debugging.md` for the full loop.

---

## RULE 2 — What to Test at Each Layer

### Backend unit (services, logic, serializers)
- Business logic branches (happy path + each edge case).
- Boundary conditions: empty input, null, zero, max, timezone edges.
- Serializer validation: required fields, invalid values rejected.
- Pure functions: given input → expected output.

### Backend integration (endpoints)
- Each endpoint: auth required (401 without token), correct status codes.
- Authorization: user A cannot access user B's data (403/404).
- Response shape matches `shared/api-contract.md` (envelope, fields).
- DB side effects: the right rows created/updated/deleted.
- Idempotency: calling twice does the right thing.

### Data/ML
- Feature engineering: new columns present, correct values on known input.
- No data leakage: train/val split respects time order.
- Model eval: metric computed correctly on a fixture.
- NEVER assert exact float equality — use tolerances (`assertAlmostEqual`).

### Frontend E2E (Playwright — critical journeys only)
- Login → key page loads → primary action works.
- The money paths (the flows that, if broken, break the product).
- NOT every component — that's what component/unit tests are for.

---

## RULE 3 — Test Quality

- **One behavior per test.** Name says what it verifies: `test_backfill_clears_stale_actual`.
- **Arrange–Act–Assert** structure. Setup in `setUp`, one action, clear assertions.
- **Deterministic.** No reliance on real time, network, or random without seeding/mocking.
  Use `timezone.now()` mocking / fixed timestamps.
- **Isolated.** Each test sets up its own data; no cross-test dependencies or ordering.
- **Fast.** Mock external services (weather API, LLM, reporting) — never hit real endpoints in tests.
- **Meaningful asserts.** Assert the actual outcome, not just "no exception."

---

## RULE 4 — What NOT to Test

- Framework internals (Django ORM itself, MUI rendering) — trust the library.
- Trivial getters/setters with no logic.
- Third-party code.
- Don't chase 100% coverage — cover the RISK, not the lines. Critical paths first.

---

## RULE 5 — Fixtures & Test Data

- Build minimal fixtures in `setUp` — only the fields the test needs.
- Reusable factory helpers for common objects (a `make_prediction(**overrides)` helper).
- NEVER depend on production data or a specific DB state.
- Timezone-aware datetimes in fixtures always (this project: UTC-aware).

---

## RULE 6 — When Tests Are Required

| Change | Test required? |
|--------|----------------|
| New service / business logic | YES — unit tests for the logic |
| New / changed endpoint | YES — integration test (auth + shape + side effects) |
| Bug fix | YES — regression test that fails before, passes after |
| New feature column (ML) | YES — presence + value on known input |
| Refactor (no behavior change) | Existing tests must stay green (that's the safety net) |
| Pure styling / copy change | No (but don't break existing E2E) |

---

## RULE 7 — Test Partitioning (MANDATORY — protects the dev laptop)

**Root cause this rule fixes:** full-suite `pytest` + `pytest-xdist -n auto` spawns
multiple parallel Postgres test DBs (`test_carbon_dev`, `test_carbon_dev_1`,
`test_carbon_dev_2`, …) and saturates CPU/RAM — the laptop hangs. The xdist flags
have been **removed from `backend/pytest.ini`** and MUST NOT be re-added.

### Backend — always per-app, never full-suite

```bash
cd /home/ahmed/aast/carbon/backend
PY=/home/ahmed/aast/carbon/.venv/bin/python
# ONE app at a time (this is the unit of work):
$PY -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider
$PY -m pytest catalog -q --maxfail=5 --disable-warnings -p no:cacheprovider
$PY -m pytest integrations -q --maxfail=5 --disable-warnings -p no:cacheprovider
$PY -m pytest accounts -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

- **NEVER** `pytest` with no args (runs the whole suite + one giant test DB).
- **NEVER** `-n auto`, `--dist loadscope`, or any `pytest-xdist` flag.
- A phase may run a **small bounded group** (e.g. `pytest ai catalog -q`) but
  never more than 2 apps in one invocation.
- Prefer the app you actually changed, plus its direct dependents only.

### Frontend — targeted vitest, one build per phase

```bash
cd /home/ahmed/aast/carbon/carbon-frontend
# ONE spec file (or a tiny glob), never the whole suite:
npx vitest run src/__tests__/AITaskPanel.test.jsx
# Build once per phase (not per file):
npm run build
```

- **NEVER** `npx vitest run` with no path (whole suite = laptop hang).
- **NEVER** `vitest --run --coverage` during routine work.
- **vitest + `@mui/x-data-grid` CSS import**: a test that (transitively) imports the grid fails with `Failed to parse source … Unexpected token`. Fix in `vitest.config.js` — inline the package under the `test` key (NOT `test.deps`): `test: { server: { deps: { inline: ['@mui/x-data-grid'] } } }`. Prefer importing pure helpers (`pulseFormat.js`) over `.jsx` components that pull the grid.

### E2E — only when a journey changed, one spec at a time

```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npx playwright test e2e/journeys/journey-11-ai-coworker-dq.spec.ts
```

### Stale test-DB cleanup (run only if you see leftover `test_carbon*` DBs)

```bash
cd /home/ahmed/aast/carbon
export PGPASSWORD=securepassword123 PAGER=cat
for db in $(psql -X -h localhost -U carbon_user -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datname LIKE 'test_carbon%';"); do
  psql -X -h localhost -U carbon_user -d postgres -c "DROP DATABASE \"$db\";"
done
```

---

## RULE 8 — Pulse Intelligence Validation Gate (AI pipeline changes)

**Root cause this rule fixes:** structural tests (stubbed LLM) prove the
pipeline is *wired*, but they cannot prove it is *intelligent* — calibrated,
honest, grounded, durable. Two real calibration bugs shipped past stub-only
tests and were only caught by a LIVE turn:
1. the clarify/disambiguate intent short-circuit returns *before* any
draft/critic witness, so a label derived only from `ledger.draft.confidence`
dropped to `""`/`False` (the UI rendered it as a plain, confident-looking answer);
2. the `ungrounded_claim` FLAG was misread as a rejection — but the critic also
attaches it to `pass` verdicts for general-knowledge it cannot ground; only a
`veto` verdict is a real rejection.

Any change touching the AI reasoning/calibration/honesty/grounding surface
(confidence label, honest-uncertainty, critic verdict/flags, intent resolver,
draft synthesis, anti-hallucination gate, or the chat dispatch path) MUST run:

```bash
./.ai-toolkit/scripts/verify.sh intelligence
```

The gate has two tiers, run in order (see `scripts/verify-intelligence.sh`):

1. **Deterministic (stubbed LLM)** — always runs, no key required. Proves the
   *plumbing* and calibration *logic*: `test_confidence_surface.py`,
   `test_intent_resolver.py`, `test_reason_lane.py`, `test_gap1_fallback.py`,
   `test_emissions_grounding.py`, `test_report_draft.py`,
   `test_planner_reasoning_skills.py`, `test_chat_wiring.py`,
   `test_intelligence.py`. Fails hard on any regression.
2. **LIVE (real LLM, no stubs)** — runs when `LLM_API_KEY` is present (env or
   `backend/.env`). Drives real turns through the six-witness pipeline with the
   configured provider (Poe gpt-4o) and asserts on *behavior*:
   `test_intelligence_live.py` + `test_live_llm_activation.py` — calibration
   (label matches the turn's self-assurance), honesty (a gap turn admits
   uncertainty and never surfaces a `high`-confidence bluff), grounding (stays
   in-domain), durable writes (real `TurnLedgerRow` + `LLMCallLog` in Postgres),
   anti-hallucination (a tool-less turn claims no mutation).

Rules:
- The deterministic tier alone is NOT a sufficient "done" for an AI-pipeline
  change when a live key is available — the LIVE tier is the *intelligence* proof.
- Each live test issues exactly ONE turn (respects `LLM_DAILY_BUDGET_USD`).
- Any new calibration/honesty/grounding behavior ships WITH a deterministic
  regression test (so it gates even when no live key is present).

---

## Verification Gate (tests are part of "done")

```bash
# Backend: per-app only (see RULE 7 — never full suite, never xdist)
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest <changed-app> -q --maxfail=5 --disable-warnings -p no:cacheprovider

# Full gate (check + lint + anti-patterns)
./.ai-toolkit/scripts/verify.sh

# AI pipeline change → intelligence gate (deterministic + LIVE, see RULE 8)
./.ai-toolkit/scripts/verify.sh intelligence

# Frontend: targeted vitest + one build (see RULE 7)
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run <specific-spec-file>
npm run build
```
A change with failing or missing required tests is NOT complete.

---

## Anti-Patterns (reject in review)

- Bug fix with no regression test
- Test that asserts "no exception thrown" and nothing else
- Tests that hit real external services (flaky, slow)
- Exact float-equality asserts on model metrics
- Tests coupled to each other's ordering / shared mutable state
- Inverted pyramid (E2E for what should be a unit test)
- Chasing coverage % instead of covering real risk
- Full-suite `pytest` with no args (one giant test DB → laptop hang)
- `pytest-xdist` / `-n auto` / `--dist loadscope` (parallel test DBs → laptop hang)
- `npx vitest run` with no path (whole suite → laptop hang)
