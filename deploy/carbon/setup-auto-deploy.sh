#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Set up pull-based auto-deploy for Carbon Data Trust Platform on the VPS.
# Creates a systemd timer that polls for new tags every 2 min.
#
# Usage (run as root on the VPS):
#   sudo bash deploy/carbon/setup-auto-deploy.sh
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="${1:-/srv/carbon}"
BACKEND_PORT="${2:-8002}"
DEPLOY_USER="${3:-ahmed}"

echo "═══════════════════════════════════════════════════════════"
echo "  Carbon Auto-Deploy Setup"
echo "  APP_DIR      : $APP_DIR"
echo "  BACKEND_PORT : $BACKEND_PORT"
echo "  User         : $DEPLOY_USER"
echo "═══════════════════════════════════════════════════════════"

cat > /etc/carbon-deploy.env <<EOF
APP_DIR=$APP_DIR
BACKEND_PORT=$BACKEND_PORT
EOF
echo "✓ Created /etc/carbon-deploy.env"

cat > /etc/systemd/system/carbon-deploy.service <<EOF
[Unit]
Description=Carbon Data Trust auto-deploy (pull-based)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=$DEPLOY_USER
ExecStart=/usr/bin/bash $APP_DIR/deploy/carbon/auto-deploy.sh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=carbon-deploy

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Created carbon-deploy.service"

cat > /etc/systemd/system/carbon-deploy.timer <<EOF
[Unit]
Description=Check for new Carbon tags every 2 minutes

[Timer]
OnBootSec=30
OnUnitActiveSec=2min
AccuracySec=30s

[Install]
WantedBy=timers.target
EOF
echo "✓ Created carbon-deploy.timer"

systemctl daemon-reload
echo "✓ systemd reloaded"

echo
echo "To ENABLE auto-deploy:"
echo "  sudo systemctl enable --now carbon-deploy.timer"
echo
echo "To check status:"
echo "  sudo systemctl status carbon-deploy.timer"
echo "  sudo journalctl -u carbon-deploy -f"
echo
echo "To DISABLE auto-deploy:"
echo "  sudo systemctl disable --now carbon-deploy.timer"
