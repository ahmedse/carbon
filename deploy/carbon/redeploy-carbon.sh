#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  redeploy-carbon.sh  — Pull latest code (or a specific tag) and redeploy
#                        carbon.clearturn.tech
#
#  Usage:
#    bash deploy/carbon/redeploy-carbon.sh           # deploy latest commit
#    bash deploy/carbon/redeploy-carbon.sh v1.0.0    # deploy exact tag
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$DEPLOY_DIR/../.." && pwd)"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"
FRONTEND_DIR="$PROJECT_ROOT/carbon-frontend"
ENV_FILE="$PROJECT_ROOT/backend/.env.carbon"

GREEN=$'\033[0;32m'; BLUE=$'\033[0;34m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
ok()   { echo -e "${GREEN}✓${NC}  $*"; }
info() { echo -e "${BLUE}▸${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
header() { echo; echo -e "${BLUE}══  $*  ══${NC}"; }

# Load env
[[ -f "$ENV_FILE" ]] || { echo "Missing env file: $ENV_FILE" >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a
INSTANCE="${INSTANCE:-carbon}"

# ── Resolve version ───────────────────────────────────────────────
if [[ "${1:-}" != "" ]]; then
    IMAGE_TAG="$1"
elif git describe --tags --match 'v*' --exact-match HEAD 2>/dev/null | grep -q .; then
    IMAGE_TAG="$(git describe --tags --match 'v*' --exact-match HEAD)"
else
    IMAGE_TAG="$(git rev-parse --short HEAD)"
fi
export IMAGE_TAG
info "Version tag: $IMAGE_TAG"

# ── 1. Pull / checkout ────────────────────────────────────────────
header "Git"
cd "$PROJECT_ROOT"
git fetch --tags
if [[ "${1:-}" != "" ]] && git rev-parse "$1" >/dev/null 2>&1; then
    git checkout "$1"
    ok "Checked out $1"
else
    git pull
    ok "Pulled latest"
fi

# ── 2. Build + restart backend ────────────────────────────────────
header "Backend"
info "Building image carbon-backend:${IMAGE_TAG} ..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build
docker tag "carbon-backend:${IMAGE_TAG}" "carbon-backend:latest" 2>/dev/null || true

info "Restarting container ..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
# remove any legacy docker-run container (no compose labels) so `up` can reuse the name
docker rm -f "${INSTANCE:-carbon}-backend" 2>/dev/null || true
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
ok "Backend running as carbon-backend:${IMAGE_TAG}"

# Prune old version images (keep last 5)
docker images carbon-backend --format '{{.Tag}}' \
  | grep -E '^v[0-9]+\.' \
  | sort -V \
  | head -n -5 \
  | xargs -r -I{} docker rmi "carbon-backend:{}" 2>/dev/null \
  && true

# ── 3. Frontend build ─────────────────────────────────────────────
header "Frontend"
cd "$FRONTEND_DIR"
cat > .env.production <<EOF
VITE_API_BASE_URL=/carbon-api/
EOF
npm ci --silent 2>/dev/null
npm run build
ok "Frontend built"

# ── 4. Reload nginx ───────────────────────────────────────────────
sudo nginx -t && sudo systemctl reload nginx
ok "Nginx reloaded"

# ── 5. Per-instance app activation (ADR-0015) ────────────────────
if [[ -n "${APP_ACTIVE_SLUGS:-}" ]]; then
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --active "$APP_ACTIVE_SLUGS" \
        && ok "Apps activated: $APP_ACTIVE_SLUGS"
else
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --all \
        && ok "All apps activated"
fi

echo
ok "Deployed ${IMAGE_TAG} → https://${DOMAIN}"
