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
git clean -fd -e backend/staticfiles -e backend/mediafiles -e backend/dataschema_uploads
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
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/carbon-api/health/" > /dev/null 2>&1; then
        log "Backend healthy!"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "WARNING: Backend did not become healthy in 60s"
    fi
    sleep 2
done

log "Reloading nginx"
sudo nginx -t && sudo systemctl reload nginx

echo "$LATEST_TAG" > "$DEPLOYED_TAG_FILE"

log "✓ Deploy complete: $LATEST_TAG"
docker compose -f "$COMPOSE_FILE" ps
