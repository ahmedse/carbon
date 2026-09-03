# Definition of Done — the Universal Completion Gate
# Read by: ALL roles. A task is NOT done until every applicable box is checked.
# Master Architect rejects any TASK-RESULTS.md that skips this.

---

## The Gate (applies to every task)

A change is DONE only when ALL applicable items are true AND proven with terminal output.

### 1. Correct
- [ ] Does exactly what the task asked — no more (no scope creep), no less.
- [ ] Follows the relevant `shared/*` contract (api / data / security / config / design / logging).
- [ ] Frontend view: built ONLY after its Screen Spec (9 artifacts) is complete — `shared/frontend-ready.md`.
- [ ] Follows best practice, not just the local pattern (base-rules §0). Debt flagged, not copied.

### 2. Reuses, doesn't duplicate
- [ ] Checked `registry/` before creating anything. Reused/extended existing code where possible.
- [ ] No duplicate component/service/endpoint/model created.

### 3. Verified (terminal proof, not description)
- [ ] `./.ai-toolkit/scripts/verify.sh` relevant target passes (or warnings explained).
- [ ] AI pipeline change → `verify.sh intelligence` passes BOTH tiers (live tier when a key is present — see testing.md RULE 8).
- [ ] Domain check green: backend `./manage.sh test` / `manage.py check`; frontend `lint` + `build`.
- [ ] The actual behavior demonstrated (endpoint hit / UI state / command output pasted).

### 4. Tested
- [ ] New logic/endpoint has tests. Bug fix has a regression test (fails before, passes after).
- [ ] Calibration/honesty/grounding behavior has a deterministic regression test (gates even without a live key — testing.md RULE 8).
- [ ] Existing tests still green (nothing broken).

### 5. Safe
- [ ] No hardcoded secrets/config (verify.sh antipatterns green). Values from env.
- [ ] Auth + authorization correct on new endpoints (security.md).
- [ ] No naive datetimes, no swallowed exceptions, no `print()` in app code.

### 6. Clean
- [ ] No debug leftovers (stray console.log, commented-out code, temp files).
- [ ] Migrations included if models changed; no missing-migration warning.
- [ ] Dependencies added to the manifest (requirements.txt / package.json).

### 7. Captured
- [ ] Registry regenerated if structure changed (`scan.sh`).
- [ ] Bug fix → playbook entry added. Architectural decision → ADR.
- [ ] `TASK-RESULTS.md` written: files changed + verification output + issues + deviations.

---

## Not Done If…
- Verification output is missing or says "probably works".
- A frontend view was coded without a complete Screen Spec (`shared/frontend-ready.md`).
- Tests are missing for new logic or a bug fix.
- A file outside the task's declared scope was changed without noting it.
- An anti-pattern was introduced (verify.sh would fail).
- The registry/playbook/ADR wasn't updated when it should have been.

---

## Quick command
```bash
./.ai-toolkit/scripts/verify.sh full     # check + tests + lint + build + antipatterns
```
Paste the tail of this into TASK-RESULTS.md as your proof.
