# Incident Runbook — Production Is Broken
# Read by: DevOps Worker, Debugger/Fixer, Master Architect.
# Purpose: a calm, consistent order of operations when prod is down or degraded.
# Panic causes destructive shortcuts. Follow the order.

---

## Priority Order: STABILIZE → DIAGNOSE → FIX → PREVENT

Restore service first. Root-cause second. Never chase the perfect fix while users are down.

---

## Step 0 — Assess (30 seconds)
```bash
./manage.sh status                          # what's up/down
docker compose ps                           # container states (prod)
docker logs <PROD_CONTAINER> --tail 50      # last errors
curl -s -o /dev/null -w "%{http_code}" http://localhost:<PORT>/api/   # is it responding?
```
Classify: total outage | degraded | single feature broken. Note the blast radius.

---

## Step 1 — Stabilize (restore service)
Pick the LEAST destructive action that restores service:

| Symptom | First stabilizing action |
|---------|--------------------------|
| Container crashed/looping | `docker restart <PROD_CONTAINER>` → watch logs |
| Bad deploy just shipped | ROLL BACK to last good image/commit (don't hotfix forward under pressure) |
| Port stuck / orphan proc | `./manage.sh clean-ports` then restart via ops script |
| DB connection errors | check DB up + creds/env; do NOT run destructive DB commands |
| One endpoint 500s | leave the rest up; isolate the failing path |

- Rollback > forward-fix when users are down. A known-good old version beats an unproven new one.
- Do NOT run migrations, `reset`, `rm -rf`, or DB DELETEs as a panic move.

---

## Step 2 — Verify Stabilization
```bash
./manage.sh status
docker logs <PROD_CONTAINER> --tail 20      # errors stopped?
curl ... /api/                              # responding 200?
```
Confirm users are served BEFORE you start deep diagnosis.

---

## Step 3 — Diagnose (now that it's stable)
- Follow `shared/debugging.md`. Check `troubleshooting/playbook.md` for a known match FIRST.
- Confirm what's actually running in prod (baked image!):
  `docker exec <PROD_CONTAINER> grep -c <marker> /app/<path>`
- Reproduce in a safe environment, not by poking prod.

---

## Step 4 — Fix (properly)
- Apply the real fix with a regression test (never-fix-twice triad).
- Deploy via the proper path (rebuild image). `docker cp` hotfix ONLY if truly urgent, and
  follow up with a proper rebuild (it's lost on recreate). See shared/config.md deploy checklist.
- Verify in-container after deploy.

---

## Step 5 — Prevent (post-incident)
- Playbook entry: symptom → cause → fix (so it's never re-diagnosed).
- If class-detectable → add a `verify.sh` check.
- If a deploy/process gap caused it → ADR + fix the process.
- Note it in the GOTCHAS_FILE if project-specific.

---

## Hard Don'ts During an Incident
- ❌ `rm -rf`, `git reset --hard`, `docker compose down -v` (volume wipe), DB `DELETE`/`DROP`
- ❌ Editing prod files ad-hoc without recording what changed
- ❌ Forward-fixing an unproven change instead of rolling back
- ❌ Touching an unrelated stack on the same host (see project.config.md → PROD_DO_NOT_TOUCH)
- ❌ Silencing the alert/log instead of fixing the cause
- ❌ Making changes without a way to undo them

---

## Communication (if others are affected)
- State: what's impacted, since when, current status, ETA if known.
- Update on stabilization, then on resolution. Facts, not speculation.
