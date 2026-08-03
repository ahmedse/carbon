# ADR 0003 — Migrate from drf-yasg to drf-spectacular

- **Status:** Proposed
- **Date:** 2026-08-03
- **Deciders:** Master Architect
- **Area:** backend

## Context
`drf-yasg` (1.21.15) is pinned in requirements.txt. The library has been
unmaintained since 2023 and emits deprecation warnings on every test run:

> SwaggerJSONRenderer & SwaggerYAMLRenderer's `format` has changed to not include
> a `.` prefix, please silence this warning by setting `SWAGGER_USE_COMPAT_RENDERERS = False`

Additionally, `drf-yasg` does not support OpenAPI 3.1, has no first-party
Pydantic/Spectacular integration, and is a blocking risk for Django 5.3+.
The replacement, `drf-spectacular`, is actively maintained by T. Franzel and is
the de-facto DRF OpenAPI tool.

## Decision
Migrate from `drf-yasg` to `drf-spectacular` in the next maintenance window:

1. Replace `drf-yasg` with `drf-spectacular` in requirements.txt
2. Replace `get_schema_view(...)` in `config/urls.py` with `SpectacularAPIView` / `SpectacularSwaggerView`
3. Replace `@swagger_auto_schema` decorators with `@extend_schema`
4. Remove `SWAGGER_SETTINGS` from settings.py (if any)
5. Verify all endpoints appear in the new schema

## Alternatives Considered
- **Keep drf-yasg** — Rejected. Unmaintained, emits warnings, blocks Django upgrades
- **Manual OpenAPI spec** — Rejected. Too labour-intensive to maintain

## Consequences
- **Positive:** Actively maintained, OpenAPI 3.1 support, better type inference
- **Negative / trade-off:** ~2-4 hour migration window; decorator syntax differs slightly
