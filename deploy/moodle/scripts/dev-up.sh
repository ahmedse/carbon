#!/usr/bin/env bash
# WSL2 dev quick start — one command from a clean checkout.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$STACK_DIR"

# Dev defaults (overridable): keep data project-local, assume no CA cert yet
export QBANK_ROOT="${QBANK_ROOT:-./data}"

"$SCRIPT_DIR/deploy.sh"

if ! grep -q "qbank.local" /etc/hosts 2>/dev/null; then
    warn "add to /etc/hosts:  127.0.0.1 qbank.local"
fi
log "Moodle: ${WWWROOT}   (accept the self-signed cert)"
