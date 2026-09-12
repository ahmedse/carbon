#!/usr/bin/env bash
# .ai-toolkit/scripts/retro.sh
# Retrospective helper: gather recent learnings for the Curator to review.
# Usage: ./retro.sh [since-date]
#   since-date: YYYY-MM-DD (default: 30 days ago)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLAYBOOK="$ROOT/.ai-toolkit/troubleshooting/playbook.md"
DECISIONS="$ROOT/.ai-toolkit/decisions"
PROPOSALS="$ROOT/.ai-toolkit/decisions/PROPOSALS-$(date +%Y-%m).md"

since="${1:-$(date -d '30 days ago' +%Y-%m-%d 2>/dev/null || date -v-30d +%Y-%m-%d 2>/dev/null || echo "2026-01-01")}"

echo "════════════════════════════════════════════════════════════════"
echo "  Retrospective: Gather Learnings Since $since"
echo "════════════════════════════════════════════════════════════════"
echo

# ── Playbook Entries ───────────────────────────────────────────────────────
echo "── Playbook Entries (troubleshooting/playbook.md) ────────────────────"
if [ -f "$PLAYBOOK" ]; then
  entries=$(grep -E "^### PB-" "$PLAYBOOK" | wc -l)
  recent=$(grep -A2 "First seen:" "$PLAYBOOK" | grep -E "$since|202[6-9]-" | wc -l)
  echo "Total entries: $entries"
  echo "Entries since $since: ~$recent (check 'First seen' dates manually)"
  echo
  echo "Recent entries:"
  grep -B1 "First seen: 202" "$PLAYBOOK" | grep "^### PB-" | tail -10 || echo "  (none with 'First seen' field)"
else
  echo "  No playbook found."
fi
echo

# ── ADRs ───────────────────────────────────────────────────────────────────
echo "── Architecture Decision Records (decisions/) ─────────────────────────"
if [ -d "$DECISIONS" ]; then
  total=$(find "$DECISIONS" -name "*.md" ! -name "0000-template.md" ! -name "README.md" ! -name "PROPOSALS-*.md" | wc -l)
  echo "Total ADRs: $total"
  echo "Recent ADRs (by file mtime):"
  find "$DECISIONS" -name "[0-9]*.md" ! -name "0000-*" -newermt "$since" 2>/dev/null | sort || \
    ls -lt "$DECISIONS"/[0-9]*.md 2>/dev/null | head -5 | awk '{print "  " $NF}' || echo "  (none)"
else
  echo "  No decisions/ dir."
fi
echo

# ── Current Warnings (verify.sh antipatterns) ──────────────────────────────
echo "── Current Anti-Pattern Warnings (verify.sh) ─────────────────────────"
cd "$ROOT"
if [ -x ".ai-toolkit/scripts/verify.sh" ]; then
  ./.ai-toolkit/scripts/verify.sh antipatterns 2>&1 | grep -E "⚠|✗" | head -15 || echo "  (all green)"
else
  echo "  verify.sh not found."
fi
echo

# ── Cluster Hints ──────────────────────────────────────────────────────────
echo "── Pattern Clustering Hints ──────────────────────────────────────────"
echo "Root cause keywords in playbook (frequency):"
if [ -f "$PLAYBOOK" ]; then
  grep -i "root cause:" "$PLAYBOOK" | sed 's/.*Root cause: //' | sort | uniq -c | sort -rn | head -10 || echo "  (none)"
else
  echo "  (no playbook)"
fi
echo

# ── Output Location ────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════════"
echo "Next steps:"
echo "  1. Review the data above."
echo "  2. Activate the Curator: ./.ai-toolkit/scripts/activate.sh curator"
echo "  3. Paste that prompt + tell Curator: 'Review learnings since $since'"
echo "  4. Curator writes proposals to: $PROPOSALS"
echo "  5. Review + approve proposals, then Curator applies them."
echo "════════════════════════════════════════════════════════════════"
