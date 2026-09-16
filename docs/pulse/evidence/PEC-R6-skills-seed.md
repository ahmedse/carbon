# PEC-R6 — Seed live Skills Catalog

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Brand:** `DJANGO_BRAND=nibras`  
**Constraint:** no `./manage.sh start|stop`; no PostgreSQL restart

## Root cause (why Console showed empty)

| Factor | Finding |
|--------|---------|
| **Catalog filter** | `CatalogService.list_skills()` selects `Skill` where `instance_id == PLAN_INSTANCE_ID` (`resolve_instance_id()` → **`nibras`**). Not CBAC `scope_ai_queryset`. |
| **Pre-existing row** | 1× `payroll_run_variance_check` already `instance_promoted` / `admitted`, but on PEC-2A fixture instance `d12337c9-…` (`app_identifier=carbon`, `visibility=private`). |
| **UI** | Skills Panel renders whatever `GET …/catalog/skills/` returns — empty array → “No skills in the catalog yet.” |
| **Not the bug** | Status filter (draft vs promoted): catalog lists all statuses for the instance. Visibility/app CBAC do not gate this endpoint. |

PEC-R5 capability empty-list was `app_identifier=nibras` vs `people`. Skills empty-list here was **wrong `instance_id`**, not app_identifier — but the seed still sets `app_identifier=people` + `visibility=shared` for CBAC consistency.

## Command

```bash
cd backend
DJANGO_BRAND=nibras ../.venv/bin/python manage.py seed_catalog_skills
```

Idempotent: second run → `already promoted … catalog-ready`.  
Promotion path: `gate._promote_skill` (critics + `SkillAdmissionLog`); never raw `status=` write. Marginal-gain critic disabled for seed (same as `test_pec2a_learning_reuse`).

## Before / after

| Metric | Before | After |
|--------|-------:|------:|
| Skills on `instance_id=nibras` | 0 | **1** |
| `CatalogService().list_skills()` | 0 | **1** |
| `GET …/catalog/skills/` (superuser) | — | **200**, count **1** |
| Anonymous | — | **401** |
| Seed 2nd run | — | no-op (already promoted) |

Skill: `payroll_run_variance_check` · `procedure` · `instance_promoted` · `gate_status=admitted` · `app_identifier=people` · `visibility=shared` · `promoted_by=system:seed_catalog_skills`  
id: `97f419cd-bc0b-4692-99d4-bb1818e4bd76`

## HTTP / view proof

Live `:8009` was unreachable from the agent during this run (no service restart). Proof against the **same DB** the backend uses:

```text
CatalogService.list_skills count= 1
  name=payroll_run_variance_check status=instance_promoted instance_id=nibras verdict=admitted

DRF CatalogViewSet.skills (superuser force_authenticate):
  auth_status 200  auth_count 1  verdicts ['admitted']
  anon_status 401
```

Operator curl when backend is up:

```bash
TOKEN=$(DJANGO_BRAND=nibras python manage.py shell -c \
  "from django.contrib.auth import get_user_model; \
   from rest_framework_simplejwt.tokens import RefreshToken; \
   u=get_user_model().objects.filter(is_superuser=True).first(); \
   print(RefreshToken.for_user(u).access_token)")

curl -sS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8009/carbon-api/ai/catalog/skills/
# expect JSON array length ≥ 1
```

## Compliance

- Pulse-only (`backend/ai/**` + evidence/docs).
- Gate-only promote via `_promote_skill`.
- Brand instance `nibras`; `app_identifier=people` via `resolve_default_app_identifier()`.
- No `./manage.sh start|stop`; no PostgreSQL touch.

## Files

| Action | File |
|--------|------|
| CREATE | `backend/ai/management/commands/seed_catalog_skills.py` |
| CREATE | `docs/pulse/evidence/PEC-R6-skills-seed.md` |
