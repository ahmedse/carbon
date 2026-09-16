# PEC-R1 — Capabilities registry list API

**Date:** 2026-09-16  
**Worker:** backend-worker (Pulse)  
**Scope:** Read-only CBAC-scoped `GET` for durable `Capability` (P3-01) rows. No frontend. No mutations.

## URL chosen

`GET /carbon-api/ai/catalog/capabilities/`

Placed on the **catalog** mount alongside `/skills/` (same `IsAuthenticated` class as agent catalog reads). Pulse `/pulse/skills/` is admin-gated telemetry; durable Capability contracts belong next to the skill catalog for Console consumption (PEC-R2).

## Shape

Business fields only (no partition keys, no approval/inputs secrets):

```json
[
  {
    "capability_id": "dq.rule.validate",
    "business_name": "Validate DQ rule",
    "purpose": "Validate a draft DQ rule before publish",
    "kind": "read_only",
    "host_action": "dq.validate_rule",
    "owner": "dq",
    "version": "1.0",
    "permissions": {"read": ["ai:view_console"]},
    "requires_confirmation": false
  }
]
```

## Auth / CBAC

| Case | Result |
|------|--------|
| Anonymous | 401 |
| Authenticated | 200 + scoped rows |
| Private row owned by another user | Hidden via `scope_ai_queryset` |
| Shared / global (null org) | Visible to authenticated caller |
| POST / PATCH / DELETE | 405 (GET-only, RULE_21) |

Scoping: `accounts.ai_scoping.scope_ai_queryset` (app_identifier + visibility + org subtree).

## Verification

```bash
./manage.sh test ai/tests/test_capability_list_api.py -q
# 4 passed

./manage.sh test ai/tests/test_capability_loader.py ai/tests/test_capability_list_api.py -q
# 7 passed, 3 failed — failures are pre-existing in test_capability_loader.py
# (pack resolves to Nibras capabilities; pilot DQ-only assertions stale). Out of PEC-R1 scope.
```

## Files touched

| File | Change |
|------|--------|
| `backend/ai/catalog_api.py` | `CapabilityListSerializer` + GET `capabilities` action |
| `backend/ai/catalog_urls.py` | `capabilities/` route (before `<pk>/`) |
| `backend/ai/tests/test_capability_list_api.py` | 401 / 200 shape / CBAC / 405 |
| `docs/pulse/evidence/PEC-R1-capabilities-list.md` | This evidence |

## Compliance checklist

- [x] RULE_18 — Pulse seat only; no `backend/people/**` / NSR FE
- [x] RULE_20 — Host read layer; engine not imported for this list
- [x] RULE_21 — Read-only list; writes return 405
- [x] RULE_23 — Business fields only; no engine jargon / partition leak
- [x] RULE_30 — Pulse residual; Nibras paths untouched
- [x] AppScopeMixin + `scope_ai_queryset` fail-closed
- [x] Thick: thin view + serializer; catalog pattern
