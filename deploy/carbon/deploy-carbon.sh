#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  deploy-carbon.sh  — Full first-time deployment of Carbon Data Trust Platform
#                      carbon.clearturn.tech  →  /srv/carbon
#
#  Run this script as a user with sudo rights on the production VPS:
#    cd /srv/carbon
#    bash deploy/carbon/deploy-carbon.sh
#
#  What this does:
#    1. Preflight: load & validate env
#    2. Create host PostgreSQL DB + user (OWN db — separate from gigacast)
#    3. Allow Docker to connect to host Postgres
#    4. Build & start backend Docker container (Gunicorn)
#    5. Build React frontend
#    6. Install nginx site config
#    7. Obtain Let's Encrypt TLS certificate
#
#  NOTE: This stack is COMPLETELY INDEPENDENT of gigacast.
#        It has its own DB, its own Docker container, its own nginx config.
# ─────────────────────────────────────────────────────────────────────────────
set -e
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$DEPLOY_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/backend/.env.carbon"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"
FRONTEND_DIR="$PROJECT_ROOT/carbon-frontend"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; NC=$'\033[0m'

ok()   { echo -e "${GREEN}✓${NC}  $*"; }
info() { echo -e "${BLUE}▸${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
die()  { echo -e "${RED}✗  $*${NC}" >&2; exit 1; }

header() {
    echo; echo -e "${BLUE}══════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $*${NC}"
    echo -e "${BLUE}══════════════════════════════════════════${NC}"
}

# ── 1. Env file ───────────────────────────────────────────────────
header "Environment"

[[ -f "$ENV_FILE" ]] || {
    cp "$DEPLOY_DIR/.env.carbon.example" "$ENV_FILE"
    die "Env file created at $ENV_FILE — fill in all CHANGE_ME values then re-run"
}

grep -q "CHANGE_ME" "$ENV_FILE" && \
    die "Still has CHANGE_ME placeholders in $ENV_FILE — fill them in first"

# Source all config from the env file — no hardcoded values
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Validate required vars
for v in DOMAIN BACKEND_PORT DB_NAME DB_USER DB_PASSWORD DJANGO_SECRET_KEY; do
    [[ -n "${!v}" ]] || die "$v is not set in $ENV_FILE"
done
INSTANCE="${INSTANCE:-carbon}"

NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"
NGINX_SRC="$DEPLOY_DIR/nginx.conf"

ok "Config loaded: domain=$DOMAIN  port=$BACKEND_PORT  db=$DB_NAME"

# ── 2. Host PostgreSQL: create DB + user ─────────────────────────
header "PostgreSQL — host DB setup"

PG_VERSION=$(sudo -u postgres psql --version | grep -oE '[0-9]+' | head -1)
info "Detected PostgreSQL $PG_VERSION"

if sudo -u postgres psql -lqt | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
    ok "Database '$DB_NAME' already exists"
else
    info "Creating database '$DB_NAME' and user '$DB_USER'..."
    sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL
    ok "Database and user created"
fi

# ── 3. Allow Docker bridge → host Postgres ────────────────────────
header "PostgreSQL — allow Docker network access"

DOCKER_SUBNET="172.17.0.0/16"
PG_HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"

if [[ ! -f "$PG_HBA" ]]; then
    PG_HBA=$(find /etc/postgresql -name pg_hba.conf 2>/dev/null | head -1)
    [[ -z "$PG_HBA" ]] && die "Cannot find pg_hba.conf — add Docker subnet manually"
fi

HBA_LINE="host    ${DB_NAME}    ${DB_USER}    ${DOCKER_SUBNET}    scram-sha-256"
if grep -q "${DB_NAME}.*${DOCKER_SUBNET}" "$PG_HBA" 2>/dev/null; then
    ok "Docker subnet rule for ${DB_NAME} already in pg_hba.conf"
else
    info "Adding Docker bridge subnet rule for ${DB_NAME} to pg_hba.conf..."
    echo "$HBA_LINE" | sudo tee -a "$PG_HBA" >/dev/null
    ok "Added: $HBA_LINE"
fi

PG_CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"
if ! grep -q "listen_addresses.*\*\|listen_addresses.*172\.17" "$PG_CONF" 2>/dev/null; then
    info "Configuring postgres to listen on all interfaces..."
    sudo sed -i "s/^#*listen_addresses\s*=.*/listen_addresses = '*'/" "$PG_CONF"
    ok "listen_addresses set to '*'"
else
    ok "postgres listen_addresses already configured"
fi

info "Reloading PostgreSQL..."
sudo systemctl reload postgresql || sudo pg_ctlcluster "$PG_VERSION" main reload
ok "PostgreSQL reloaded"

# ── 4. Backend Docker container ───────────────────────────────────
header "Backend — Docker build & start"

info "Creating volume directories on host..."
mkdir -p \
    "$PROJECT_ROOT/backend/staticfiles" \
    "$PROJECT_ROOT/backend/mediafiles" \
    "$PROJECT_ROOT/backend/dataschema_uploads"
# Set ownership to allow Docker container (app user, uid 1000) to write
chown -R 1000:1000 \
    "$PROJECT_ROOT/backend/staticfiles" \
    "$PROJECT_ROOT/backend/mediafiles" \
    "$PROJECT_ROOT/backend/dataschema_uploads" 2>/dev/null || true
ok "Volume directories ready"

if docker ps -a --format '{{.Names}}' | grep -q "^carbon-backend$"; then
    info "Stopping old container..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down
fi

info "Building Docker image..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --no-cache

info "Starting container..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

info "Waiting for container to start (30s max)..."
for i in $(seq 1 30); do
    sleep 1
    if docker ps --filter "name=carbon-backend" --filter "status=running" | grep -q carbon-backend; then
        ok "Container is running"
        break
    fi
    [[ $i == 30 ]] && { docker logs carbon-backend --tail 40; die "Container failed to start"; }
done

sleep 3
if curl -sf "http://127.0.0.1:${BACKEND_PORT}/carbon-api/health/" >/dev/null 2>&1; then
    ok "Backend responding on port $BACKEND_PORT"
else
    warn "Backend not yet responding on port $BACKEND_PORT (may still be running migrations)"
fi

# ── 4b. Per-instance app activation (ADR-0015) ────────────────────
header "App activation"
if [[ -n "${APP_ACTIVE_SLUGS:-}" ]]; then
    ok "Activating apps: $APP_ACTIVE_SLUGS"
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --active "$APP_ACTIVE_SLUGS"
else
    ok "No APP_ACTIVE_SLUGS — activating all apps"
    docker exec "${INSTANCE}-backend" python manage.py activate_apps --all
fi

# ── 5. Frontend build ─────────────────────────────────────────────
header "Frontend — npm build"

cd "$FRONTEND_DIR"

# Create production .env for the build
cat > .env.production <<EOF
VITE_API_BASE_URL=/carbon-api/
EOF

info "Installing npm dependencies..."
npm ci --silent

info "Building React app..."
npm run build

ok "Frontend built → $FRONTEND_DIR/dist"
cd "$PROJECT_ROOT"

# ── 6. Nginx ─────────────────────────────────────────────────────
header "Nginx — site configuration"

info "Installing HTTP bootstrap config (for cert acquisition)..."
sudo tee "$NGINX_CONF" >/dev/null <<NGINX_HTTP
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}
NGINX_HTTP

[[ -L "/etc/nginx/sites-enabled/${DOMAIN}" ]] || \
    sudo ln -s "$NGINX_CONF" "/etc/nginx/sites-enabled/${DOMAIN}"

sudo nginx -t || die "nginx HTTP bootstrap config test failed"
sudo systemctl reload nginx
ok "Nginx HTTP bootstrap active"

# ── 7. TLS certificate ────────────────────────────────────────────
header "TLS — Let's Encrypt"

if command -v certbot >/dev/null; then
    if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
        CERTBOT_EMAIL="admin@clearturn.tech"
        info "Obtaining certificate for $DOMAIN (email: $CERTBOT_EMAIL)..."
        sudo certbot certonly --webroot -w /var/www/html \
            -d "$DOMAIN" --non-interactive --agree-tos -m "$CERTBOT_EMAIL"
        ok "Certificate obtained"
    else
        ok "Certificate already exists for $DOMAIN"
    fi

    info "Installing full HTTPS nginx config..."
    sudo bash -c "sed \
        -e 's|/srv/carbon/|${PROJECT_ROOT}/|g' \
        -e 's|127\.0\.0\.1:8002|127.0.0.1:${BACKEND_PORT}|g' \
        -e 's|carbon\.clearturn\.tech|${DOMAIN}|g' \
        -e 's|    # ssl_certificate |    ssl_certificate |g' \
        -e 's|    # ssl_certificate_key |    ssl_certificate_key |g' \
        -e 's|    # include /etc/letsencrypt|    include /etc/letsencrypt|g' \
        -e 's|    # ssl_dhparam |    ssl_dhparam |g' \
        \"$NGINX_SRC\" > \"$NGINX_CONF\""

    sudo nginx -t || die "nginx HTTPS config test failed — check $NGINX_CONF"
    sudo systemctl reload nginx
    ok "Nginx reloaded with full HTTPS config"
else
    warn "certbot not found — HTTP-only config is active"
    warn "Install certbot then run: sudo certbot certonly --webroot -w /var/www/html -d ${DOMAIN}"
    warn "Then re-run this script to install the full HTTPS nginx config"
fi

# ── Done ──────────────────────────────────────────────────────────
header "Deployment complete"

ok "Domain  : https://${DOMAIN}"
ok "Backend : http://127.0.0.1:${BACKEND_PORT}  (container: ${INSTANCE}-backend)"
ok "DB      : postgres://localhost/${DB_NAME}  (host, via host.docker.internal)"
ok "Frontend: ${FRONTEND_DIR}/dist"
echo
info "Useful commands:"
echo "  docker logs ${INSTANCE}-backend -f"
echo "  docker compose --env-file $ENV_FILE -f $COMPOSE_FILE down"
echo "  docker compose --env-file $ENV_FILE -f $COMPOSE_FILE up -d"
echo "  cd $FRONTEND_DIR && npm run build"
echo "  sudo systemctl reload nginx"
echo
