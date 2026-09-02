#!/usr/bin/env bash
# Assemble the air-gapped release bundle on the ONLINE dev machine:
#   docker save both images, tar the stack source, write MANIFEST.sha256.
# Sign it separately:  minisign -S -m release/MANIFEST.sha256
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$STACK_DIR"

require_cmd docker

OUT="${1:-$STACK_DIR/release}"
load_env

mkdir -p "$OUT/images" "$OUT/moodle"

log "saving images…"
docker save "${MOODLE_IMAGE}"   | gzip -9 > "$OUT/images/moodle.tar.gz"
docker save "${POSTGRES_IMAGE}" | gzip -9 > "$OUT/images/postgres.tar.gz"

log "tarring stack source…"
tar -czf "$OUT/qbank-stack.tar.gz" \
    --exclude='.env' --exclude='config' --exclude='tls' --exclude='data' \
    --exclude='build' --exclude='release' \
    -C "$STACK_DIR" .

# Carry the moodle tarball as source-of-truth (matches EDOS §10 bundle layout)
if ls build/moodle-*.tgz >/dev/null 2>&1; then
    cp build/moodle-*.tgz         "$OUT/moodle/" 2>/dev/null || true
    cp build/*.tgz.sha256         "$OUT/moodle/" 2>/dev/null || true
fi

log "writing MANIFEST.sha256…"
( cd "$OUT" && find . -type f ! -name 'MANIFEST.sha256' ! -name 'MANIFEST.sha256.sig' -print0 \
    | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )

log "bundle ready at $OUT"
warn "sign it:  minisign -S -m $OUT/MANIFEST.sha256"
