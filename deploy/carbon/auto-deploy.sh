#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Pull-based auto-deploy for Carbon Data Trust Platform.
# Runs on the VPS via systemd timer every 2 minutes.
# Checks for new git tags and deploys if a newer tag is found.
#
# Needs: APP_DIR, BACKEND_PORT set in /etc/carbon-deploy.env
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

CONFIG="/etc/carbon-deploy.env"
if [[ ! -f "$CONFIG" ]]; then
    echo "ERROR: $CONFIG not found" >&2
    exit 1
fi
source "$CONFIG"
APP_DIR="${APP_DIR:?APP_DIR must be set in $CONFIG}"
BACKEND_PORT="${BACKEND_PORT:-8002}"
ENV_FILE="$APP_DIR/backend/.env.carbon"
COMPOSE_FILE="$APP_DIR/deploy/carbon/docker-compose.yml"
FRONTEND_DIR="$APP_DIR/carbon-frontend"

DEPLOY_LOCK="/tmp/carbon-deploy.lock"
DEPLOYED_TAG_FILE="$APP_DIR/.deployed-tag"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Packs the carbon cell may load, and the packs it must never see.
CARBON_RUNTIME_PACKS=(carbon aast-med _platform)
CARBON_FORBIDDEN_PACKS=(nibras eduos medos tectona)

# Carbon boots domain_packs/carbon (+ aast-med + _platform). A foreign pack
# must never be mounted, so the cell cannot fall back to another brand.
# Mirrors prepare_nibras_runtime in deploy/instance/auto-deploy.sh without
# touching that shared (nibras-production) script.
prepare_carbon_runtime() {
    local src_root="$APP_DIR/domain_packs"
    local dest="$APP_DIR/.runtime-packs"
    local name pack_id

    if [[ ! -f "$src_root/carbon/pack.yaml" ]]; then
        log "ERROR: $src_root/carbon/pack.yaml missing — refusing to start"
        exit 1
    fi
    pack_id=$(awk '/^id:[[:space:]]*/ { print $2; exit }' "$src_root/carbon/pack.yaml")
    if [[ "$pack_id" != "carbon" ]]; then
        log "ERROR: resolved pack id is '${pack_id:-missing}', refusing to start"
        exit 1
    fi

    rm -rf "$dest"
    mkdir -p "$dest"
    for name in "${CARBON_RUNTIME_PACKS[@]}"; do
        if [[ ! -d "$src_root/$name" ]]; then
            log "ERROR: required pack dir $src_root/$name missing — refusing to start"
            exit 1
        fi
        cp -a "$src_root/$name" "$dest/$name"
    done
    for name in "${CARBON_FORBIDDEN_PACKS[@]}"; do
        if [[ -e "$dest/$name" ]]; then
            log "ERROR: runtime pack dir contains forbidden pack $name"
            exit 1
        fi
    done
    if [[ ! -f "$dest/carbon/pack.yaml" ]]; then
        log "ERROR: carbon pack did not land in $dest"
        exit 1
    fi

    export DOMAIN_PACKS_MOUNT="$dest"
    local built_at
    built_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    export CARBON_RELEASE_TAG="$LATEST_TAG"
    export CARBON_IMAGE_BUILT_AT="$built_at"
    export CARBON_DEPLOYED_AT="$built_at"
    log "Carbon runtime packs: $dest (carbon + aast-med + _platform)"
}

# After the container is healthy, prove the running cell loaded no foreign
# pack. A failed gate aborts before .deployed-tag is stamped.
assert_carbon_pack_gate() {
    local body
    body=$(curl -sf -H 'X-Forwarded-Proto: https' \
        "http://127.0.0.1:${BACKEND_PORT}/carbon-api/health/") || {
        log "ERROR: carbon health document unavailable for the pack gate"
        exit 1
    }
    HEALTH_JSON="$body" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["HEALTH_JSON"])
rel = data.get("release") or {}
brand = rel.get("process_brand")
pack = rel.get("pack")
loaded = list(rel.get("loaded_packs") or [])
catalogs = list(rel.get("catalogs") or [])
extra = list(rel.get("extra_packs") or [])
allowed = {"carbon", "aast-med", "_platform"}
forbidden = {"nibras", "eduos", "medos", "tectona"}
seen = set(loaded) | set(catalogs) | set(extra)
problems = []
if brand != "aastmt":
    problems.append(f"process_brand={brand!r}")
if pack != "carbon":
    problems.append(f"pack={pack!r}")
if extra != ["aast-med"]:
    problems.append(f"extra_packs={extra!r}")
unknown = sorted(seen - allowed)
if unknown:
    problems.append(f"unexpected packs loaded: {unknown}")
hit = sorted(seen & forbidden)
if hit:
    problems.append(f"forbidden packs loaded: {hit}")
if not rel.get("tag"):
    problems.append("release tag is empty")
if not rel.get("pulse_enabled"):
    problems.append("pulse_enabled is not true")
if problems:
    sys.exit("carbon pack gate failed: " + "; ".join(problems))
print("carbon pack gate ok", rel.get("tag"), pack, rel.get("pack_version"))
PY
}

if [[ -f "$DEPLOY_LOCK" ]]; then
    log "Deploy already in progress (lock: $DEPLOY_LOCK), skipping."
    exit 0
fi

cleanup() { rm -f "$DEPLOY_LOCK"; }
trap cleanup EXIT
touch "$DEPLOY_LOCK"

cd "$APP_DIR"

git fetch origin --tags --force --quiet 2>/dev/null

LATEST_TAG=$(git tag -l 'v*' --sort=-version:refname | head -1)
if [[ -z "$LATEST_TAG" ]]; then
    log "No version tags found."
    exit 0
fi

CURRENT_TAG=""
if [[ -f "$DEPLOYED_TAG_FILE" ]]; then
    CURRENT_TAG=$(cat "$DEPLOYED_TAG_FILE")
fi

if [[ "$LATEST_TAG" == "$CURRENT_TAG" ]]; then
    exit 0
fi

log "New tag detected: $LATEST_TAG (current: ${CURRENT_TAG:-none})"

log "Checking out $LATEST_TAG"
git clean -fd -e backend/staticfiles -e backend/mediafiles -e backend/dataschema_uploads \
    -e backend/.env -e 'backend/.env.*' -e 'deploy/carbon/' -e .deployed-tag
git checkout -f "$LATEST_TAG"

if [[ -f "$FRONTEND_DIR/package.json" ]] && command -v npm &>/dev/null; then
    log "Building frontend"
    cd "$FRONTEND_DIR"
    cat > .env.production <<EOF
VITE_API_BASE_URL=/carbon-api/
EOF
    npm ci --silent 2>/dev/null
    npm run build
    cd "$APP_DIR"
fi

log "Ensuring host volume dirs"
mkdir -p \
    "$APP_DIR/backend/staticfiles" \
    "$APP_DIR/backend/mediafiles" \
    "$APP_DIR/backend/dataschema_uploads"
chown -R 1000:1000 \
    "$APP_DIR/backend/staticfiles" \
    "$APP_DIR/backend/mediafiles" \
    "$APP_DIR/backend/dataschema_uploads" 2>/dev/null || true

log "Preparing isolated runtime packs"
prepare_carbon_runtime

log "Building & starting backend"
export IMAGE_TAG="$LATEST_TAG"
if [[ -f "$ENV_FILE" ]]; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --no-cache
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --force-recreate
else
    docker compose -f "$COMPOSE_FILE" build --no-cache
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate
fi

log "Waiting for healthy backend"
for i in $(seq 1 30); do
    if curl -sf -H 'X-Forwarded-Proto: https' \
        "http://127.0.0.1:${BACKEND_PORT}/carbon-api/health/" > /dev/null 2>&1; then
        log "Backend healthy!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "WARNING: Backend did not become healthy in 60s"
    fi
    sleep 2
done

log "Verifying pack isolation"
assert_carbon_pack_gate

log "Activating apps (ADR-0015)"
if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi
INSTANCE="${INSTANCE:-carbon}"
if [[ -n "${APP_ACTIVE_SLUGS:-}" ]]; then
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --active "$APP_ACTIVE_SLUGS" || true
else
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --all || true
fi

log "Reloading nginx"
sudo nginx -t && sudo systemctl reload nginx

echo "$LATEST_TAG" > "$DEPLOYED_TAG_FILE"

log "✓ Deploy complete: $LATEST_TAG"
docker compose -f "$COMPOSE_FILE" ps
