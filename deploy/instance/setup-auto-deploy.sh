#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Set up pull-based auto-deploy for ONE Carbon instance on the VPS.
# Creates a systemd timer that polls for new ${INSTANCE}-v* tags
# every 2 minutes. No inbound SSH needed — all outbound git pulls.
#
# Usage (run as root on the VPS):
#   sudo bash deploy/instance/setup-auto-deploy.sh nibras /srv/nibras 8003 ahmed
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

INSTANCE="${1:?usage: setup-auto-deploy.sh <instance-name> [app-dir] [port] [user]}"
APP_DIR="${2:-/srv/$INSTANCE}"
BACKEND_PORT="${3:-8002}"
DEPLOY_USER="${4:-ahmed}"

echo "═══════════════════════════════════════════════════════════"
echo "  $INSTANCE Auto-Deploy Setup"
echo "  APP_DIR      : $APP_DIR"
echo "  BACKEND_PORT : $BACKEND_PORT"
echo "  User         : $DEPLOY_USER"
echo "═══════════════════════════════════════════════════════════"

# ── 1. Config file ──────────────────────────────────────────────
cat > "/etc/${INSTANCE}-deploy.env" <<EOF
APP_DIR=$APP_DIR
BACKEND_PORT=$BACKEND_PORT
INSTANCE=$INSTANCE
EOF
echo "✓ Created /etc/${INSTANCE}-deploy.env"

# ── 2. Systemd service ──────────────────────────────────────────
cat > "/etc/systemd/system/${INSTANCE}-deploy.service" <<EOF
[Unit]
Description=$INSTANCE auto-deploy (pull-based)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=$DEPLOY_USER
ExecStart=/usr/bin/bash $APP_DIR/deploy/instance/auto-deploy.sh $INSTANCE
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$INSTANCE-deploy

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Created ${INSTANCE}-deploy.service"

# ── 3. Systemd timer (every 2 minutes) ──────────────────────────
cat > "/etc/systemd/system/${INSTANCE}-deploy.timer" <<EOF
[Unit]
Description=Check for new $INSTANCE tags every 2 minutes

[Timer]
OnBootSec=30
OnUnitActiveSec=2min
AccuracySec=30s

[Install]
WantedBy=timers.target
EOF
echo "✓ Created ${INSTANCE}-deploy.timer"

# ── 4. Enable and start ──────────────────────────────────────────
systemctl daemon-reload
systemctl enable "${INSTANCE}-deploy.timer"
systemctl start "${INSTANCE}-deploy.timer"

echo ""
echo "✓ Auto-deploy timer is running for instance '$INSTANCE'."
echo ""
echo "Useful commands:"
echo "  systemctl status ${INSTANCE}-deploy.timer        # timer status"
echo "  systemctl list-timers ${INSTANCE}-deploy.timer   # next trigger"
echo "  journalctl -u ${INSTANCE}-deploy -f              # watch deploy logs"
echo "  systemctl start ${INSTANCE}-deploy.service       # trigger deploy now"
echo ""
echo "How it works:"
echo "  Every 2 min the VPS checks for new ${INSTANCE}-v* tags."
echo "  When a new tag appears, it auto-deploys that instance only."
echo "  No inbound SSH needed — all outbound git pulls."
