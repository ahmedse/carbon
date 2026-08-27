# EPH-5C — OpenAPI Spec (drf-yasg → drf-spectacular migration, ADR 0003)

**Date:** 2026-08-27
**Executor:** backend-worker (concurrent) + master-architect (defect fixes, verification, commit)
**Commit:** `537c2c5` (backend) — docs commit follows
**Status:** DONE ✅ (verified live + full regression)

---

## Summary

Migrated the platform's OpenAPI schema generation from the unmaintained `drf-yasg` to
`drf-spectacular` (ADR 0003). The schema is now served in **all environments** (not just dev)
at `/carbon-api/schema/` with Swagger UI + ReDoc, gated behind `AdminOrSuperuserOnly`.

## Scope

| File | Change |
|------|--------|
| `backend/requirements.txt` | `drf-yasg` → `drf-spectacular==0.30.0` |
| `backend/config/settings.py` | `INSTALLED_APPS`, `DEFAULT_SCHEMA_CLASS`, `SPECTACULAR_SETTINGS` (title, version, path-prefix trim, no serve-include) |
| `backend/config/urls.py` | `/carbon-api/schema/` (JSON), `/schema/swagger-ui/`, `/schema/redoc/` — gated `AdminOrSuperuserOnly`, all envs; removed dev-gated drf-yasg block |
| `backend/accounts/views.py` | `@swagger_auto_schema` → `@extend_schema` (platform_apps FBV) |
| `backend/catalog/views.py` | archive-bulk + governance compliance conversions (staged patch excluded concurrent notes/reactions work) |
| `backend/dq/views.py` | 9 schema sites converted; inline request schemas wrapped in `application/json` media-type maps |
| `backend/emissions/views.py` | 3 schema sites converted (report PDF, owner summary/assets/activity, batch calculate) |
| `backend/mdm/views.py` | 5 schema sites converted (values/date, transition, add_value, archive-bulk, bulk-create, bind-field) |
| `backend/mdm/tests/test_swagger_docs.py` | rewritten: hits `/schema/?format=json` as superuser, asserts 11 operations + descriptions + admin-only auth gate |

## Defects found & fixed during verification (master-architect)

1. **Missing `DEFAULT_SCHEMA_CLASS`** — schema generation raised
   `AssertionError: Incompatible AutoSchema used on View ... ScopedRoleViewSet`.
   Fix: `'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema'` in `REST_FRAMEWORK`.
2. **15 bare-dict `request=` usages** — drf-spectacular interprets a bare dict as a
   media-type→schema map, producing invalid OpenAPI (`jsonschema` validation errors).
   Fix: wrap inline schemas as `request={'application/json': {...}}` across
   catalog/dq/emissions/mdm.
3. **Missing path-prefix trim** — drf-spectacular kept the `/carbon-api/` mount in every
   path (drf-yasg stripped it), breaking doc assertions.
   Fix: `SCHEMA_PATH_PREFIX: '/carbon-api'` + `SCHEMA_PATH_PREFIX_TRIM: True` in
   `SPECTACULAR_SETTINGS`.

## Verification evidence

```bash
# 1. manage.py check — PASS (no system checks failed)
# 2. makemigrations --check --dry-run — "No changes detected"
# 3. Schema generation snippet (drf_spectacular.validation):
#    VALIDATE ERRORS: None          (schema valid OpenAPI 3.0.3)
#    MISSING: []                    (all 20 documented paths present, prefix stripped)
#    transition requestBody: {'content': {'application/json': {'schema': {
#        'type': 'object', 'properties': {'state': {...}}, 'required': ['state']}}}}
# 4. pytest mdm/tests/test_swagger_docs.py -v --create-db → 3 passed, 11 subtests
# 5. Full regression: pytest core/ catalog/ accounts/ mdm/ importexport/ -q --create-db
#    → 625 passed, 11 subtests passed
# 6. Live (./manage.sh restart):
#    GET /carbon-api/schema/?format=json            → 200 (JWT admin), openapi 3.0.3, 364 paths
#    GET /carbon-api/schema/?format=json (anon)     → 401
#    GET /carbon-api/schema/swagger-ui/ (admin)     → 200
#    GET /carbon-api/schema/redoc/ (admin)          → 200
#    GET /carbon-api/swagger/ (old path)            → 404 (removed)
#    GET /carbon-api/health/                        → 200, API-Version: 1 (EPH-5A intact)
```

## Notes / non-goals

- `swagger_fake_view` guards preserved untouched (drf-spectacular sets the same flag).
- Schema-generation warnings remain for serializer-less APIViews (graceful fallback) —
  pre-existing behavior, not blockers.
- **Excluded from commit** (other sessions' uncommitted work): `mdm/serializers.py` +
  `mdm/tests/test_org_units.py` (null-normalization), `catalog/views.py` notes/comments/
  reactions additions (staged selectively — only EPH-5C hunks committed), W7-B frontend
  decommission files.
- ADR 0003 status: **Accepted** by implementation (can update ADR doc in a follow-up if desired).
