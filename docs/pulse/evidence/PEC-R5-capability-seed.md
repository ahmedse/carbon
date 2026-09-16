# PEC-R5 — Seed live Capability registry

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Brand:** `DJANGO_BRAND=nibras`  
**Constraint:** no `./manage.sh start|stop`; no PostgreSQL restart

## Command

```bash
cd backend
DJANGO_BRAND=nibras ../.venv/bin/python manage.py seed_nibras_processes
```

Uses pack `domain_packs/nibras` → upserts durable `Capability` rows + publishes lifecycle `ProcessDefinition`s (idempotent).

## Bug fixed (empty API despite rows)

`seed_nibras_processes` previously set `Capability.app_identifier = instance_id` (`nibras`).  
`scope_ai_queryset` filters by `resolve_default_app_identifier()` → **`people`** for Nibras brand.

Mismatch → `GET /carbon-api/ai/catalog/capabilities/` returned `[]` while DB had rows.

**Fix:** seed sets `app_identifier = resolve_default_app_identifier()` (same contract as `seed_nibras_knowledge --app people`).

## Before / after

| Metric | Before | After |
|--------|-------:|------:|
| DB `Capability` count | 20 | **31** |
| Distinct `app_identifier` | `nibras` | **`people`** |
| `scope_ai_queryset` (superuser) | 0 | **31** |
| `GET …/capabilities/` HTTP | 200 | **200** |
| `GET …/capabilities/` array length | **0** | **31** |
| Seed 2nd run | — | 0 created, 31 updated (idempotent) |
| Processes active | 3 | **5** (+ gosi_wps, onboarding) |

First seed pass (before app fix): `11 created, 20 updated` (GOSI/onboarding caps).  
Second pass (after app fix): `0 created, 31 updated` → all rows now `people`.

## HTTP proof

```bash
# Mint JWT
DJANGO_BRAND=nibras python manage.py shell -c \
  "from django.contrib.auth import get_user_model; \
   from rest_framework_simplejwt.tokens import RefreshToken; \
   u=get_user_model().objects.filter(is_superuser=True).first(); \
   print(RefreshToken.for_user(u).access_token)"

curl -sS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8009/carbon-api/ai/catalog/capabilities/
# → HTTP 200, JSON array length 31

curl -sS -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8009/carbon-api/ai/catalog/capabilities/
# → 401 (anonymous)
```

Sample ids: `employee.onboarding.*`, `gosi_wps.sif.*`, `leave.*`, `loan.*`, `payroll.*`.

## Skills (note only — not force-promoted)

| Surface | Count |
|---------|------:|
| DB `Skill` | 1 (`payroll_run_variance_check`, `app_identifier=carbon`, `visibility=private`) |
| `GET …/catalog/skills/` | **0** (scoping / not in seed path) |

`seed_nibras_processes` does not seed skills; left as residual.

## Files

| Action | File |
|--------|------|
| MODIFY | `backend/ai/management/commands/seed_nibras_processes.py` — app_identifier → brand default app |
| CREATE | `docs/pulse/evidence/PEC-R5-capability-seed.md` |

## Residuals

- Skills catalog still empty for Console (out of PEC-R5 force-promote scope).
- Existing `ProcessDefinition` / lone Skill rows still carry `app_identifier=carbon` (pre-existing; not changed here).
