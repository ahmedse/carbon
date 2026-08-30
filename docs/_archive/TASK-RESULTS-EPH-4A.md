# Task Results — EPH-4A: Column-Level RBAC (FieldAccessPolicy)

**Date:** 2026-08-26
**Worker:** backend-worker (DeepSeek V4-Flash) · **Architect:** master-architect (DeepSeek V4-Pro)
**Status:** DONE · closes P0-1 (column-level access control)
**Commit:** `448ccc9`

## What shipped

| Area | Change |
|------|--------|
| Model | `FieldAccessPolicy` (`deny` / `mask` per `DataField`, gated by `required_capability`) |
| Migration | `dataschema.0011_fieldaccesspolicy` |
| Capability | New `catalog:view_pii` (distinct, sensitive) |
| Serializer | `DataFieldSerializer.to_representation()` applies deny/mask |
| Admin CRUD | `GET/POST /dataschema/fields/{id}/policies/` + `DELETE .../{pk}/` |
| Tests | 9 tests in `dataschema/tests/test_field_access_policy.py` |

## Design decisions

1. **`catalog:view_pii` is a distinct, sensitive capability** — NOT implied by
   `catalog:view` (analysts/viewers/auditors must never silently gain PII access).
2. **Granted to `dataowners_group` only.** The spec mentions "Data Owner + HR groups";
   this codebase has **no HR group** (`accounts/constants.py` groups are
   `dataowners_group`, `analysts_group`, `viewers_group`, `auditors_group`,
   `carbon_data_owners_group`, `carbon_analysts_group`, plus the `*_lead` groups).
   Future HR/other groups must be granted via admin or a management command — not by
   silently editing `GROUP_CAPABILITIES`.
3. **Superuser bypass via `has_capability()`**, not a naive
   `key in get_user_capabilities(user)` membership test — `has_capability` correctly
   honors the `"*"` wildcard.
4. **Request-context guard** in `to_representation()` — `perform_create`/`perform_update`
   call `DataFieldSerializer(obj).data` with no request; missing context → full data
   (no masking applied in change logs).
5. **N+1 mitigation** — `DataFieldViewSet` and `DataTableViewSet` querysets prefetch
   `access_policies`.

## Verification (architect-run)

```
manage.py check ................................................. no issues
makemigrations --check --dry-run ................................ no changes
migrate dataschema .............................................. 0011 OK
pytest dataschema/tests/test_field_access_policy.py -v ........... 9 passed
pytest dataschema/ accounts/ -q ................................. 422 passed
```

## Response shape contract (for EPH-4C frontend)

- `deny`: `{"id": <int>, "name": <str>, "access_denied": true}`
- `mask`: full field payload + `"is_masked": true`

## Next

EPH-4B (Data Masking Engine) — `DataField.masking_strategy` + `MaskingService`;
depends on EPH-4A (`FieldAccessPolicy` + `catalog:view_pii`).
