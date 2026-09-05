#!/usr/bin/env bash
# deploy-instance.sh — deploy ONE isolated Carbon instance (ADR-0015).
# Parameterized by deploy/<instance>/.env (see stamp-instance.sh).
#
# Usage (on the VPS, as a sudo-capable user):
#   bash deploy/<instance>/deploy-instance.sh <instance-name>
set -euo pipefail

INSTANCE="${1:?usage: deploy-instance.sh <instance-name>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTANCE_DIR="$ROOT/deploy/$INSTANCE"
TPL="$ROOT/deploy/instance"
ENV_FILE="$ROOT/backend/.env.$INSTANCE"
COMPOSE_FILE="$INSTANCE_DIR/docker-compose.yml"

GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; NC=$'\033[0m'
ok()  { echo -e "${GREEN}✓${NC}  $*"; }
die() { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }

# ── Env ───────────────────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE — copy deploy/$INSTANCE/.env there first"
grep -q "CHANGE_ME" "$ENV_FILE" && die "$ENV_FILE still has CHANGE_ME placeholders"

ENV_FILE_ABS="$ENV_FILE"  # absolute path survives the source below (env file redefines ENV_FILE as a compose-relative path)
set -a; source "$ENV_FILE_ABS"; set +a
for v in INSTANCE DOMAIN BACKEND_PORT DB_NAME DB_USER DB_PASSWORD SECRET_KEY FERNET_KEY TURNKEY_CALLBACK_SECRET; do
  [[ -n "${!v}" ]] || die "$v is not set in $ENV_FILE"
done
ok "Instance=$INSTANCE  domain=$DOMAIN  port=$BACKEND_PORT  db=$DB_NAME"

# ── Port collision guard (two instances must never share a port) ──
if command -v ss &>/dev/null && ss -ltn 2>/dev/null | grep -qE ":${BACKEND_PORT}\\b"; then
  die "Port $BACKEND_PORT is already in use — pick a free BACKEND_PORT in $ENV_FILE"
fi
if command -v docker &>/dev/null && docker ps --format '{{.Ports}}' 2>/dev/null | grep -qE ":${BACKEND_PORT}->"; then
  die "Port $BACKEND_PORT is published by another container — pick a free BACKEND_PORT"
fi

# ── Host PostgreSQL — OWN database per instance ───────────────────
if sudo -u postgres psql -lqt | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  ok "Database '$DB_NAME' already exists"
else
  sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
SQL
  ok "Database '$DB_NAME' + user created"
fi

# ── Build & start backend ─────────────────────────────────────────
ok "Building ${INSTANCE}-backend"
docker compose --env-file "$ENV_FILE_ABS" -f "$COMPOSE_FILE" build --no-cache
docker compose --env-file "$ENV_FILE_ABS" -f "$COMPOSE_FILE" up -d

# ── Migrate + per-instance app activation ─────────────────────────
ok "Migrating"
docker exec "${INSTANCE}-backend" python manage.py migrate --noinput || \
  die "migrate failed — see: docker logs ${INSTANCE}-backend"

if [[ -n "${APP_ACTIVE_SLUGS:-}" ]]; then
  ok "Activating apps: $APP_ACTIVE_SLUGS"
  docker exec "${INSTANCE}-backend" python manage.py activate_apps --active "$APP_ACTIVE_SLUGS"
else
  ok "No APP_ACTIVE_SLUGS — activating all apps"
  docker exec "${INSTANCE}-backend" python manage.py activate_apps --all
fi

# ── Render nginx config ───────────────────────────────────────────
ok "Rendering nginx.conf"
sed -e "s/__DOMAIN__/${DOMAIN}/g" -e "s/__INSTANCE__/${INSTANCE}/g" \
    "$TPL/nginx.conf.template" > "$INSTANCE_DIR/nginx.conf"

ok "Done."
echo
echo "Install the web server:"
echo "  sudo cp $INSTANCE_DIR/nginx.conf /etc/nginx/sites-available/$DOMAIN"
echo "  sudo ln -s /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/"
echo "  sudo certbot --nginx -d $DOMAIN"
echo "  sudo nginx -t && sudo systemctl reload nginx"
