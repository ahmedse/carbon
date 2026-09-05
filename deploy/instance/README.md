# Deploy Kit — Multi-instance template (ADR-0015)

**One codebase, N isolated deployments.** Do **not** fork the repo, and do **not**
reintroduce multi-tenancy (`tenant_id`). Each organisation is a *deployment* of the
same single codebase, differentiated only by env config and the app-activation set.

`deploy/carbon/` is one instantiation of this template. This directory is the
reusable generalization.

## Prod topology (identical to `deploy/carbon/`)

| Service | Where it runs | How it's reached |
|---------|---------------|------------------|
| Backend (Gunicorn) | **Docker** (`${INSTANCE}-backend`) | `127.0.0.1:${BACKEND_PORT}` → container `:8000` |
| Frontend (React SPA) | **Host** — nginx serves `dist/` | `https://<DOMAIN>/` |
| PostgreSQL | **Host** | `host.docker.internal:5432` (own DB per instance) |
| Redis (cache + queue) | **Host** | `host.docker.internal:6379` (unique DB index per instance) |

Docker is **never** used in the dev environment — but **prod uses Docker for the
backend**, exactly like `deploy/carbon/`. Frontend, Redis, and Postgres stay on the
host; only the Django/Gunicorn backend is containerized.

## Port & DB-index allocation (MUST stay unique per host)

| Instance | `BACKEND_PORT` | `DB_NAME` | `REDIS_URL` db index |
|----------|---------------|-----------|----------------------|
| carbon   | 8006          | carbon_prod | `…:6379/0` |
| nibras   | 8008          | nibras_prod | `…:6379/1` |
| medos    | 8009          | medos_prod  | `…:6379/2` |
| tectona  | 8010          | tectona_prod| `…:6379/3` |

`deploy-instance.sh` refuses to start if `BACKEND_PORT` is already listening or
already published by another container. Never reuse a port or Redis DB index
between two instances on the same host.

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Generic — reads `${INSTANCE}`, `${ENV_FILE}`, `${BACKEND_PORT}` from the instance env file at runtime. Serves every org unchanged. |
| `.env.template` | Per-instance config: identity, branding, DB, domain, `APP_ACTIVE_SLUGS`. |
| `nginx.conf.template` | Rendered to `nginx.conf` by `deploy-instance.sh` (substitutes `__DOMAIN__`, `__INSTANCE__`). |
| `stamp-instance.sh` | Creates `deploy/<name>/` from the template. |
| `deploy-instance.sh` | Deploys one instance (DB → build → migrate → activate apps → render nginx). |
| `auto-deploy.sh` | Pull-based release deploy — reacts only to `${INSTANCE}-v*` tags. |
| `setup-auto-deploy.sh` | Installs a systemd timer (every 2 min) that drives `auto-deploy.sh`. |

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

## Tag-based releases & auto-deploy (CI/CD without inbound SSH)

Deploys are **pull-based**: the VPS polls the git remote every 2 minutes and reacts
only to tags prefixed with its own instance name. Commits/pushes stay human-gated
(git-workflow RULE 1); a tag push is the explicit release trigger.

### Release workflow (from a dev machine / GitHub Actions)

```bash
# 1. Land the change on main (human-gated commit + push)
# 2. Cut an instance-scoped tag and push it:
git tag nibras-v0.1.0
git push origin nibras-v0.1.0
```

Within 2 minutes the VPS pulls the tag and auto-deploys **that instance only**.
`nibras-v*` never triggers `aastmt`/`medos`/`tectona`, and vice-versa.

### Tag naming convention

```
<instance>-v<major>.<minor>.<patch>     # nibras-v0.1.0, aastmt-v1.6.0
```

- `INSTANCE` matches the stamped dir name and the `DJANGO_BRAND` id.
- `--sort=-version:refname` orders them correctly (0.1.0 < 0.10.0).

### Enable on the VPS (once per instance)

```bash
sudo bash deploy/nibras/setup-auto-deploy.sh nibras /srv/nibras 8003 ahmed
# → /etc/nibras-deploy.env + nibras-deploy.service + nibras-deploy.timer (2 min)
```

Useful ops:

```bash
systemctl status nibras-deploy.timer
journalctl -u nibras-deploy -f
systemctl start nibras-deploy.service   # trigger now
```

### What a deploy does (`auto-deploy.sh`)

1. Locks `/tmp/<instance>-deploy.lock` (no concurrent deploys).
2. `git fetch --tags`, finds newest `${INSTANCE}-v*` tag, skips if already `.deployed-tag`.
3. Checks out the tag (preserving `staticfiles`/`mediafiles`/`dataschema_uploads`).
4. Builds frontend with `VITE_BRAND=<DJANGO_BRAND>` + `VITE_API_BASE_URL=/carbon-api/`.
5. `docker compose build --no-cache` + `up -d --force-recreate` (container `${INSTANCE}-backend`).
6. Health-checks `http://127.0.0.1:<port>/carbon-api/health/`.
7. `activate_apps --active "$APP_ACTIVE_SLUGS"` (per-instance subset).
8. `nginx -t` + reload, stamps `.deployed-tag`.

### Secrets never leave the VPS

`/etc/<instance>-deploy.env` and `backend/.env.<instance>` hold DB creds, secret key,
and domains on the server. Nothing sensitive is committed or shipped via CI — the
remote is read-only from the VPS's perspective.

### Note on imported raw data

`auto-deploy.sh` runs `git clean -fd`, which deletes untracked files (incl. raw data).
Keep PII (e.g. GOFSCO xlsx) **outside** `APP_DIR` (e.g. `/srv/<instance>-data/`) and
import it via `--path` — never place it inside the git checkout.
