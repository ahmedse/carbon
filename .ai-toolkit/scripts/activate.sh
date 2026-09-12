#!/bin/bash
# .ai-toolkit/scripts/activate.sh
# Prints the exact activation prompt to paste into Zoo Code / any chat window.
#
# Usage:
#   ./ai-toolkit/scripts/activate.sh              # list available roles
#   ./ai-toolkit/scripts/activate.sh backend-worker
#   ./ai-toolkit/scripts/activate.sh master-architect

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$TOOLKIT_DIR/project.config.md"
ROLES_DIR="$TOOLKIT_DIR/roles"

# ── Helpers ───────────────────────────────────────────────────────────────────

get_config() {
  local key="$1"
  grep "^${key}=" "$CONFIG_FILE" | head -1 | cut -d= -f2-
}

list_roles() {
  echo ""
  echo "Available roles:"
  echo ""
  for f in "$ROLES_DIR"/*.md; do
    role=$(basename "$f" .md)
    model=$(grep "^# Recommended Model:" "$f" | head -1 | sed 's/# Recommended Model: //')
    printf "  %-22s  %s\n" "$role" "$model"
  done
  echo ""
  echo "Usage: $0 <role-name>"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────

if [ $# -eq 0 ]; then
  list_roles
  exit 0
fi

ROLE="$1"
ROLE_FILE="$ROLES_DIR/${ROLE}.md"

if [ ! -f "$ROLE_FILE" ]; then
  echo "Error: unknown role '$ROLE'"
  list_roles
  exit 1
fi

PROJECT=$(get_config "PROJECT_NAME")
MODEL=$(grep "^# Recommended Model:" "$ROLE_FILE" | head -1 | sed 's/# Recommended Model: //')
RELATIVE_TOOLKIT="$(realpath --relative-to="$(pwd)" "$TOOLKIT_DIR" 2>/dev/null || echo ".ai-toolkit")"

# ── Print the activation prompt ───────────────────────────────────────────────

echo ""
echo "\`\`\`"
echo "============================================================"
echo " ACTIVATION PROMPT — PASTE INTO YOUR CHAT WINDOW"
echo " Role:   ${ROLE}"
echo " Project: ${PROJECT}"
echo " Model:   ${MODEL}"
echo "============================================================"
echo ""
echo "Your role is ${ROLE} for ${PROJECT}."
echo ""
echo "Before starting any work, complete these steps in order:"
echo "1. Read ${RELATIVE_TOOLKIT}/project.config.md — project paths, commands, and hard rules"
echo "2. Read ${RELATIVE_TOOLKIT}/shared/base-rules.md — universal terminal, verification, and handoff rules"
echo "3. Read ${RELATIVE_TOOLKIT}/roles/${ROLE}.md — your exact role, constraints, and verification gate"
echo "4. Read the task spec (TASKS.md current phase, or I will provide it)"
echo "5. Confirm your role by responding: Ready as ${ROLE} for ${PROJECT}."
echo ""
echo "Do not begin work until you have read all four files and confirmed."
echo "\`\`\`"
