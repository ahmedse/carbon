#!/bin/bash
# .ai-toolkit/scripts/new-task.sh
# Scaffolds a new phase entry in TASKS.md.
#
# Usage:
#   ./ai-toolkit/scripts/new-task.sh <role> "<title>"
#
# Examples:
#   ./ai-toolkit/scripts/new-task.sh backend-worker "Add OBC to new forecaster"
#   ./ai-toolkit/scripts/new-task.sh frontend-worker "Fix Grid layout on mobile"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$TOOLKIT_DIR/project.config.md"
TASKS_FILE="$(dirname "$TOOLKIT_DIR")/TASKS.md"

get_config() {
  local key="$1"
  grep "^${key}=" "$CONFIG_FILE" | head -1 | cut -d= -f2-
}

list_roles() {
  for f in "$TOOLKIT_DIR/roles"/*.md; do
    basename "$f" .md
  done
}

if [ $# -lt 2 ]; then
  echo "Usage: $0 <role> \"<task title>\""
  echo ""
  echo "Available roles:"
  list_roles | sed 's/^/  /'
  exit 1
fi

ROLE="$1"
TITLE="$2"
DATE=$(date +%Y-%m-%d)
MODEL=$(grep "^# Recommended Model:" "$TOOLKIT_DIR/roles/${ROLE}.md" 2>/dev/null | head -1 | sed 's/# Recommended Model: //' || echo "DeepSeek-V3 / Sonnet")

# Count existing phases for auto-numbering
if [ -f "$TASKS_FILE" ]; then
  N=$(grep -c "^## Phase " "$TASKS_FILE" 2>/dev/null || echo "0")
  N=$((N + 1))
else
  N=1
fi

cat >> "$TASKS_FILE" << TEMPLATE

---

## Phase ${N} — ${TITLE}
**Date:** ${DATE}
**Worker Role:** ${ROLE}
**Recommended Model:** ${MODEL}
**Status:** PENDING

### Files to Read First
- <!-- add paths here -->

### Files to Change
- <!-- add paths here -->

### Context
<!-- What currently exists, and why we are changing it. 3-5 lines. -->

### Implementation
<!-- Exact change to make. Enough detail that a weak model can execute it blindly. -->

### DO NOT TOUCH
- <!-- list files/functions the worker must not modify -->

### Verification Gate
\`\`\`bash
# Exact commands to run. Expected output should be stated.
# Example: python manage.py check → "System check identified no issues"
\`\`\`
TEMPLATE

echo ""
echo "Phase ${N} scaffolded in TASKS.md."
echo "Fill in the Implementation section and Verification Gate before assigning to a worker."
echo ""
echo "Then run:"
echo "  ./.ai-toolkit/scripts/activate.sh ${ROLE}"
echo "  → paste the output into Zoo Code with model: ${MODEL}"
echo ""
