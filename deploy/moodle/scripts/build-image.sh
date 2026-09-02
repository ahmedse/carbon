#!/usr/bin/env bash
# Build qbank/moodle:<version> on the ONLINE dev machine.
# Expects the latest moodle-5.2.*.tgz (+ .sha256) in build/.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$STACK_DIR"

require_cmd docker
require_cmd tar

BUILD_DIR="$STACK_DIR/build"
mkdir -p "$BUILD_DIR"

tgz="$(ls -1 "$BUILD_DIR"/moodle-5.2.*.tgz 2>/dev/null | sort -V | tail -1 || true)"
[[ -n "$tgz" ]] || die "no moodle-5.2.*.tgz in build/ — download the latest 5.2.x from https://download.moodle.org/"

base="$(basename "$tgz" .tgz)"
version="${base#moodle-}"

# Verify sha256 if the .sha256 sidecar is present
if [[ -f "${tgz}.sha256" ]]; then
    ( cd "$BUILD_DIR" && sha256sum -c "${base}.tgz.sha256" ) || die "sha256 mismatch for ${base}.tgz"
else
    warn "no ${base}.tgz.sha256 — skipping checksum (NOT recommended)"
fi

# Extract (moodle tarball has a single top-level dir; strip it)
rm -rf "$BUILD_DIR/moodle-code"
mkdir -p "$BUILD_DIR/moodle-code"
tar -xzf "$tgz" -C "$BUILD_DIR/moodle-code" --strip-components=1
log "extracted ${base}"

IMAGE="qbank/moodle:${version}"
docker build --build-arg MOODLE_VERSION="$version" -t "$IMAGE" .
log "built ${IMAGE}"

# Point .env at the exact image tag
load_env
if grep -q '^MOODLE_IMAGE=' "$STACK_DIR/.env"; then
    sed -i "s|^MOODLE_IMAGE=.*|MOODLE_IMAGE=${IMAGE}|" "$STACK_DIR/.env"
else
    printf 'MOODLE_IMAGE=%s\n' "$IMAGE" >> "$STACK_DIR/.env"
fi
log ".env MOODLE_IMAGE=${IMAGE}"
