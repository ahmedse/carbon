#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Set up Pulse heartbeat timer for ONE Carbon instance on the VPS.
# Creates a systemd timer that runs daily to drive proactive cognition
# (consolidation/distill/decay loops + PulseHeartbeat telemetry).
#
# Each instance runs as a docker container ${INSTANCE}-backend;
# the command runs INSIDE it via docker exec.
#
# Usage (run as root on the VPS):
#   sudo bash deploy/instance/setup-pulse-heartbeat.sh nibras
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

INSTANCE="${1:?usage: setup-pulse-heartbeat.sh <instance-name>}"

echo "═══════════════════════════════════════════════════════════"
echo "  $INSTANCE Pulse Heartbeat Setup"
echo "  INSTANCE: $INSTANCE"
echo "═══════════════════════════════════════════════════════════"

# ── 1. Systemd service ──────────────────────────────────────────
# ExecStartPre ensures idempotent instance registration before maintenance runs.
cat > "/etc/systemd/system/${INSTANCE}-pulse-heartbeat.service" <<EOF
[Unit]
Description=$INSTANCE Pulse heartbeat (background cognition)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStartPre=/usr/bin/docker exec ${INSTANCE}-backend python manage.py ensure_pulse_instance
ExecStart=/usr/bin/docker exec ${INSTANCE}-backend python manage.py run_pulse_maintenance
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$INSTANCE-pulse-heartbeat

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Created ${INSTANCE}-pulse-heartbeat.service"

# ── 2. Systemd timer (daily at 2 AM UTC) ────────────────────────
# Persistent=true ensures missed runs are caught up on next boot.
cat > "/etc/systemd/system/${INSTANCE}-pulse-heartbeat.timer" <<EOF
[Unit]
Description=Daily $INSTANCE Pulse heartbeat (02:00 UTC)

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF
echo "✓ Created ${INSTANCE}-pulse-heartbeat.timer"

# ── 3. Enable and start ──────────────────────────────────────────
systemctl daemon-reload
systemctl enable "${INSTANCE}-pulse-heartbeat.timer"
systemctl start "${INSTANCE}-pulse-heartbeat.timer"

echo ""
echo "✓ Pulse heartbeat timer is running for instance '$INSTANCE'."
echo ""
echo "Useful commands:"
echo "  systemctl status ${INSTANCE}-pulse-heartbeat.timer         # timer status"
echo "  systemctl list-timers ${INSTANCE}-pulse-heartbeat.timer    # next trigger"
echo "  journalctl -u ${INSTANCE}-pulse-heartbeat -f               # watch logs"
echo "  systemctl start ${INSTANCE}-pulse-heartbeat.service        # trigger now"
echo ""
echo "How it works:"
echo "  Daily at 02:00 UTC, the heartbeat ensures the Pulse instance"
echo "  is registered, then runs consolidation/distill/decay loops"
echo "  plus writes PulseHeartbeat telemetry. All runs inside the"
echo "  ${INSTANCE}-backend container via docker exec (per-brand isolation)."
