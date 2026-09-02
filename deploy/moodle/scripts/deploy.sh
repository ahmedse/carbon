#!/usr/bin/env bash
# Deploy on the air-gapped workstation (or WSL dev):
#   verify manifest → docker load → TLS cert → render config → up → install → cron (opt).
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$STACK_DIR"

require_cmd docker
require_cmd openssl

load_env

# 0. verify bundle manifest if a release/ dir is present
if [[ -f release/MANIFEST.sha256 ]]; then
    log "verifying release manifest…"
    ( cd release && sha256sum -c MANIFEST.sha256 ) || die "manifest verification FAILED — aborting"
    # signature check (if minisign present and .sig present)
    if [[ -f release/MANIFEST.sha256.sig ]] && command -v minisign >/dev/null 2>&1; then
        minisign -V -m release/MANIFEST.sha256 -x release/MANIFEST.sha256.sig -q || die "signature verification FAILED"
    fi
fi

# 1. load images if present in release/images
if ls release/images/*.tar.gz >/dev/null 2>&1; then
    log "loading images…"
    gunzip -c release/images/moodle.tar.gz   | docker load
    gunzip -c release/images/postgres.tar.gz | docker load
fi

# 2. TLS cert (offline-CA cert on edOS; self-signed bootstrap otherwise)
if [[ ! -f tls/tls.crt || ! -f tls/tls.key ]]; then
    warn "no tls/tls.crt + tls.key — generating self-signed DEV cert"
    warn "(production: install the offline-CA cert from EDOS §7 and re-run)"
    mkdir -p tls
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -days 3650 -nodes \
        -subj "/CN=${MOODLE_DOMAIN}" \
        -addext "subjectAltName=DNS:${MOODLE_DOMAIN},DNS:localhost" \
        -keyout tls/tls.key -out tls/tls.crt
    chmod 600 tls/tls.key
fi

# 3. render config.php
"$SCRIPT_DIR/render-config.sh"

# 4. bring up the stack
docker compose up -d

# 5. first-run Moodle install (idempotent — skips if already installed)
if docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_name='mdl_config'" 2>/dev/null | grep -q 1; then
    log "Moodle already installed — skipping install.php"
else
    log "installing Moodle…"
    docker compose exec -T moodle php admin/cli/install.php \
        --chmod=2770 --lang=en \
        --wwwroot="$WWWROOT" --dataroot=/var/www/moodledata \
        --dbtype=pgsql --dbhost=db --dbname="$POSTGRES_DB" \
        --dbuser="$POSTGRES_USER" --dbpass="$POSTGRES_PASSWORD" --prefix=mdl_ \
        --fullname="$MOODLE_SITE_NAME" --shortname="qbank" \
        --adminuser="$MOODLE_ADMIN_USER" --adminpass="$MOODLE_ADMIN_PASS" \
        --adminemail="$MOODLE_ADMIN_EMAIL" \
        --non-interactive --agree-license
    docker compose exec -T moodle php admin/cli/purge_caches.php
    log "Moodle installed."
fi

# 6. optional: install host systemd cron timer
if [[ "${1:-}" == "--cron" ]]; then
    log "installing host cron timer…"
    sed "s|@STACK_DIR@|$STACK_DIR|" "$STACK_DIR/cron/qbank-cron.service" \
        > /etc/systemd/system/qbank-cron.service
    cp "$STACK_DIR/cron/qbank-cron.timer" /etc/systemd/system/qbank-cron.timer
    systemctl daemon-reload
    systemctl enable --now qbank-cron.timer
    log "cron timer enabled"
fi

log "done. Moodle at ${WWWROOT}"
