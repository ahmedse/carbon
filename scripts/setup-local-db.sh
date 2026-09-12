#!/bin/bash
# One-time local Postgres setup for Carbon dev.
# Creates the `carbon_user` role + the two per-brand dev databases
# (carbon_dev, nibras_dev). Idempotent — safe to re-run.
#
# Run as:  sudo bash scripts/setup-local-db.sh
# (you'll type your own sudo password in the terminal)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$ROOT/backend/.env"

DB_USER=$(grep -E '^DB_USER=' "$ENV" | cut -d= -f2)
DB_PASSWORD=$(grep -E '^DB_PASSWORD=' "$ENV" | cut -d= -f2)

[ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] || {
  echo "ERROR: DB_USER / DB_PASSWORD missing from backend/.env" >&2
  exit 1
}

psql_su() { sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc "$1"; }

echo "==> Ensuring role '$DB_USER'"
if [ "$(psql_su "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")" = "1" ]; then
  echo "    role exists"
else
  psql_su "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD' CREATEDB"
  echo "    role created"
fi

for db in carbon_dev nibras_dev; do
  echo "==> Ensuring database '$db'"
  if [ "$(psql_su "SELECT 1 FROM pg_database WHERE datname='$db'")" = "1" ]; then
    echo "    database exists"
  else
    psql_su "CREATE DATABASE $db OWNER $DB_USER"
    echo "    database created"
  fi
done

echo ""
echo "Done. Local dev databases ready:"
echo "  carbon_dev  (brand=aastmt)"
echo "  nibras_dev  (brand=nibras)"
