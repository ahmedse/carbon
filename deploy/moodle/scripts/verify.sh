#!/usr/bin/env bash
# Verify the release MANIFEST.sha256 signature + the manifest's own checksums.
# Run on the edOS workstation (or anywhere) before trusting the bundle.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$STACK_DIR/release"

log()  { printf '\033[1;32m[+] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[ -f MANIFEST.sha256 ]     || die "missing MANIFEST.sha256"
[ -f MANIFEST.sha256.sig ] || die "missing MANIFEST.sha256.sig (signature)"
[ -f qbank.pub ]           || die "missing qbank.pub (public key)"

log "1/2 — verifying Ed25519 signature…"
openssl pkeyutl -verify -pubin -inkey qbank.pub -rawin \
    -in MANIFEST.sha256 -sigfile MANIFEST.sha256.sig

log "2/2 — verifying file checksums…"
sha256sum -c MANIFEST.sha256

log "ALL GOOD — bundle is authentic and intact."
