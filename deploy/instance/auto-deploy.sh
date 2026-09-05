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
FRONTEND_DIR="$APP_DIR/carbon-frontend"

DEPLOY_LOCK="/tmp/${INSTANCE}-deploy.lock"
DEPLOYED_TAG_FILE="$APP_DIR/.deployed-tag"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

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
    -e backend/staticfiles -e backend/mediafiles -e backend/dataschema_uploads
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

# ── Frontend build (bake in the instance brand) ────────────────────
if [[ -f "$FRONTEND_DIR/package.json" ]] && command -v npm &>/dev/null; then
    log "Building frontend (brand=$BRAND)"
    cd "$FRONTEND_DIR"
    cat > .env.production <<EOF
VITE_BRAND=${BRAND}
VITE_API_BASE_URL=/carbon-api/
EOF
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
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" build --no-cache
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" up -d --force-recreate

# ── Wait for healthy backend ───────────────────────────────────────
log "Waiting for healthy backend"
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/carbon-api/health/" >/dev/null 2>&1; then
        log "Backend healthy!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "WARNING: Backend did not become healthy in 60s"
    fi
    sleep 2
done

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
docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" ps
