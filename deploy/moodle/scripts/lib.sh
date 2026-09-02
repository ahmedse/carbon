#!/usr/bin/env bash
# Shared helpers for the QBank Moodle stack scripts.
# Used identically on Ubuntu bare-metal (edOS) and Ubuntu WSL2 (dev).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"   # deploy/moodle

log()  { printf '\033[1;32m[+] %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

# Load .env into the shell (creating it from the example on first run).
load_env() {
    if [[ ! -f "$STACK_DIR/.env" ]]; then
        cp "$STACK_DIR/.env.example" "$STACK_DIR/.env"
        warn "created $STACK_DIR/.env from example — review before production use"
    fi
    set -a
    # shellcheck disable=SC1091
    . "$STACK_DIR/.env"
    set +a
}

# Pipefail-safe random hex (od reads exactly N bytes, no SIGPIPE race).
rand_hex() { od -An -tx1 -N "$1" /dev/urandom | tr -d ' \n'; }
rand_salt() { rand_hex 32; }   # 64 hex chars
# Moodle default password policy: >=8 chars, 1 upper, 1 lower, 1 digit, 1 special.
rand_pass() { printf 'Qb1!%s' "$(rand_hex 8)"; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }
