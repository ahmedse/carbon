---

## 3. `docs/env.md`

```markdown
# Environment Variables Reference

Document all environment variables used by the platform.

---
# Environment Variables Reference

This document lists environment variables the platform actually reads.

## Backend (Django)

Core:

- `DJANGO_ENV`: `development` or `production`
- `SECRET_KEY`: a long random secret (required)
- `DJANGO_DEBUG` (fallback: `DEBUG`): `True`/`False`
- `DJANGO_ALLOWED_HOSTS` (fallback: `ALLOWED_HOSTS`): comma-separated list, e.g. `localhost,127.0.0.1`
- `DJANGO_API_PREFIX`: API prefix used by all routes, e.g. `/api/v1/` or `/carbon-api/`

Security / CORS / CSRF:

- `CSRF_TRUSTED_ORIGINS`: comma-separated origins, e.g. `https://carbon.example.com`
- `CORS_ALLOWED_ORIGINS`: comma-separated origins, e.g. `https://carbon.example.com`
- `DJANGO_SECURE_SSL_REDIRECT`: `True`/`False`
- `DJANGO_SESSION_COOKIE_SECURE`: `True`/`False`
- `DJANGO_CSRF_COOKIE_SECURE`: `True`/`False`

Files:

- `DJANGO_STATIC_ROOT`: e.g. `./staticfiles/`
- `DJANGO_MEDIA_ROOT`: e.g. `./mediafiles/`
- `DATASCHEMA_UPLOAD_PATH`: e.g. `dataschema_uploads/`

Database:

- `DB_NAME`: e.g. `carbon_dev`
- `DB_USER`: e.g. `carbon_user`
- `DB_PASSWORD`: database password
- `DB_HOST`: e.g. `localhost`
- `DB_PORT`: e.g. `5432`

## Frontend (Vite/React)

- `VITE_BASE`: frontend base path for routing, e.g. `/carbon/`
- `VITE_API_BASE_URL`: full backend API base URL (should already include the API prefix), e.g. `http://localhost:8001/api/v1`

