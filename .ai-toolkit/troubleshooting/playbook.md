# Playbook — Known Issues → Root Cause → Verified Fix

Search before debugging: `grep -i "<symptom>" .ai-toolkit/troubleshooting/playbook.md`
Append a new entry every time you confirm+fix a non-trivial bug (see `shared/debugging.md`).

**Entry format:**
```
### PB-NN — <short symptom>
- Symptom: <what you observe>
- Layer: backend | frontend | data | deploy | infra
- Root cause: <the real cause, confirmed>
- Fix: <the verified fix>
- Best practice note: <the RIGHT long-term fix, if the applied fix was a workaround>
- Regression guard: <test path / verify.sh check / N/A>
- First seen: YYYY-MM-DD
```

> NOTE: Some entries below describe **workarounds for existing tech debt**. Where the
> current codebase forces a workaround, the "Best practice note" states the RIGHT fix.
> Do the right thing — don't treat a workaround as the target design.

---

### PB-01 — Terminal hangs / command never returns
- Symptom: a command (often starting a server) hangs the session indefinitely.
- Layer: infra / dev-env
- Root cause: a background/long-lived process keeps stdin attached to the terminal PTY,
  so the shell never sees a clean command boundary.
- Fix: use the ops script (`./manage.sh start <svc>`) which fully detaches. For ad-hoc:
  `setsid <cmd> </dev/null >/tmp/x.log 2>&1 &` (the `</dev/null` is mandatory).
- Best practice note: services belong in a supervised process manager (systemd / compose),
  not started ad-hoc in an interactive shell.
- Regression guard: base-rules §2/§3; never run `runserver`/`npm run dev` raw.
- First seen: recurring.

### PB-02 — Code "deployed" but production still runs the old behavior
- Symptom: fixed a file, rsynced + restarted, prod unchanged. `grep` for the change in
  the container returns 0.
- Layer: deploy
- Root cause: this project BAKES code into the Docker image at `/app`; bind mounts don't
  cover the code tree, and `docker restart` doesn't re-pull host code.
- Fix (hotfix): `docker cp <hostfile> <container>:/app/<path>` → `docker restart` →
  verify `docker exec ... grep -c <marker> /app/<path>` > 0.
- Best practice note: the RIGHT fix is a CI/CD pipeline that rebuilds+redeploys the image
  on merge. `docker cp` is an emergency hotfix (lost on recreate), not a deploy method.
- Regression guard: deploy checklist in shared/config.md; verify-in-container step.
- First seen: 2026-07-27.

### PB-03 — Dashboard/stale data after source update
- Symptom: updated/deleted source data, dashboard/aggregates still show old values.
- Layer: backend / data
- Root cause: derived/cached copies of data not invalidated when source changes.
- Fix: clear ALL derived copies too, not just the source-of-truth table.
- Best practice note: compute derived values in the write pipeline with a single
  invalidation point, or cache with explicit invalidation.
- Regression guard: integration test asserting reset clears derived fields.
- First seen: recurring.

### PB-04 — API endpoint unexpectedly slow (seconds for a list)
- Symptom: a list/aggregate endpoint takes seconds.
- Layer: backend
- Root cause: `select_related()` pulls JSONField-bearing parent rows that get deserialized
  for every row (or an N+1 query in a loop).
- Fix: `select_related(None)` + `.defer()` the heavy JSON fields; annotate only needed
  values in the DB; verify query count in `./manage.sh shell`.
- Best practice note: measure before optimizing; keep list serializers lean by default.
- Regression guard: shared/data-layer.md query rules; a test asserting query count.
- First seen: recurring.

### PB-05 — Model predictions systematically biased (all high/low)
- Symptom: forecasts consistently above/below actuals during a regime shift.
- Layer: data / ML
- Root cause: online bias correction is a no-op because the active forecaster lacks the
  expected method (guarded by `hasattr`), or the residual window has no backfilled actuals.
- Fix: ensure the forecaster implements the correction hook AND actuals are backfilled for
  the residual window; confirm the correction actually applies (peak delta == expected).
- Best practice note: a capability gated by `hasattr` should fail loud in dev/test, not
  silently no-op. Add an explicit capability check + test.
- Regression guard: unit test: correction ON vs OFF produces the expected delta.
- First seen: 2026-07.

### PB-06 — Naive-datetime / timezone bugs (off-by-hours, flaky time tests)
- Symptom: timestamps off by the UTC offset; tests that pass/fail by time of day.
- Layer: backend / data
- Root cause: `datetime.now()` / `datetime.utcnow()` producing naive datetimes.
- Fix: use `django.utils.timezone.now()`; store UTC-aware; convert at presentation only.
- Best practice note: THIS is the right way regardless of what existing code does — the
  codebase still has naive-datetime debt (verify.sh flags it); fix on touch.
- Regression guard: `verify.sh antipatterns` greps for naive datetime.
- First seen: recurring (existing debt).
