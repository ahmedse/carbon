# GradeVance LTI LMS soak checklist

Use this after code is green (`72+ pytest`). Goal: one real Canvas/Moodle round-trip.

## 1. Env (EduOS instance)

```bash
export GRADEVANCE_LTI_ENABLED=true
export GRADEVANCE_LTI_ISSUER=https://<lms>/
export GRADEVANCE_LTI_CLIENT_ID=<tool-client-id>
export GRADEVANCE_LTI_AUTH_LOGIN_URL=https://<lms>/mod/lti/auth.php   # Moodle example
export GRADEVANCE_LTI_JWKS_URL=https://<lms>/mod/lti/certs.php
export GRADEVANCE_LTI_REDIRECT_URI=https://<eduos-host>/api/v1/gradevance/lti/oidc/launch/
export GRADEVANCE_LTI_DEPLOYMENT_IDS=<deployment-id>
export GRADEVANCE_LTI_TOKEN_URL=https://<lms>/mod/lti/token.php
export GRADEVANCE_LTI_CLIENT_SECRET=<secret>
export GRADEVANCE_LTI_AGS_DRY_RUN=false   # only after dry-run looks right
# Optional Deep Linking sign:
# export GRADEVANCE_LTI_TOOL_PRIVATE_KEY_PEM="$(cat tool_private.pem)"
```

Readiness: `GET /api/v1/gradevance/lti/status/` → `ready: true`.
Public registration helper: `GET /api/v1/gradevance/lti/tool-config/`.
Tool JWKS: `GET /api/v1/gradevance/lti/jwks/`.

## 2. LMS registration

1. Create external tool pointing at `initiate_login_uri` from tool-config.
2. Set redirect/target to `redirect_uris[0]`.
3. Paste tool JWKS URL (or public key).
4. Enable Assignment and Grade Services + Deep Linking scopes.

## 3. Soak path

| Step | Expect |
|------|--------|
| LMS launches tool | OIDC login → platform auth → launch 200 |
| Launch JSON | `user.username` starts with `lti:`; capabilities mapped |
| Publish summative assignment | Set `brief.lti.ags_lineitem_url` from launch claim (or LMS lineitem) |
| Student submits / analyze | Run created; review queue if low confidence |
| Marker releases | `released=true`; `run_manifest.ags_passback.ok` |
| Gradebook | Score appears when `AGS_DRY_RUN=false` |

Offline rehearsal (no LMS):  
`pytest gradevance/tests/test_lti_soak_path.py -o addopts= -p no:_testbrand`

## 4. Failures

| Symptom | Check |
|---------|-------|
| 503 on login | `GRADEVANCE_LTI_ENABLED` / missing settings |
| 401 on launch | JWKS / nonce / deployment_id |
| AGS 409 | Summative not released |
| AGS 502 | Token URL / client secret / lineitem URL |
| No gradebook row | Still dry-run, or LMS scope missing score write |
