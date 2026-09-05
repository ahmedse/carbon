#!/usr/bin/env bash
# stamp-instance.sh — create a new isolated deployment from deploy/instance/.
#
# One codebase, N isolated deployments (ADR-0015). This stamps deploy/<name>/
# with the parameterized compose/env/scripts — never fork the repo.
#
# Usage:
#   bash deploy/instance/stamp-instance.sh <instance-name>
set -euo pipefail

INSTANCE="${1:?usage: stamp-instance.sh <instance-name> (e.g. aast, nibras, healthy)}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TPL="$ROOT/deploy/instance"
DEST="$ROOT/deploy/$INSTANCE"

if [[ -d "$DEST" ]]; then
  echo "ERROR: $DEST already exists — not overwriting." >&2
  exit 1
fi
mkdir -p "$DEST"

cp "$TPL/docker-compose.yml"  "$DEST/docker-compose.yml"
cp "$TPL/deploy-instance.sh"  "$DEST/deploy-instance.sh"
cp "$TPL/auto-deploy.sh"      "$DEST/auto-deploy.sh"
cp "$TPL/setup-auto-deploy.sh" "$DEST/setup-auto-deploy.sh"
chmod +x "$DEST/deploy-instance.sh" "$DEST/auto-deploy.sh" "$DEST/setup-auto-deploy.sh"

sed -e "s/^INSTANCE=.*/INSTANCE=${INSTANCE}/" \
    -e "s|^ENV_FILE=.*|ENV_FILE=../../backend/.env.${INSTANCE}|" \
    "$TPL/.env.template" > "$DEST/.env"

echo "Stamped: $DEST"
echo
echo "Next steps:"
echo "  1. Edit  $DEST/.env  (domain, DB creds, secret key, APP_ACTIVE_SLUGS)"
echo "  2. Copy  cp $DEST/.env  $ROOT/backend/.env.$INSTANCE"
echo "  3. Deploy bash $DEST/deploy-instance.sh $INSTANCE"
echo "  4. Auto  sudo bash $DEST/setup-auto-deploy.sh $INSTANCE /srv/$INSTANCE <port> <user>"
echo "     (polls for ${INSTANCE}-v* tags every 2 min — see README)"
