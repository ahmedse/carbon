#!/usr/bin/env bash
# Render config/config.php from config.php.template using .env values.
# Secrets (POSTGRES_PASSWORD, MOODLE_ADMIN_PASS, PASSWORDSALTMAIN) are
# generated once and persisted in .env so re-renders are stable.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

load_env

persist() { # persist NAME VALUE into .env
    local name="$1" value="$2"
    if grep -q "^${name}=" "$STACK_DIR/.env"; then
        sed -i "s|^${name}=.*|${name}=${value}|" "$STACK_DIR/.env"
    else
        printf '%s=%s\n' "$name" "$value" >> "$STACK_DIR/.env"
    fi
}

# Generate secrets where still placeholder/empty
if [[ -z "${POSTGRES_PASSWORD:-}" || "$POSTGRES_PASSWORD" == "__CHANGE_ME__" ]]; then
    POSTGRES_PASSWORD="$(rand_pass)"; persist POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
fi
if [[ -z "${MOODLE_ADMIN_PASS:-}" || "$MOODLE_ADMIN_PASS" == "__CHANGE_ME__" ]]; then
    MOODLE_ADMIN_PASS="$(rand_pass)"; persist MOODLE_ADMIN_PASS "$MOODLE_ADMIN_PASS"
fi
if [[ -z "${PASSWORDSALTMAIN:-}" ]]; then
    PASSWORDSALTMAIN="$(rand_salt)"; persist PASSWORDSALTMAIN "$PASSWORDSALTMAIN"
    load_env
fi

mkdir -p "$STACK_DIR/config"

# Substitute ONLY the named vars (envsubst would otherwise clobber PHP `$CFG`)
export WWWROOT DBHOST DBNAME="${POSTGRES_DB}" DBUSER="${POSTGRES_USER}" DBPASS="${POSTGRES_PASSWORD}" PASSWORDSALTMAIN

envsubst '${WWWROOT} ${DBHOST} ${DBNAME} ${DBUSER} ${DBPASS} ${PASSWORDSALTMAIN}' \
    < "$STACK_DIR/config.php.template" > "$STACK_DIR/config/config.php"

chmod 600 "$STACK_DIR/config/config.php"
log "rendered config/config.php"
