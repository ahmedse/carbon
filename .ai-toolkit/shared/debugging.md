# Debugging Methodology — and the "Never Fix the Same Bug Twice" Loop
# Read by: Debugger/Fixer (primary), all workers when something breaks.
# Purpose: diagnose from evidence, fix the root cause, and make the bug impossible to recur.

---

## The Core Principle

**Diagnosis before fix. Root cause before patch. Regression test before "done."**

A fix without a confirmed root cause is a guess — guesses create new bugs.
A fix without a regression test is temporary — the bug will silently return.
A recurring bug that isn't captured in the playbook wastes tokens re-diagnosing it.

---

## The Debugging Loop (follow in order)

```
1. CHECK KNOWN ISSUES FIRST
   - grep the troubleshooting playbook:  grep -i "<symptom>" .ai-toolkit/troubleshooting/playbook.md
   - read the project gotchas file (project.config.md → GOTCHAS_FILE)
   - If found → apply the documented fix. STOP here. (This is the whole point.)

2. REPRODUCE
   - Get a deterministic repro. Exact steps, exact input, exact environment.
   - Can't reproduce → you can't confirm a fix. Keep gathering evidence.

3. ISOLATE (bisect the surface)
   - Local vs container? Which layer (frontend / API / service / DB / deploy)?
   - Trace the call chain backward from the symptom to where the wrong value is born.
   - Binary-search the change history / the code path — halve the suspect area each step.

4. HYPOTHESIZE (one at a time)
   - State it explicitly: "X fails because Y does Z instead of A."
   - Predict what you'd see if the hypothesis is true.

5. CONFIRM with evidence (don't fix yet)
   - Add a diagnostic (log/print/shell check), reproduce, verify the prediction.
   - Backend: `./manage.sh shell` to inspect real values. Frontend: console/network tab.
   - Container: `docker exec ... ` to read the ACTUAL running code/values.

6. REGRESSION TEST FIRST (red)
   - Write a failing test that captures the bug (see shared/testing.md RULE 1).
   - This proves you understand the bug AND locks it out forever.

7. FIX the confirmed root cause — minimally (green)
   - Change ONLY what the root cause requires. No refactoring, no drive-by "improvements".
   - The regression test now passes.

8. VERIFY end-to-end
   - Run the gate: ./.ai-toolkit/scripts/verify.sh  +  ./manage.sh test
   - Reproduce the original symptom → confirm it's gone (before/after evidence).

9. CAPTURE so it never recurs
   - Add/append an entry to .ai-toolkit/troubleshooting/playbook.md (symptom → cause → fix).
   - If it was architectural → write an ADR (decisions/).
   - If it's a project-specific gotcha → note it in the GOTCHAS_FILE.
```

---

## The "Never Fix Twice" Triad

Every non-trivial bug fix produces THREE artifacts. This is what kills recurring problems:

| Artifact | Where | Prevents |
|----------|-------|----------|
| **Regression test** | `<app>/tests/` | The bug silently returning in code |
| **Playbook entry** | `troubleshooting/playbook.md` | Re-diagnosing the same symptom |
| **Anti-pattern check** (if pattern-detectable) | `scripts/verify.sh` | The whole CLASS of bug reappearing |

If a bug could recur across the codebase (e.g. "naive datetime", "raw fetch"),
add a grep for it to `verify.sh` so the machine catches it, not a human.

---

## Common Root-Cause Classes (check these fast)

| Symptom | Likely class | First check |
|---------|-------------|-------------|
| Works locally, fails in prod | Code not in container / env diff | `docker exec ... grep -c <marker> /app/...` |
| Fixed but still broken in prod | Stale container (baked image) | Verify code IS in the container |
| Stale data after update | Derived/backfilled copy not cleared | Trace which layer the UI reads |
| Systematic model bias | Online correction off / missing data | `hasattr(forecaster,'set_inference_config')` + actuals present |
| Endpoint slow | N+1 / select_related on JSON parent | Count queries in shell |
| Intermittent / flaky | Time/timezone/race/ordering | Naive datetime? Test isolation? |
| Silent no-op | Guarded by `hasattr`/feature flag/try-except | Is the guard passing? Is the exception swallowed? |

(Expand these into full entries in the playbook as you confirm them.)

---

## Debugging Discipline (what NOT to do)

- NEVER fix without confirming the root cause (no shotgun/guess fixes).
- NEVER fix multiple unrelated bugs in one change — one bug, one fix, one test.
- NEVER refactor while fixing — it hides what actually fixed it.
- NEVER swallow exceptions to "make the error go away" — surface and handle them.
- NEVER trust that the container runs the code you edited on the host — verify.
- NEVER mark done without before/after evidence + a passing regression test.

---

## Output (for TASK-RESULTS.md)

```markdown
## [Date] Debugger/Fixer — [Bug]
### Root Cause
[exact: what was wrong and why]
### Regression Test
- <app>/tests/test_x.py::test_y — fails before fix, passes after
### Fix
- path:line — [minimal change]
### Before/After Evidence
Before: [repro output showing bug]
After:  [output showing fixed] + [./manage.sh test tail]
### Captured
- Playbook entry: troubleshooting/playbook.md #NN
- ADR (if architectural): decisions/00NN  | or NONE
- verify.sh check added (if class-detectable): [yes/no]
```
