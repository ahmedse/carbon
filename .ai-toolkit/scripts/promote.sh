#!/usr/bin/env bash
# promote.sh — Cross-project pattern scanner.
# Scans every registered project's playbook for recurring root-cause classes and
# drafts promotion candidates (patterns seen in >=2 projects) for the Curator to review.
#
# Usage: ~/ai-toolkit/scripts/promote.sh
# Output: ~/ai-toolkit/patterns/CANDIDATES-<YYYY-MM-DD>.md

set -euo pipefail

CENTRAL="$HOME/ai-toolkit"
PROJECTS=(
  "$HOME/clearturn/turnkey"
  "$HOME/clearturn/gigacast"
  "$HOME/aast/carbon"
)
OUT="$CENTRAL/patterns/CANDIDATES-$(date +%Y-%m-%d).md"

# Keyword classes to detect across playbooks (extend as patterns emerge).
KEYWORDS="datetime|timezone|naive|select_related|json|n\+1|migration|uuid|flush|race|cache|async|await|docker|container|nohup|stdin|permission|auth|cors|rate.?limit|serialize|deadlock|memory|leak"

echo "# Cross-Project Promotion Candidates — $(date +%Y-%m-%d)" > "$OUT"
echo "" >> "$OUT"
echo "Root-cause keywords appearing in the playbooks of 2+ projects." >> "$OUT"
echo "Review each against patterns/README.md promotion contract before promoting." >> "$OUT"
echo "" >> "$OUT"

declare -A hits
for p in "${PROJECTS[@]}"; do
  name=$(basename "$p")
  pb=$(find "$p/.ai-toolkit/troubleshooting" -name '*.md' 2>/dev/null)
  [ -z "$pb" ] && continue
  # For each keyword, does this project's playbook mention it?
  while IFS='|' read -ra KWS; do :; done <<< "$KEYWORDS"
  for kw in ${KEYWORDS//|/ }; do
    if grep -qiE "$kw" $pb 2>/dev/null; then
      hits["$kw"]="${hits[$kw]:-} $name"
    fi
  done
done

found=0
for kw in "${!hits[@]}"; do
  projs=$(echo "${hits[$kw]}" | tr ' ' '\n' | sed '/^$/d' | sort -u)
  count=$(echo "$projs" | grep -c .)
  if [ "$count" -ge 2 ]; then
    found=$((found+1))
    echo "## Candidate: \`$kw\` (seen in $count projects)" >> "$OUT"
    echo "Projects: $(echo $projs | tr '\n' ' ')" >> "$OUT"
    echo "- [ ] Same root-cause class? (not just same keyword)" >> "$OUT"
    echo "- [ ] Project-agnostic (or framework-scoped)?" >> "$OUT"
    echo "- [ ] Not already in a shared/ contract or frameworks/ module?" >> "$OUT"
    echo "- [ ] → If yes: add UP-NNNN to patterns/index.md" >> "$OUT"
    echo "" >> "$OUT"
  fi
done

echo "Scanned ${#PROJECTS[@]} projects. Found $found candidate keyword(s) in 2+ projects."
echo "Draft written to: $OUT"
