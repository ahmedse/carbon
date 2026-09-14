#!/bin/bash
# .ai-toolkit/scripts/audit-routes.sh
# Registry drift check (P2-11).
#
# Recomputes the live URL-route inventory exactly as `scan.sh api` does and
# diffs it against the committed .ai-toolkit/registry/api.md. The comparison is
# timestamp-insensitive (the "auto-generated …" header is ignored), so a freshly
# regenerated registry always passes and only REAL route drift fails.
#
# "Toolkit rot is the same disease": a registry that stops matching the live
# codebase is worse than no registry. This gate fails closed when routes have
# changed but the registry was not regenerated.
#
# Usage:
#   ./.ai-toolkit/scripts/audit-routes.sh
#
# Exit 0 = registry in sync; exit 1 = drift (regenerate + commit).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT="$(dirname "$TOOLKIT_DIR")"
CONFIG="$TOOLKIT_DIR/project.config.md"
REG="$TOOLKIT_DIR/registry/api.md"

cfg() { grep "^$1=" "$CONFIG" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/ *#.*//' | tr -d '\r' | xargs || true; }

BACKEND_DIR="$ROOT/$(cfg BACKEND_DIR)"

# Same excludes as scan.sh — vendored/generated code pollutes the registry.
EXCLUDES="venv .venv node_modules __pycache__ migrations .git dist build staticfiles static media archive archived_apps simulations catboost_info"
GREP_EX=""
for d in $EXCLUDES; do GREP_EX="$GREP_EX --exclude-dir=$d"; done

if [ ! -f "$REG" ]; then
  echo "✗ registry missing: $REG — run ./.ai-toolkit/scripts/scan.sh api first" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 1. Live inventory — mirror scan.sh scan_api exactly (same grep/sed/head limits,
#    including the `-A1` context lines that render `def …` with `-` separators).
{
  echo "## DRF Routers & url paths"
  grep -rn $GREP_EX "router.register\|path(\|re_path(" "$BACKEND_DIR" --include="urls.py" 2>/dev/null \
    | sed "s|$ROOT/||" | head -300
  echo "## @action custom endpoints (ViewSet extra routes)"
  grep -rn $GREP_EX "@action" "$BACKEND_DIR" --include="*.py" -A1 2>/dev/null \
    | grep -E "@action|def " | sed "s|$ROOT/||" | head -200
} > "$tmp/live"

# 2. Committed inventory — strip the timestamp header, the note, code fences, and blanks.
grep -vE 'auto-generated|Before adding an endpoint|^```|^$' "$REG" > "$tmp/committed"

# 3. Diff. Drift → fail with a pointer to regenerate.
if diff -u "$tmp/committed" "$tmp/live" > "$tmp/diff"; then
  echo "✓ registry/api.md in sync with live routes"
else
  echo "✗ registry drift detected (registry/api.md is stale):" >&2
  cat "$tmp/diff" >&2
  echo "" >&2
  echo "Regenerate with: ./.ai-toolkit/scripts/scan.sh api   then commit registry/api.md" >&2
  exit 1
fi
