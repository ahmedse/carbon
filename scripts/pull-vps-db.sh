#!/bin/bash
# Pull production data from the VPS into local dev databases.
#
# Usage:  bash scripts/pull-vps-db.sh [vps-ssh-host]
#         (default ssh host: carbon-prod)
#
# Requires:
#   - `ssh <host>` reachable (key auth or password)
#   - local DBs created first: sudo bash scripts/setup-local-db.sh
#   - VPS `sudo -u postgres pg_dump` works (peer auth on the VPS)
#
# Streams pg_dump straight into local Postgres — no temp files, no seeding.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$ROOT/backend/.env"
VPS_HOST="${1:-carbon-prod}"

DB_USER=$(grep -E '^DB_USER=' "$ENV" | cut -d= -f2)
DB_PASSWORD=$(grep -E '^DB_PASSWORD=' "$ENV" | cut -d= -f2)
export PGPASSWORD="$DB_PASSWORD"

[ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ] || {
  echo "ERROR: DB_USER / DB_PASSWORD missing from backend/.env" >&2
  exit 1
}

# prod DB (VPS) -> local dev DB (brand-derived)
PULL_MAP=(
  "carbon_prod carbon_dev"
  "nibras_prod nibras_dev"
)

for entry in "${PULL_MAP[@]}"; do
  set -- $entry
  prod="$1"; dev="$2"
  echo "==> Pulling $prod -> $dev"
  ssh "$VPS_HOST" \
    "sudo -u postgres pg_dump --no-owner --no-privileges --clean --if-exists -d $prod" \
    | psql -h localhost -U "$DB_USER" -v ON_ERROR_STOP=1 -d "$dev"
  echo "    $dev restored"
done

echo ""
echo "Done. Run migrations check:  .venv/bin/python backend/manage.py migrate --plan"
