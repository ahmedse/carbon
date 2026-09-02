#!/usr/bin/env bash
# Deploy on the air-gapped workstation (or WSL dev).
#
# Flow (canonical Moodle):
#   1. verify release manifest (if present) -> docker load
#   2. TLS cert (offline-CA cert on edOS; self-signed bootstrap otherwise)
#   3. start db, wait healthy
#   4. if config/config.php missing -> run admin/cli/install.php in a one-off
#      container (it WRITES config.php itself and refuses if one exists),
#      capture the generated config.php, insert air-gap hardening, persist salt.
#   5. docker compose up -d (now mounts the hardened config.php)
#   6. verify + purge caches + optional admin re-hash + cron timer (--cron)
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$STACK_DIR"

require_cmd docker
require_cmd openssl

load_env

# Generate + persist any missing secrets before first use.
_ensure_secrets() {
    local changed=0
    if [[ -z "${POSTGRES_PASSWORD:-}" || "$POSTGRES_PASSWORD" == "__CHANGE_ME__" ]]; then
        POSTGRES_PASSWORD="$(rand_hex 16)"
        printf 'POSTGRES_PASSWORD=%s\n' "$POSTGRES_PASSWORD" >> "$STACK_DIR/.env"
        changed=1
    fi
    if [[ -z "${MOODLE_ADMIN_PASS:-}" || "$MOODLE_ADMIN_PASS" == "__CHANGE_ME__" ]]; then
        MOODLE_ADMIN_PASS="$(rand_pass)"
        printf 'MOODLE_ADMIN_PASS=%s\n' "$MOODLE_ADMIN_PASS" >> "$STACK_DIR/.env"
        changed=1
    fi
    if [[ "$changed" == "1" ]]; then
        set -a; . "$STACK_DIR/.env"; set +a
    fi
}
_ensure_secrets

# Host-side data root (absolute, or relative to the stack dir)
case "$QBANK_ROOT" in
    /*) HOST_ROOT="$QBANK_ROOT" ;;
    *)  HOST_ROOT="$STACK_DIR/$QBANK_ROOT" ;;
esac

# --- 0. verify + load a release bundle if present -------------------------
if [[ -f release/MANIFEST.sha256 ]]; then
    log "verifying release manifest…"
    ( cd release && sha256sum -c MANIFEST.sha256 ) || die "manifest verification FAILED — aborting"
    if [[ -f release/MANIFEST.sha256.sig ]] && command -v minisign >/dev/null 2>&1; then
        minisign -V -m release/MANIFEST.sha256 -x release/MANIFEST.sha256.sig -q \
            || die "signature verification FAILED"
    fi
fi
if ls release/images/*.tar.gz >/dev/null 2>&1; then
    log "loading images…"
    gunzip -c release/images/moodle.tar.gz   | docker load
    gunzip -c release/images/postgres.tar.gz | docker load
fi

# --- 1. TLS cert ----------------------------------------------------------
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

# --- 2. DB up -------------------------------------------------------------
mkdir -p "$HOST_ROOT/moodledata"
# Docker creates missing bind-mount parents as root; keep the data ROOT host-owned
# (moodledata itself stays www-data-owned). Non-recursive chown via the container.
if [[ "$(stat -c %U "$HOST_ROOT" 2>/dev/null)" != "$(id -un)" ]]; then
    docker run --rm --entrypoint sh \
        -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
        -v "$HOST_ROOT:/dataroot:rw" \
        "$MOODLE_IMAGE" \
        -c 'chown "$HOST_UID:$HOST_GID" /dataroot'
fi
docker compose up -d db
docker compose ps db

MARKER="Air-gap hardening (inserted by scripts/deploy.sh)"
INSTALLED_NOW=0

# --- 3. Install phase (only when config.php does not exist yet) -----------
if [[ -f config/config.php ]]; then
    log "config/config.php exists — skipping install"
else
    # dataroot must be writable by the container's www-data (uid 33)
    chown -R 33:33 "$HOST_ROOT/moodledata" 2>/dev/null \
        || warn "could not chown dataroot to uid 33 — install may fail"
    mkdir -p config

    log "installing Moodle via CLI (no config yet)…"
    docker run --rm \
        --network "${COMPOSE_PROJECT_NAME:-qbank}_default" \
        --entrypoint sh \
        -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
        -v "$STACK_DIR/config:/write:rw" \
        -v "$HOST_ROOT/moodledata:/var/www/moodledata" \
        "$MOODLE_IMAGE" \
        -c "php admin/cli/install.php \
                --chmod=2770 --lang=en \
                --wwwroot='$WWWROOT' --dataroot=/var/www/moodledata \
                --dbtype=pgsql --dbhost=db --dbname='$POSTGRES_DB' \
                --dbuser='$POSTGRES_USER' --dbpass='$POSTGRES_PASSWORD' --prefix=mdl_ \
                --fullname='$MOODLE_SITE_NAME' --shortname=qbank \
                --adminuser='$MOODLE_ADMIN_USER' --adminpass='$MOODLE_ADMIN_PASS' \
                --adminemail='$MOODLE_ADMIN_EMAIL' \
                --non-interactive --agree-license \
            && cp /var/www/html/config.php /write/config.php \
            && chmod 600 /write/config.php \
            && chown \"\$HOST_UID:\$HOST_GID\" /write/config.php \
            && chown -R 33:33 /var/www/moodledata"
    [[ -f config/config.php ]] || die "install.php did not produce config/config.php"
    INSTALLED_NOW=1
fi

# --- 3b. Idempotent hardening injection -----------------------------------
# Insert the air-gap hardening block before the setup.php require. If this was
# a fresh install and the installer omitted a salt, generate + persist one and
# remember to re-hash the admin password afterwards.
if ! grep -qF "$MARKER" config/config.php; then
    if grep -q 'passwordsaltmain' config/config.php; then
        log "installer generated a salt — keeping it"
        QBANK_ADD_SALT=0
    elif [[ "$INSTALLED_NOW" == "1" ]]; then
        SALT="$(grep '^PASSWORDSALTMAIN=' "$STACK_DIR/.env" | cut -d= -f2)"
        if [[ -z "$SALT" || "$SALT" == "__CHANGE_ME__" ]]; then
            SALT="$(rand_hex 32)"
            printf 'PASSWORDSALTMAIN=%s\n' "$SALT" >> "$STACK_DIR/.env"
        fi
        export QBANK_SALT="$SALT"
        QBANK_ADD_SALT=1
    else
        # pre-existing config without a salt and no fresh install: leave hashes alone
        QBANK_ADD_SALT=0
        warn "config.php has no passwordsaltmain and was not freshly installed — leaving as-is"
    fi
    export QBANK_MARKER="$MARKER" QBANK_ADD_SALT
    python3 - <<'PY'
import os
path = "config/config.php"
s = open(path).read()
x = open("harden/config-extra.php").read()
if os.environ.get("QBANK_ADD_SALT") == "1":
    x += "\n$CFG->passwordsaltmain = '%s';\n" % os.environ["QBANK_SALT"]
    open("config/.added_salt", "w").write("1")
marker = "require_once(__DIR__ . '/lib/setup.php')"
i = s.index(marker)
open(path, "w").write(s[:i] + x.rstrip("\n") + "\n" + s[i:])
PY
    log "hardening settings present in config.php"
else
    log "config.php already hardened"
fi

# --- 3c. Permissions: owner = host user, group = www-data(33), mode 640 -------
# Apache runs as www-data (uid/gid 33); the bind mount preserves host ownership,
# so set the group to 33 via the container (root) — no host sudo needed. Owner
# stays the host user so future deploy runs can still read/edit it.
docker run --rm --entrypoint sh \
    -e HOST_UID="$(id -u)" \
    -v "$STACK_DIR/config:/write:rw" \
    "$MOODLE_IMAGE" \
    -c 'chown "$HOST_UID":33 /write/config.php && chmod 640 /write/config.php'

# --- 4. Full stack up -----------------------------------------------------
docker compose up -d
docker compose ps

# --- 5. Post-install verification ----------------------------------------
if docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_name='mdl_config'" 2>/dev/null | grep -q 1; then
    log "Moodle DB schema present"
else
    die "mdl_config table missing — install did not complete"
fi

docker compose exec -T moodle php admin/cli/purge_caches.php || true

# If we added the salt AFTER install.php created the admin user, re-hash it.
if [[ -f config/.added_salt ]]; then
    log "re-hashing admin password with the new salt…"
    docker compose exec -T moodle php admin/cli/reset_password.php \
        --username="$MOODLE_ADMIN_USER" --password="$MOODLE_ADMIN_PASS"
    rm -f config/.added_salt
fi

# --- 6. Optional host cron timer -----------------------------------------
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
