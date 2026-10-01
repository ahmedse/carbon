#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Pull-based auto-deploy for ONE Carbon instance (ADR-0015).
# Runs on the VPS via a systemd timer every 2 minutes.
#
# Tag routing: each instance reacts ONLY to its own `${INSTANCE}-v*`
# tags (e.g. nibras-v0.1.0, aastmt-v1.6.0). A shared codebase ships
# per-instance releases without cross-instance deploys.
#
# Needs: /etc/<instance>-deploy.env with APP_DIR, BACKEND_PORT, INSTANCE
#        (created by setup-auto-deploy.sh <instance>).
#
# Usage (normally via systemd):
#   bash deploy/instance/auto-deploy.sh <instance-name>
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

INSTANCE="${1:?usage: auto-deploy.sh <instance-name> (e.g. carbon, nibras)}"
CONFIG="/etc/${INSTANCE}-deploy.env"

if [[ ! -f "$CONFIG" ]]; then
    echo "ERROR: $CONFIG not found — run setup-auto-deploy.sh $INSTANCE first" >&2
    exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG"

APP_DIR="${APP_DIR:?APP_DIR must be set in $CONFIG}"
BACKEND_PORT="${BACKEND_PORT:-8002}"

COMPOSE_ENV_FILE="$APP_DIR/backend/.env.$INSTANCE"
COMPOSE_FILE="$APP_DIR/deploy/$INSTANCE/docker-compose.yml"
RUNTIME_COMPOSE="$COMPOSE_FILE"
FRONTEND_DIR="$APP_DIR/carbon-frontend"
# Packs that must never be mounted into the nibras cell.
NIBRAS_FORBIDDEN_PACKS=(carbon aast-med eduos medos tectona)

DEPLOY_LOCK="/tmp/${INSTANCE}-deploy.lock"
DEPLOYED_TAG_FILE="$APP_DIR/.deployed-tag"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# INSTANCE=nibras boots domain_packs/nibras only. A missing or foreign pack
# aborts before the container starts, so the process cannot fall back to carbon.
prepare_nibras_runtime() {
    [[ "$INSTANCE" == "nibras" ]] || return 0
    if [[ "$BRAND" != "nibras" ]]; then
        log "ERROR: INSTANCE=nibras refuses DJANGO_BRAND=${BRAND:-unset}. Refusing a carbon fallback."
        exit 1
    fi
    local src="$APP_DIR/domain_packs/nibras"
    local dest="$APP_DIR/.runtime-packs"
    local pack_id name
    if [[ ! -f "$src/pack.yaml" ]]; then
        log "ERROR: $src/pack.yaml missing — refusing to start"
        exit 1
    fi
    pack_id=$(awk '/^id:[[:space:]]*/ { print $2; exit }' "$src/pack.yaml")
    if [[ "$pack_id" != "nibras" ]]; then
        log "ERROR: resolved pack id is '${pack_id:-missing}', refusing to start"
        exit 1
    fi
    rm -rf "$dest"
    mkdir -p "$dest/nibras"
    cp -a "$src/." "$dest/nibras/"
    # Shared guide copy. Not a Pulse pack and has no catalog.
    if [[ -d "$APP_DIR/domain_packs/_platform" ]]; then
        mkdir -p "$dest/_platform"
        cp -a "$APP_DIR/domain_packs/_platform/." "$dest/_platform/"
    fi
    for name in "${NIBRAS_FORBIDDEN_PACKS[@]}"; do
        if [[ -e "$dest/$name" ]]; then
            log "ERROR: runtime pack dir contains forbidden pack $name"
            exit 1
        fi
    done
    if [[ ! -f "$dest/nibras/pack.yaml" || ! -f "$dest/nibras/api_catalog.yaml" ]]; then
        log "ERROR: nibras pack did not land in $dest"
        exit 1
    fi
    export DOMAIN_PACKS_MOUNT="$dest"
    local built_at
    built_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    export CARBON_IMAGE_BUILT_AT="$built_at"
    export CARBON_DEPLOYED_AT="$built_at"
    RUNTIME_COMPOSE="$APP_DIR/deploy/$INSTANCE/docker-compose.runtime.yml"
    COMPOSE_FILE_SRC="$COMPOSE_FILE" \
    RUNTIME_COMPOSE_PATH="$RUNTIME_COMPOSE" \
    DOMAIN_PACKS_MOUNT="$dest" \
    RELEASE_TAG="$LATEST_TAG" \
    IMAGE_BUILT_AT="$built_at" \
    python3 - <<'PY'
import os, re, sys
from pathlib import Path
text = Path(os.environ["COMPOSE_FILE_SRC"]).read_text(encoding="utf-8")
mount = os.environ["DOMAIN_PACKS_MOUNT"]
new, n = re.subn(
    r"(?m)^(\s*-\s*)([^:\n]+):/domain_packs(?::ro)?\s*$",
    lambda m: f"{m.group(1)}{mount}:/domain_packs:ro",
    text,
    count=1,
)
if n != 1:
    sys.exit("domain_packs volume not found in compose; refusing nibras start")
if "CARBON_RELEASE_TAG" not in new:
    block = (
        "    environment:\n"
        f"      CARBON_RELEASE_TAG: \"{os.environ['RELEASE_TAG']}\"\n"
        f"      CARBON_IMAGE_BUILT_AT: \"{os.environ['IMAGE_BUILT_AT']}\"\n"
        f"      CARBON_DEPLOYED_AT: \"{os.environ['IMAGE_BUILT_AT']}\"\n"
    )
    new, n2 = re.subn(r"(?m)^(    image:.*\n)", r"\1" + block, new, count=1)
    if n2 != 1:
        sys.exit("could not inject release env; refusing nibras start")
Path(os.environ["RUNTIME_COMPOSE_PATH"]).write_text(new, encoding="utf-8")
PY
    log "Nibras runtime packs: $dest (nibras only)"
}

assert_nibras_pack_gate() {
    [[ "$INSTANCE" == "nibras" ]] || return 0
    BACKEND_PORT="$BACKEND_PORT" python3 - <<'PY'
import json, os, sys, urllib.request
port = os.environ["BACKEND_PORT"]
url = f"http://127.0.0.1:{port}/carbon-api/health/"
with urllib.request.urlopen(url, timeout=15) as resp:
    data = json.load(resp)
rel = data.get("release") or {}
pack = rel.get("pack")
brand = rel.get("process_brand")
loaded = list(rel.get("loaded_packs") or [])
catalogs = list(rel.get("catalogs") or [])
extra = list(rel.get("extra_packs") or [])
forbidden = {"carbon", "aast-med", "eduos", "medos", "tectona"}
seen = set(loaded) | set(catalogs) | set(extra)
problems = []
if brand != "nibras":
    problems.append(f"process_brand={brand!r}")
if pack != "nibras":
    problems.append(f"pack={pack!r}")
if extra:
    problems.append(f"extra_packs={extra!r}")
if loaded != ["nibras"]:
    problems.append(f"loaded_packs={loaded!r}")
hit = sorted(seen & forbidden)
if hit:
    problems.append(f"forbidden catalogs loaded: {hit}")
if not rel.get("pulse_enabled"):
    problems.append("pulse_enabled is not true")
if problems:
    sys.exit("nibras pack gate failed: " + "; ".join(problems))
print("nibras pack gate ok", rel.get("tag"), pack, rel.get("pack_version"))
PY
}

# Prevent concurrent deploys
if [[ -f "$DEPLOY_LOCK" ]]; then
    log "Deploy already in progress (lock: $DEPLOY_LOCK), skipping."
    exit 0
fi
cleanup() { rm -f "$DEPLOY_LOCK"; }
trap cleanup EXIT
touch "$DEPLOY_LOCK"

cd "$APP_DIR"

# Fetch latest tags
git fetch origin --tags --force --quiet 2>/dev/null

# ── Tag routing (ADR-0015): only this instance's prefixed tags ─────
LATEST_TAG=$(git tag -l "${INSTANCE}-v*" --sort=-version:refname | head -1)
if [[ -z "$LATEST_TAG" ]]; then
    log "No ${INSTANCE}-v* tags found — nothing to deploy."
    exit 0
fi

CURRENT_TAG=""
if [[ -f "$DEPLOYED_TAG_FILE" ]]; then
    CURRENT_TAG=$(cat "$DEPLOYED_TAG_FILE")
fi

if [[ "$LATEST_TAG" == "$CURRENT_TAG" ]]; then
    exit 0  # Already deployed, silent exit
fi

log "New tag detected: $LATEST_TAG (current: ${CURRENT_TAG:-none})"

# ── Checkout the tag ───────────────────────────────────────────────
log "Checking out $LATEST_TAG"
git clean -fd \
    -e backend/staticfiles -e backend/mediafiles -e backend/dataschema_uploads \
    -e backend/.env -e 'backend/.env.*' \
    -e "deploy/${INSTANCE}/" -e .deployed-tag
git checkout -f "$LATEST_TAG"

# ── Load instance env (brand, app activation, domain) ──────────────
if [[ -f "$COMPOSE_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$COMPOSE_ENV_FILE"
    set +a
fi
# Backend uses DJANGO_BRAND; frontend uses VITE_BRAND (same id space).
BRAND="${DJANGO_BRAND:-$INSTANCE}"
prepare_nibras_runtime

# ── Frontend build (bake in the instance brand) ────────────────────
if [[ -f "$FRONTEND_DIR/package.json" ]] && command -v npm &>/dev/null; then
    log "Building frontend (brand=$BRAND)"
    cd "$FRONTEND_DIR"
    # HTML %VITE_*% is left literal when the var is absent (Vite html env
    # replacement). Brand copy lives in .env.instance.<brand>. The API base
    # stays relative so nginx on this host proxies /carbon-api/.
    BRAND_ENV="$FRONTEND_DIR/.env.instance.${BRAND}"
    {
        printf 'VITE_BRAND=%s\n' "$BRAND"
        printf 'VITE_API_BASE_URL=/carbon-api/\n'
        if [[ -f "$BRAND_ENV" ]]; then
            grep -E '^(VITE_PLATFORM_NAME|VITE_PLATFORM_SHORT|VITE_PLATFORM_TITLE|VITE_PLATFORM_TAGLINE|VITE_PLATFORM_DESCRIPTION|VITE_CANONICAL_URL|VITE_PULSE_INSTANCE_ID)=' "$BRAND_ENV" || true
        else
            log "WARNING: $BRAND_ENV missing — index.html will keep %VITE_*% placeholders"
        fi
    } > .env.production
    npm ci --silent 2>/dev/null
    npm run build
    cd "$APP_DIR"
fi

# ── Ensure host volume dirs (fresh checkouts need them) ────────────
log "Ensuring host volume dirs"
mkdir -p \
    "$APP_DIR/backend/staticfiles" \
    "$APP_DIR/backend/mediafiles" \
    "$APP_DIR/backend/dataschema_uploads"
chown -R 1000:1000 \
    "$APP_DIR/backend/staticfiles" \
    "$APP_DIR/backend/mediafiles" \
    "$APP_DIR/backend/dataschema_uploads" 2>/dev/null || true

# ── Build & restart backend ────────────────────────────────────────
log "Building & starting backend"
export IMAGE_TAG="$LATEST_TAG"
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$RUNTIME_COMPOSE" build --no-cache
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$RUNTIME_COMPOSE" up -d --force-recreate

# ── Wait for healthy backend ───────────────────────────────────────
log "Waiting for healthy backend"
HEALTHY=0
WAIT_TICKS=30
if [[ "$INSTANCE" == "nibras" ]]; then
    WAIT_TICKS=60
fi
for i in $(seq 1 "$WAIT_TICKS"); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/carbon-api/health/" >/dev/null 2>&1; then
        log "Backend healthy!"
        HEALTHY=1
        break
    fi
    if [[ $i -eq $WAIT_TICKS && "$INSTANCE" != "nibras" ]]; then
        log "WARNING: Backend did not become healthy in $((WAIT_TICKS * 2))s"
    fi
    sleep 2
done
if [[ "$INSTANCE" == "nibras" ]]; then
    if [[ "$HEALTHY" -ne 1 ]]; then
        log "ERROR: nibras backend did not become healthy; tag will not be recorded"
        exit 1
    fi
    assert_nibras_pack_gate
fi

# ── Per-instance app activation (ADR-0015) ─────────────────────────
if [[ -n "${APP_ACTIVE_SLUGS:-}" ]]; then
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --active "$APP_ACTIVE_SLUGS" || true
else
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --all || true
fi

# ── Reload nginx ───────────────────────────────────────────────────
log "Reloading nginx"
sudo nginx -t && sudo systemctl reload nginx

# Record successful deploy
echo "$LATEST_TAG" > "$DEPLOYED_TAG_FILE"

log "✓ Deploy complete: $LATEST_TAG"
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$RUNTIME_COMPOSE" ps
