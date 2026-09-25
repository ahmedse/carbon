#!/usr/bin/env bash
# Restore the 2026-09-25 nibras_dev snapshot taken before name-inferred
# gender and nationality. Test database only. See
# backups/snapshots/nibras_dev_20260925_before_name_inference.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP="$ROOT/backups/snapshots/nibras_dev_20260925_before_name_inference.dump"
EXPECTED_SHA="e52d87f92d410830c5d0b7aa4fcbf74254be4af69088d54247549f496dc31f9c"
ENV_FILE="$ROOT/backend/.env"

if [[ "${1:-}" != "--yes" ]]; then
  echo "Refusing to restore. This replaces nibras_dev with the 2026-09-25 snapshot."
  echo "Stop Django on :8009, then re-run: $0 --yes"
  exit 1
fi

if [[ ! -f "$DUMP" ]]; then
  echo "Missing dump: $DUMP"
  exit 1
fi

actual="$(sha256sum "$DUMP" | awk '{print $1}')"
if [[ "$actual" != "$EXPECTED_SHA" ]]; then
  echo "SHA-256 mismatch. Expected $EXPECTED_SHA"
  echo "Got      $actual"
  exit 1
fi

brand="$(grep -E '^DJANGO_BRAND=' "$ENV_FILE" | cut -d= -f2- | tr -d '[:space:]')"
db_name="$(grep -E '^DB_NAME=' "$ENV_FILE" | cut -d= -f2- | tr -d '[:space:]')"
if [[ "$brand" != "nibras" || "$db_name" != "nibras_dev" ]]; then
  echo "Refusing: backend/.env is brand=$brand db=$db_name, not nibras / nibras_dev."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export PGPASSWORD="$DB_PASSWORD"

echo "Restoring $DUMP into $DB_NAME ..."
pg_restore \
  --host="${DB_HOST:-localhost}" \
  --port="${DB_PORT:-5432}" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --clean --if-exists --no-owner --no-acl \
  "$DUMP"
echo "Restore finished. Expect 555 employees, 1 with gender, 60 with nationality."
