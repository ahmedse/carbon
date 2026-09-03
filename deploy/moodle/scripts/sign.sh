#!/usr/bin/env bash
# Sign the release MANIFEST.sha256 with an Ed25519 key (OpenSSL, no sudo).
#
# Why OpenSSL Ed25519 instead of minisign: minisign is the canonical tool for
# this stack, but it needs `sudo apt install minisign` (no passwordless sudo on
# dev). OpenSSL Ed25519 gives the SAME guarantee — tamper-evident, authenticated
# integrity — with zero extra installs. If minisign is later available, use it:
#     minisign -S -m release/MANIFEST.sha256
#
# Layout:
#   .sign/ed25519.key   <- SECRET key (stays on the ONLINE dev machine, gitignored)
#   release/qbank.pub   <- PUBLIC key (travels with the bundle to edOS)
#   release/MANIFEST.sha256.sig  <- signature (travels with the bundle)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SIGN_DIR="$STACK_DIR/.sign"
KEY="$SIGN_DIR/ed25519.key"
PUB="$STACK_DIR/release/qbank.pub"
MANIFEST="$STACK_DIR/release/MANIFEST.sha256"
SIG="$MANIFEST.sig"

log()  { printf '\033[1;32m[+] %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$MANIFEST" ] || die "no $MANIFEST — run bundle.sh first"
command -v openssl >/dev/null 2>&1 || die "missing openssl"

mkdir -p "$SIGN_DIR" "$STACK_DIR/release"

# Generate the keypair once; reuse on later bundles.
if [ ! -f "$KEY" ]; then
    log "generating Ed25519 keypair…"
    openssl genpkey -algorithm ed25519 -out "$KEY" 2>/dev/null
    chmod 600 "$KEY"
fi

log "signing $MANIFEST"
openssl pkeyutl -sign -inkey "$KEY" -rawin -in "$MANIFEST" -out "$SIG" 2>/dev/null

log "exporting public key to $PUB"
openssl pkey -in "$KEY" -pubout -out "$PUB" 2>/dev/null

log "done."
warn "secret key: $KEY  (KEEP ON DEV / back up securely — never ship to edOS)"
log "verification command (on edOS):"
printf '    openssl pkeyutl -verify -pubin -inkey qbank.pub -rawin -in MANIFEST.sha256 -sigfile MANIFEST.sha256.sig\n'
