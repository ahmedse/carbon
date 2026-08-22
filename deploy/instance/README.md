# Deploy Kit — Multi-instance template (ADR-0015)

**One codebase, N isolated deployments.** Do **not** fork the repo, and do **not**
reintroduce multi-tenancy (`tenant_id`). Each organisation is a *deployment* of the
same single codebase, differentiated only by env config and the app-activation set.

`deploy/carbon/` is one instantiation of this template. This directory is the
reusable generalization.

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Generic — reads `${INSTANCE}`, `${ENV_FILE}`, `${BACKEND_PORT}` from the instance env file at runtime. Serves every org unchanged. |
| `.env.template` | Per-instance config: identity, branding, DB, domain, `APP_ACTIVE_SLUGS`. |
| `nginx.conf.template` | Rendered to `nginx.conf` by `deploy-instance.sh` (substitutes `__DOMAIN__`, `__INSTANCE__`). |
| `stamp-instance.sh` | Creates `deploy/<name>/` from the template. |
| `deploy-instance.sh` | Deploys one instance (DB → build → migrate → activate apps → render nginx). |

## Stamp a new org (e.g. Nibras)

```bash
bash deploy/instance/stamp-instance.sh nibras
# edit deploy/nibras/.env  (DOMAIN, DB creds, DJANGO_INSTANCE_NAME=Nibras, APP_ACTIVE_SLUGS)
cp deploy/nibras/.env backend/.env.nibras
bash deploy/nibras/deploy-instance.sh nibras
```

## The one per-instance knob: app activation

The **only** code-level difference between deployments is which `AppManifest`s are
active. `deploy-instance.sh` drives it from `APP_ACTIVE_SLUGS` in the env file:

```bash
python manage.py activate_apps --active emissions,people   # AAST
python manage.py activate_apps --active healthy            # Healthy Foods
python manage.py activate_apps --all                       # everything
```

Rules (see `backend/appregistry/management/commands/activate_apps.py`):
- System apps (`is_system=True`, e.g. emissions) always stay active.
- Non-system apps not in `--active` are deactivated.
- Idempotent — safe to run on every deploy.
- A slug with no manifest yet is a warning, not an error.

## Isolation guarantees

- **Database:** each instance gets its own Postgres DB (`DB_NAME` per env).
- **Containers/volumes:** namespaced by `${INSTANCE}` so instances can co-exist on one host.
- **Branding:** `DJANGO_INSTANCE_NAME` drives `PLATFORM_TITLE` + frontend `VITE_*`.
- **No tenant column anywhere** — isolation is a boundary, not a `WHERE` clause.
