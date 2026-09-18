# GradeVance enterprise integration (P3)

## LTI 1.3 Advantage

| Endpoint | Purpose |
|----------|---------|
| `GET/POST /api/v1/gradevance/lti/oidc/login/` | OIDC login initiation (state+nonce); 503 until configured |
| `POST /api/v1/gradevance/lti/oidc/launch/` | Callback — JWT/JWKS verified; provisions User + ScopedRole; returns AGS/NRPS URLs from claims |
| `GET /api/v1/gradevance/lti/config/` | Readiness flags (no secrets) |
| `GET /api/v1/gradevance/lti/status/` | Advantage surface + AGS dry-run flag |
| `GET /api/v1/gradevance/lti/jwks/` | Tool public JWKS (from `GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM`) |
| `POST /api/v1/gradevance/lti/deep-link/preview/` | Content-item + optional signed JWT |
| `POST /api/v1/gradevance/lti/nrps/preview/` | NRPS roster dry-run (+ optional `sync`) |
| `GET /api/v1/gradevance/runs/<id>/ags-preview/` | AGS score JSON (no network) |
| `POST /api/v1/gradevance/runs/<id>/ags-passback/` | OAuth2 + POST to lineitem `/scores` (dry-run default) |
| `GET /api/v1/gradevance/accessibility/` | WCAG checklist toward VPAT |

Modules: `lti/jwt_verify.py`, `lti/provision.py`, `lti/ags.py`, `lti/ags_client.py`, `lti/deep_link.py`, `lti/nrps.py`.

Env:

- `GRADEVANCE_LTI_ENABLED`, `ISSUER`, `CLIENT_ID`, `AUTH_LOGIN_URL`, `JWKS_URL`, `REDIRECT_URI`, `DEPLOYMENT_IDS`
- `GRADEVANCE_LTI_TOKEN_URL`, `GRADEVANCE_LTI_CLIENT_SECRET` (AGS live post)
- `GRADEVANCE_LTI_AGS_DRY_RUN` (default `true`)
- `GRADEVANCE_LLM_CODER_ENABLED` (default `false`)

| Capability | Status |
|------------|--------|
| OIDC login launch | Live when configured — maps LMS roles → `gradevance_*` groups / ScopedRole |
| Assignment Deep Linking | Preview API + authoring UI; sign with tool key in production |
| AGS score passback | Builder + HTTP client; only after summative `released=True`; dry-run default |
| NRPS | Membership parser ready; HTTP sync TBD |

Implementation home: `backend/gradevance/lti/` — never in Pulse.

## SSO

EduOS instance uses platform SSO (SAML/OIDC) already on ClearTurn accounts.
LTI launch also establishes a Django session when the request has one.
Role mapping table lives in instance config, not hardcoded English-department assumptions.

## Audit export

`GET /api/v1/gradevance/runs/<id>/audit-export/` returns a JSON evidence package
(`export_format: json_v2`): assignment/submission metadata, segments + LCT codes,
wave metrics, coaching, rubric `evidence_bindings`, ExpertEdit trail, release
actor/timestamp, and last AGS passback result. Summative without `released`
returns 409. `?format=download` attaches a JSON file.

## Accessibility (WCAG toward VPAT)

GradeVance studios ship skip links + `<main>` landmarks + table captions.
Evidence pack: `docs/eduos/vpat-evidence/checklist.json`.
Playwright landmarks smoke: `carbon-frontend/e2e/journeys/journey-gradevance-a11y.spec.ts`.
Full VPAT 2.5 still needs axe + manual keyboard/SR under EduOS theme.

## LMS soak

See [LMS-SOAK.md](./LMS-SOAK.md). Offline rehearsal:
`pytest gradevance/tests/test_lti_soak_path.py`. Readiness:
`manage.py gradevance_lti_readiness`.
