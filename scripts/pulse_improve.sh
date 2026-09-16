#!/usr/bin/env bash
# pulse_improve.sh — the closed-loop Pulse intelligence audit, one command.
#
#   BASELINE → ENSEMBLE AUDIT (5 lanes, judged) → CONSOLIDATED TESTABLE WORKLIST
#
# This encodes the methodology: measure first (ground truth), then let an
# ensemble of strong models critique, judged into a ranked worklist where only
# TESTABLE findings are actioned. After you fix a finding, re-run the scorecard
# and `--compare` to PROVE the number moved (keep only non-regressing changes).
#
# Usage:
#   scripts/pulse_improve.sh                 # baseline + all 5 audit lanes
#   scripts/pulse_improve.sh --audit-only    # skip baseline (reuse last)
#   scripts/pulse_improve.sh --baseline-only # just the scorecard
#
# Env:
#   PANEL_PROMPT / PANEL_ARCH / PANEL_DOMAIN — override model panels (space-sep)
#   JUDGE — override the reconciling judge (default gemini-3.1-pro)
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python3"
OUT="$REPO/raw/reviews"
mkdir -p "$OUT"

JUDGE="${JUDGE:-gemini-3.1-pro}"
STAMP="$(date +%Y%m%d-%H%M%S)"

baseline_only=0; audit_only=0
for a in "$@"; do
  case "$a" in
    --baseline-only) baseline_only=1 ;;
    --audit-only)    audit_only=1 ;;
  esac
done

hr() { printf '  %s\n' "────────────────────────────────────────────────────────"; }

if [[ "$audit_only" -eq 0 ]]; then
  echo; echo "  ▶ STEP 1 — BASELINE (ground truth)"; hr
  DJANGO_BRAND=nibras "$PY" "$REPO/scripts/pulse_scorecard.py" \
    --out "$OUT/scorecard-$STAMP.json"
  cp "$OUT/scorecard-$STAMP.json" "$OUT/scorecard-latest.json"
fi
[[ "$baseline_only" -eq 1 ]] && exit 0

echo; echo "  ▶ STEP 2 — ENSEMBLE AUDIT (judged worklists)"; hr

audit() {
  local lane="$1"; shift
  local out="$OUT/audit-$lane.json"
  echo; echo "  ── lane: $lane"
  "$PY" "$REPO/scripts/pulse_audit.py" --lane "$lane" --judge "$JUDGE" \
    --out "$out" "$@" || echo "  ⚠ lane $lane failed (continuing)"
}

audit prompt_audit \
  --files backend/ai/engine/llm/prompts.py \
  ${PANEL_PROMPT:+--models $PANEL_PROMPT}

audit architecture \
  --files backend/ai/engine/cognition/turn/runner.py \
          backend/ai/engine/agent/reasoning.py \
          backend/ai/engine/cognition/turn/intent.py \
  ${PANEL_ARCH:+--models $PANEL_ARCH}

audit domain_gaps \
  --files domain_packs/nibras/api_catalog.yaml \
          domain_packs/nibras/processes/payroll.run.lifecycle.yaml \
          domain_packs/nibras/processes/leave.request.lifecycle.yaml \
          domain_packs/nibras/processes/loan.request.lifecycle.yaml \
  ${PANEL_DOMAIN:+--models $PANEL_DOMAIN}

audit instance_review \
  --files backend/ai/engine/instances/nibras/instance.yaml

# Skill audit only if the instance has guidance skills.
if compgen -G "$REPO/domain_packs/nibras/skills/*/SKILL.md" >/dev/null 2>&1; then
  audit skill_audit --files domain_packs/nibras/skills/*/SKILL.md
fi

echo; echo "  ▶ STEP 3 — CONSOLIDATED TESTABLE WORKLIST"; hr
"$PY" - "$OUT" <<'PY'
import json, sys, glob, os
out_dir = sys.argv[1]
rows = []
for f in glob.glob(os.path.join(out_dir, "audit-*.json")):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    lane = d.get("lane", os.path.basename(f))
    wl = (d.get("verdict") or {}).get("worklist") or []
    for w in wl:
        if w.get("actionable"):
            rows.append((lane, w))
sev_rank = {"CRITICAL": 0, "HIGH": 1, "MED": 2, "LOW": 3}
rows.sort(key=lambda r: (sev_rank.get(r[1].get("severity", "LOW"), 3),
                         -int(r[1].get("agreement", 0) or 0)))
testable = [r for r in rows if r[1].get("testable")]
print(f"  {len(rows)} actionable · {len(testable)} convert to a failing test\n")
print(f"  {'#':<3}{'lane':<16}{'sev':<10}{'agree':<7}{'test':<6}title")
hr = "  " + "─"*72
print(hr)
for i, (lane, w) in enumerate(rows[:25], 1):
    t = "yes" if w.get("testable") else "—"
    print(f"  {i:<3}{lane[:15]:<16}{w.get('severity','?'):<10}"
          f"{str(w.get('agreement','?')):<7}{t:<6}{(w.get('title') or '')[:44]}")
print(hr)
consolidated = os.path.join(out_dir, "worklist-consolidated.json")
json.dump([{"lane": l, **w} for l, w in rows], open(consolidated, "w"),
          indent=2, ensure_ascii=False)
print(f"  ✓ consolidated → {consolidated}")
PY

echo
echo "  ▶ NEXT: pick a testable finding → write the failing test → fix →"
echo "         DJANGO_BRAND=nibras $PY scripts/pulse_scorecard.py --out $OUT/scorecard-after.json"
echo "         $PY scripts/pulse_scorecard.py --compare $OUT/scorecard-latest.json $OUT/scorecard-after.json"
echo "         (keep the change only if OVERALL went up and nothing regressed)"
echo
