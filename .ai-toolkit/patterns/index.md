# Universal Patterns Index

Promoted, project-agnostic lessons. Every agent reads relevant entries on activation.
Each pattern: **trap → correct practice → detectable?**. Stable ids `UP-NNNN`.

> Seeded from recurring lessons observed across turnkey (FastAPI) + gigacast/carbon (Django).
> Add new entries only via the promotion contract in `README.md`.

---

### UP-0001 — Naive datetimes cause silent time bugs
- **Trap:** `datetime.now()` / `datetime(2026,7,1)` produce naive timestamps → wrong ordering, off-by-timezone comparisons, DST corruption.
- **Correct:** Always timezone-aware UTC. Django → `django.utils.timezone.now()`. FastAPI/stdlib → `datetime.now(timezone.utc)`.
- **Seen in:** gigacast, carbon (Django), turnkey (FastAPI).
- **Detectable:** grep `datetime.now()` / `datetime.utcnow()` without tz.

### UP-0002 — `select_related()` on JSONField parents = massive slowdown
- **Trap:** Eager-joining rows that carry large JSONFields deserializes full JSON per row (observed ~75x slowdown on list endpoints).
- **Correct:** `select_related(None)` + `.defer(...)` the JSON columns on list/aggregate endpoints; annotate only what's needed.
- **Seen in:** gigacast, carbon.
- **Detectable:** grep `select_related(` near models with JSONField in list views.

### UP-0003 — Object identity generated at flush time, not construction
- **Trap:** Reading an auto-generated field (UUID/PK) right after constructing an ORM object returns None/stale — it's assigned on flush/insert.
- **Correct:** Flush/commit before reading generated ids; in batch paths, don't key on ids until after persistence.
- **Seen in:** turnkey (batch-predict).
- **Detectable:** review — hard to grep.

### UP-0004 — Background processes must fully detach stdin
- **Trap:** `nohup cmd &` leaves stdin attached → the terminal/session hangs forever.
- **Correct:** `setsid cmd >log 2>&1 </dev/null &` (or the project ops script `start`). Never run servers/watchers in a foreground session.
- **Seen in:** all projects (ops scripts encode this).
- **Detectable:** grep background invocations missing `</dev/null`.

### UP-0005 — In Docker, code is baked into the image
- **Trap:** Editing host files / `docker restart` does NOT change running container code → "fixed but still broken in prod."
- **Correct:** Hotfix = `docker cp` + restart + **verify** `docker exec … grep -c marker`. Proper fix = rebuild image via deploy script.
- **Seen in:** all deployed projects.
- **Detectable:** process/checklist (verify grep after deploy).

### UP-0006 — Hiding command output during conversation breaks trust
- **Trap:** Agent runs a gate command (tests, grep, migration check) and reports "ok" without showing the output. Master/user can't verify. Also: running `pytest tests/` unbounded hangs the session on async event loop contention.
- **Correct:** Always pipe output to a visible summary. Tests → `| tail -5`. Gates → `grep -c` with pass/fail. Per-directory runs with `timeout 15`. Never bury output behind "Large tool result written to file."
- **Seen in:** pulse (P1.1 session — test output hidden, full suite hung).
- **Detectable:** grep for `timeout 300 venv/bin/python -m pytest tests/ -q` without `| tail`.

### UP-0007 — Reordering the LLM system prompt kills the prefix cache (~30x cost)
- **Trap:** Mutating/reordering the stable system-prompt + tool-definitions prefix between calls invalidates DeepSeek's prefix cache → cache-miss ~$0.22/M instead of hit ~$0.007/M on every subsequent call.
- **Correct:** Keep a STABLE, long-lived prefix at the FRONT; append new context AFTER it; never rotate/reorder. Version the prefix, append-only during a session. Tier by complexity: V4-Flash for routine, V4-Pro for hard reasoning.
- **Seen in:** carbon (RULE_24/25/26 → shared/model-budgeting.md).
- **Detectable:** grep for mid-session system-prompt reassignment / prefix reorder.

### UP-0008 — `-o addopts=''` is the way to bypass pytest.ini xdist (not `-p`)
- **Trap:** `pytest.ini` sets `addopts = -n auto` (xdist). `-p no:xdist` is INVALID → pytest errors. After a schema change, stale per-worker test DBs (`test_*_gw0..7`) cause spurious "column does not exist" under `--reuse-db`.
- **Correct:** Neutralize pytest.ini addopts with `-o addopts=''`; drop the stale `test_*_gw*` DBs (or use `--create-db`). FK column idiom: a field named `parent` yields column `parent_id` and attribute `obj.parent_id` (Django).
- **Seen in:** carbon (Phase 19 — `AIMessage.parent` self-FK).
- **Detectable:** grep for `-p no:xdist` / `--reuse-db` + `-n auto` together.

---

*Source: ~/ai-toolkit/patterns/index.md — symlinked into every project*
