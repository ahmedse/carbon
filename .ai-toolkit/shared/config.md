# Config & Environments — No Hardcoding, One Source of Truth
# Read by: all workers, especially Backend, Frontend, DevOps.
# Purpose: nothing environment-specific is ever hardcoded; prod is safe by construction.

---

## RULE 1 — Nothing Environment-Specific Is Hardcoded

Anything that differs between dev / staging / prod is a CONFIG VALUE, not a literal.

That includes: hosts, ports, URLs, DB creds, API keys, feature flags, timeouts,
model names, base paths, allowed origins, log levels, external service endpoints.

```python
# WRONG
REPORTING_URL = "http://localhost:4000"
MODEL = "gpt-4"
DB_HOST = "127.0.0.1"

# CORRECT
REPORTING_URL = os.getenv("REPORTING_BASE_URL", "http://localhost:4000")  # dev default OK
# Carbon does NOT manage LLM models. Pulse owns all AI/LLM configuration.
# Carbon's only AI config is VITE_PULSE_HOST / VITE_PULSE_INSTANCE_ID (frontend)
# and PULSE_HOST / PULSE_JWT_SECRET (backend). See registry/config-keys.md.
DB_HOST = os.getenv("DB_HOST", "localhost")
```

Every config key is listed in `registry/config-keys.md` (auto-generated). Add new keys there
by adding them in code + `.env.example`, then re-run `scan.sh`.

---

## RULE 2 — Defaults: Safe for Dev, Explicit for Prod

- Non-secret dev default is allowed (`os.getenv("PORT", "8001")`).
- Real secrets have NO default — `os.environ["DJANGO_SECRET_KEY"]` (crash if missing = correct).
- Prod-critical flags default to the SECURE value:
  `DEBUG` defaults False, `SECURE_SSL_REDIRECT` defaults True.

---

## RULE 3 — `.env` Discipline

- `.env` holds real values — NEVER committed.
- `.env.example` committed, lists EVERY key with a placeholder/dummy value + comment.
- When you add a new `os.getenv("NEW_KEY")`, you MUST add `NEW_KEY=` to `.env.example`.
- Frontend build-time config via `import.meta.env.VITE_*` (Vite) — same discipline.

---

## RULE 4 — Environment Detection

- One switch drives environment behavior (`DJANGO_ENV=development|production`).
- Environment-conditional blocks are grouped, not scattered:
  ```python
  if DJANGO_ENV == "production":
      DEBUG = False
      SECURE_SSL_REDIRECT = True
      CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
  ```
- NEVER detect environment by hostname string-matching scattered through the code.

---

## RULE 5 — Feature Flags

- Toggle risky/new behavior behind an env flag, default OFF in prod until proven.
- Flags are read once at startup or via a small config accessor — not re-parsed everywhere.
- Remove dead flags after a feature is permanent (don't accumulate flag debt).

---

## RULE 6 — Prod Config Safety Checklist

Before/at deploy (DevOps Worker):
```
[ ] DEBUG=False
[ ] SECRET_KEY set (no fallback) and unique to prod
[ ] ALLOWED_HOSTS explicit, no '*' / '0.0.0.0'
[ ] CORS/CSRF origins explicit whitelists
[ ] Secure cookies + SSL redirect on
[ ] DB creds from env, not literals
[ ] All keys the app reads exist in the prod environment (cross-check registry/config-keys.md)
[ ] No dev/test endpoint or debug toolbar enabled
```

---

## RULE 7 — Single Source of Truth for Shared Values

- A value used in >1 place is defined ONCE and imported — never copy-pasted.
  - Backend: a settings constant or config accessor.
  - Frontend: a `config.js` constant or a token.
- Ports, base URLs, timezone, model names: defined once, referenced everywhere.
- If the same literal appears in 2 files, that's a bug — hoist it.

---

## Anti-Patterns (reject in review)

- Hardcoded host / port / URL / model name / credential
- New `os.getenv` key missing from `.env.example`
- Environment detected by scattered hostname checks
- `DEBUG=True` reachable in production
- The same config literal duplicated across files
- Secret with a hardcoded fallback value
