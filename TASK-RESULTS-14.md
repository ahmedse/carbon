# TASK-RESULTS-14 — QA Re-validation: Journey-11 after defect fixes (F1 / A1 / B5)

Date: 2026-08-18 · Role: QA/Validator · Model: DeepSeek-V3 · Phase: Phase 14 · Source: `TASKS.md` §Phase 14, `e2e/journeys/journey-11-ai-coworker-dq.spec.ts`, `e2e/journeys/journey-10-ai-workspace.spec.ts`

---

## Executive Summary

**Verdict: FAILED** — B5 is NOT fixed (1× P1), plus 1× P2 (missing B5 unit coverage), 1× P2 (new A4 hover failure), 16× P2 (pre-existing stale unit specs).

Of the three in-scope defects this phase was meant to confirm as fixed:

- **F1 (edit + regenerate → 500)** — ✅ VALIDATED. Journey-10 = 29/29 PASS.
- **A1 (newChat list-load race)** — ✅ VALIDATED. Part A now progresses past the `newChat` helper through A2/A3; it fails later at A4 on an unrelated hover issue.
- **B5 (nl_rule_test auto-send → "Pass rate" card)** — ❌ NOT VALIDATED. The `AITaskTransferContext.jsx` auto-send block is present in source, but the E2E "Pass rate" card still never renders after "Test live" (150s timeout), and the claimed 2 new unit tests are **absent** (file has 8, not 10).

### Issue counts by severity

| Severity | Count | Notes |
|----------|-------|-------|
| P0 | 0 | — |
| P1 | 1 | B5 "Pass rate" card never renders after "Test live" |
| P2 | 18 | 16 stale unit specs + 1 missing B5 unit coverage + 1 A4 hover failure |

---

## Task Results

| # | Gate | Command | Expected | Actual | Result |
|---|------|---------|----------|--------|--------|
| 0 | Preconditions | `./manage.sh status` + curl health | both 200 | 200 / 200 (backend :8009, frontend :5179) | ✅ |
| 1 | Unit — B5 | `npx vitest run src/__tests__/AITaskTransferContext.test.jsx` | 10 passed | **8 passed** | ❌ |
| 2 | Unit — full | `npm test -- --run` | all green (~400+) | **16 failed / 430 passed (446)** | ❌ |
| 3 | E2E — Journey-11 | `npx playwright test … journey-11-ai-coworker-dq` | ALL PASS | **2 failed / 1 passed** | ❌ |
| 4 | E2E — Journey-10 | `npx playwright test … journey-10-ai-workspace` | 29/29 PASS | **29/29 PASS** | ✅ |

---

## Files Changed

**NONE.** This was a pure validation pass — no code edits, no commits. (`TASK-RESULTS-14.md` is the only new artifact.)

---

## Verification Output

### Preconditions
```
Backend API:  RUNNING (PID: 1993, Port: 8009)
Frontend:     RUNNING (PID: 2075, Port: 5179)
PostgreSQL:   RUNNING
--- backend health ---  200
--- frontend health --- 200
```

### Gate 1 — AITaskTransferContext unit test
```
 RUN  v4.1.10 /home/ahmed/aast/carbon/carbon-frontend
 Test Files  1 passed (1)
      Tests  8 passed (8)
   Duration  2.09s
```
⚠️ Spec claimed 10 tests (2 new `nl_rule_test` auto-send tests). File contains only 8 `it()` blocks and **zero** `nl_rule_test` coverage.

### Gate 2 — full unit suite
```
 Test Files  5 failed | 20 passed (25)
      Tests  16 failed | 430 passed (446)
   Duration  8.92s
```
Failing files (all 16 failures are stale pre-Sprint-18 specs, the F2 finding):
- `AIMessageBubble.feedback.test.jsx` (5 failed)
- `AIMessageBubble.transparency.test.jsx` (1 failed)
- `AIArtifacts.test.jsx` (2 failed)
- `AISharedThreads.test.jsx` (4 failed)
- `AIWorkspace.shell.test.jsx` (4 failed)

### Gate 3 — Journey-11 E2E
```
Running 3 tests using 1 worker
  ✘  Part A … A4: feedback Accept on latest assistant (10.0m — timeout)
  ✘  Part B … B5: NL rule test → Execute Mode → Save Rule (3.5m — "Pass rate" not found)
  ✓  Part C … RBAC — admin console gate + copilot availability (viewer) (15.9s)

  2 failed / 1 passed (13.9m)
```

### Gate 4 — Journey-10 E2E (F1 regression guard)
```
Running 29 tests using 1 worker
  ✓ … ✓ (all 29)
  29 passed (1.5m)
```

---

## Deviations

- **B5 unit coverage absent (spec drift).** `TASKS.md` Phase 14 states "2 new unit tests added in `AITaskTransferContext.test.jsx` (10 total, all passing)". The actual file has **8 tests** and no `nl_rule_test` case. The B5 source fix (`if (type === 'nl_rule_test' && normalizedPayload.nl) sendMessage(...)`) is present at `AITaskTransferContext.jsx:149`, but it is **untested at the unit layer**.
- **A4 failure is new and out of the F1/A1/B5 scope.** The dataowner test now reaches A4 (proving A1's `newChat` race is fixed), then fails on an unrelated hover/overlay defect.

---

## Issues Found

| ID | Severity | Symptom | Repro | Owner |
|----|----------|---------|-------|-------|
| R14-1 (B5) | **P1** | "Pass rate" card never renders after clicking "Test live" on a DQ suggestion | `journey-11` Part B → B4 accept → B5: `navigateTo /catalog/tables/3` → `Suggest Rules` → send "Suggest a rule that rejects rows where fuel liters is negative." → click `Test live` → `expect(getByText(/Pass rate/i).first()).toBeVisible({timeout:150000})` times out (element not found) at spec line 250 | debugger-fixer (likely `nl` resolves empty → no auto-send → no `nl_rule_test` turn; or backend returns no `pass_rate` in the `nl_rule_test` metadata) |
| R14-2 (B5) | P2 | B5 regression coverage missing — 8 tests not 10, zero `nl_rule_test` cases | `npx vitest run src/__tests__/AITaskTransferContext.test.jsx` → 8 passed | frontend-worker (add the 2 claimed `nl_rule_test` auto-send unit tests) |
| R14-3 (A4) | P2 | `Accept response` button `.hover()` blocked — `<div class="MuiBox-root css-1v62va1">` intercepts pointer events, 600s timeout | `journey-11` Part A → A4: `page.getByRole('button', { name: 'Accept response' }).last().hover()` at spec line 144 → 545 retries, overlay intercepts | frontend-worker (z-index/overlay obscuring the message hover toolbar) or test-owner (locator fragility) |
| R14-4 (F2) | P2 | 16 stale unit specs still failing (pre-existing Sprint-18 finding, out of scope) | `npm test -- --run` → 16 failed across `AIMessageBubble.feedback/transparency`, `AIArtifacts`, `AISharedThreads`, `AIWorkspace.shell` | frontend-worker (already tracked as F2 from Sprint-18 Phase A) |

---

## Conclusion

- **F1** is confirmed fixed (Journey-10 29/29).
- **A1** is confirmed fixed (Part A clears `newChat` and reaches A4).
- **B5** is **NOT** fixed: the E2E "Pass rate" card still fails to render, and the promised unit coverage is missing. Per the Phase 14 "Notes for the Master", the leading hypothesis is a suggestion whose `nl` resolves empty (fallback `definition?.name`) so the `nl_rule_test` auto-send never fires — producing no `NLRuleTestCard`. This is recorded for the Debugger/Fixer; **no code was changed** (RULE_11).

---

# ═══ RE-VALIDATION RUN — 2026-08-23 ═══

Date: 2026-08-23 · Role: QA/Validator · Phase: Phase 14 (re-run) · Source: `TASKS.md` §Phase 14

## Executive Summary

**Verdict: FAILED (not signed off).** The four required test gates could **not be executed** in this session — no terminal/command-execution tool is available — so no fresh runtime evidence could be produced. Static (Layer 1) verification confirms all three in-scope fixes are **present in source**, but two defects remain that block sign-off:

1. **B5 unit coverage is absent.** Spec claims "2 new unit tests (10 total)"; the file actually has **15 tests and zero `nl_rule_test` auto-send cases** (RULE_11 regression gap).
2. **The B5 fix has a data-flow fragility** that matches the prior E2E failure: `nl = suggestion?.prompt || definition?.name || name || ''` can resolve empty, so the `nl_rule_test` auto-send never fires and the "Pass rate" card never renders.

The prior run (above, 2026-08-18) reported **FAILED** with B5 still broken at E2E and the same missing coverage. Nothing in the current source contradicts that; the B5 root cause is still present.

### Issue counts by severity

| Severity | Count | Notes |
|----------|-------|-------|
| P0 | 0 | — |
| P1 | 1 | R14-5 — B5 `nl`-resolution fragility (root cause of "Pass rate" never rendering) |
| P2 | 2 | R14-6 missing B5 coverage · R14-7 spec drift (10 vs 15 tests) |
| Env | 1 | R14-8 — terminal execution unavailable (blocker, not a product defect) |

## Task Results

| # | Gate | Command | Expected | Actual | Result |
|---|------|---------|----------|--------|--------|
| 0 | Preconditions | `./manage.sh status` + curl health | both 200 | Services RUNNING (`./manage.sh start` exited 0; backend :8009, frontend :5179). HTTP not re-checked (no exec). | ⚠️ |
| 1 | Unit — B5 | `npx vitest run src/__tests__/AITaskTransferContext.test.jsx` | 10 passed | **NOT RUN** (no exec). Static: 15 `it()` blocks, 0 `nl_rule_test`. | ❌ |
| 2 | Unit — full | `npm test -- --run` | all green | **NOT RUN** (no exec). | ❌ |
| 3 | E2E — Journey-11 | `npx playwright test … journey-11-ai-coworker-dq` | ALL PASS | **NOT RUN** (no exec). | ❌ |
| 4 | E2E — Journey-10 | `npx playwright test … journey-10-ai-workspace` | 29/29 PASS | **NOT RUN** (no exec). Last known: 29/29 (08-18). | ❌ |

## Files Changed

**NONE.** Pure validation — no code edits, no commits. (This appended re-validation section is the only artifact.)

## Verification Output

### Structural verification (Layer 1 — static, no execution)
- **F1** ✅ — `backend/ai/protocol.py:94` `current_view: str = ""` default present; `to_prompt_prefix` guards `if self.current_view`.
- **A1** ✅ — `journey-11` `newChat` helper uses `getByRole('button', { name: 'New chat' }).first()` + `toBeVisible({ timeout: 15_000 })`.
- **B5 (source)** ✅ — `AITaskTransferContext.jsx:164` `if (type === 'nl_rule_test' && normalizedPayload.nl) sendMessage(...)`.
- **Diagnostics** ✅ — `get_errors` on `AITaskTransferContext.jsx`, `AITaskTransferContext.test.jsx`, `journey-11-ai-coworker-dq.spec.ts` → all "No errors found".

### Gate commands — NOT EXECUTED (no terminal tool in this session)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npx vitest run src/__tests__/AITaskTransferContext.test.jsx   # expected 10 passed
npm test -- --run                                             # expected all green
npx playwright test --config e2e/playwright.config.ts journey-11-ai-coworker-dq   # expected ALL PASS
npx playwright test --config e2e/playwright.config.ts journey-10-ai-workspace     # expected 29/29
```
`terminal_last_command` shows only `./manage.sh start`; no run/execute tool is available, so these could not be re-run.

## Deviations

- **B5 unit coverage absent (spec drift).** Spec claims 2 new `nl_rule_test` unit tests (10 total). Actual: **15 tests** (grep: 15 `it()` blocks) and **zero `nl_rule_test` auto-send cases**.
- **Terminal execution unavailable** — gates not re-run; environment limitation, not a product defect.

## Issues Found

| ID | Severity | Symptom | Repro | Owner |
|----|----------|---------|-------|-------|
| R14-5 (B5) | P1 | "Pass rate" card never renders — `nl` can resolve empty so the auto-send never fires | `AIConversationView.jsx:459` `handleTestLive`: `nl = suggestion?.prompt || suggestion?.definition?.name || suggestion?.name || ''`; empty → `AITaskTransferContext.jsx:164` skips `sendMessage` → no `nl_rule_test` turn → no `NLRuleTestCard`. Matches 08-18 E2E failure + task "Notes for the Master" hypothesis. Runtime re-confirmation blocked (no exec). | frontend-worker (or backend-worker if `dq_suggest` omits `prompt`) |
| R14-6 (B5) | P2 | B5 regression coverage missing — 15 tests, zero `nl_rule_test` auto-send cases (RULE_11) | `src/__tests__/AITaskTransferContext.test.jsx` — none of the 15 `it()` blocks exercise the `nl_rule_test` auto-send | frontend-worker |
| R14-7 | P2 | Spec drift — "10 tests" vs actual 15 (Phase 16 resume tests landed after the 08-18 report) | static grep of the file shows 15 `it()` blocks | master-architect (spec) |
| R14-8 | — | Blocker: terminal/command execution unavailable → 4 gates not re-run; no fresh runtime evidence | n/a (environment) | n/a |

## Verdict

**FAILED (not signed off).** The F1/A1/B5 source fixes are present, but (a) the four required test gates could not be executed in this session, and (b) the B5 fix still lacks regression coverage and carries a data-flow fragility consistent with the prior E2E failure. Hand to Debugger/Fixer (R14-5) and frontend-worker (R14-6) before re-validating.
