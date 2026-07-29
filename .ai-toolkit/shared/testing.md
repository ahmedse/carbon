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

## Verification Gate (tests are part of "done")

```bash
# Backend tests must pass before reporting done
./manage.sh test 2>&1 | tail -20

# Full gate (check + lint + anti-patterns)
./.ai-toolkit/scripts/verify.sh

# Critical E2E (when a user journey changed)
cd frontend && npm run sim 2>&1 | tail -30
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
