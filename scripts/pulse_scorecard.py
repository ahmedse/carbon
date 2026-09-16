#!/usr/bin/env python3
"""
pulse_scorecard.py — the GROUND-TRUTH baseline for the Pulse audit loop.

Philosophy: an audit finding only counts when it moves a measured number.
This runner produces that number. It aggregates every *deterministic,
repeatable* signal Pulse already has into a single scorecard JSON stamped with
the git SHA + timestamp, so you can diff two runs and prove a change helped.

It measures (each is a 0..1 rate, higher = better):

  1. eval_deterministic  — ai.eval.hrms_report scenarios (net-pay grounding,
                           CBAC cross-employee deny, no-fabrication)
  2. eval_pytest         — the answer-quality + grounding pytest eval suite
  3. redteam_defense     — (optional) pass rate of the adversarial red-team loop
                           if a graded file is supplied

It intentionally does NOT call an LLM. It is the *stable* anchor the LLM audits
are judged against. Run it BEFORE an audit (baseline) and AFTER applying a
change (delta) — keep the change only if `overall` went up and nothing
regressed.

Usage:
    # Full baseline (deterministic + pytest eval):
    DJANGO_BRAND=nibras python3 scripts/pulse_scorecard.py \
        --out raw/reviews/scorecard-baseline.json

    # Include a previously-graded red-team file in the score:
    python3 scripts/pulse_scorecard.py \
        --redteam-grades raw/reviews/redteam_grades.json \
        --out raw/reviews/scorecard-after.json

    # Compare two scorecards (prints the delta table, exits 1 on regression):
    python3 scripts/pulse_scorecard.py \
        --compare raw/reviews/scorecard-baseline.json raw/reviews/scorecard-after.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_BACKEND = _REPO / "backend"
_VENV_PY = _REPO / ".venv" / "bin" / "python"

# Weight each measured lane into the single `overall` score. Deterministic
# checks are weighted highest — they are the least noisy signal.
WEIGHTS = {
    "eval_deterministic": 0.45,
    "eval_pytest": 0.35,
    "redteam_defense": 0.20,
}


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO, text=True
        ).strip()
    except Exception:
        return "unknown"


def _python() -> str:
    return str(_VENV_PY) if _VENV_PY.exists() else sys.executable


def _run(cmd: list[str], *, env_brand: str = "nibras") -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env["DJANGO_BRAND"] = env_brand
    return subprocess.run(
        cmd, cwd=_BACKEND, capture_output=True, text=True, env=env, timeout=900
    )


# ── Lane 1: deterministic HRMS report ───────────────────────────────────────

def measure_eval_deterministic() -> dict:
    """Run ai.eval.hrms_report → parse 'Scenario X: PASS|FAIL' lines."""
    proc = _run([_python(), "-m", "ai.eval.hrms_report"])
    out = proc.stdout + proc.stderr
    results = re.findall(r"(Scenario [A-Z][^:]*): (PASS|FAIL)", out)
    passed = sum(1 for _, v in results if v == "PASS")
    total = len(results)
    return {
        "rate": (passed / total) if total else 0.0,
        "passed": passed,
        "total": total,
        "scenarios": {name.strip(): verdict for name, verdict in results},
        "exit_code": proc.returncode,
    }


# ── Lane 2: pytest answer-quality + grounding eval suite ─────────────────────

EVAL_TESTS = [
    "ai/tests/test_answer_quality_eval.py",
    "ai/tests/test_hrms_answer_quality_eval.py",
    "ai/tests/test_eval_envelope_checks.py",
    "ai/tests/test_retrieval_grounding.py",
    "ai/tests/test_answer_envelope.py",
]


def measure_eval_pytest() -> dict:
    """Run the eval pytest subset → parse the 'N passed, M failed' summary."""
    proc = _run(
        [_python(), "-m", "pytest", *EVAL_TESTS, "-q", "--no-header", "--tb=no"]
    )
    out = proc.stdout + proc.stderr
    passed = int((re.search(r"(\d+) passed", out) or [0, 0])[1])
    failed = int((re.search(r"(\d+) failed", out) or [0, 0])[1])
    errors = int((re.search(r"(\d+) error", out) or [0, 0])[1])
    total = passed + failed + errors
    return {
        "rate": (passed / total) if total else 0.0,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "exit_code": proc.returncode,
    }


# ── Lane 3: red-team defense rate (optional, from a pre-graded file) ─────────

def measure_redteam_defense(grades_path: Path | None) -> dict:
    """Parse a poe_redteam grades file → PASS rate across adversarial queries."""
    if not grades_path or not grades_path.exists():
        return {"rate": None, "passed": 0, "total": 0, "note": "no grades file"}
    data = json.loads(grades_path.read_text())
    items = data.get("result", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {"rate": None, "passed": 0, "total": 0, "note": "unparseable"}
    verdicts = [str(i.get("verdict", "")).upper() for i in items if isinstance(i, dict)]
    passed = sum(1 for v in verdicts if v == "PASS")
    total = len(verdicts)
    return {
        "rate": (passed / total) if total else 0.0,
        "passed": passed,
        "partial": sum(1 for v in verdicts if v == "PARTIAL"),
        "failed": sum(1 for v in verdicts if v == "FAIL"),
        "total": total,
    }


# ── Aggregate ────────────────────────────────────────────────────────────────

def build_scorecard(redteam_grades: Path | None) -> dict:
    lanes = {
        "eval_deterministic": measure_eval_deterministic(),
        "eval_pytest": measure_eval_pytest(),
        "redteam_defense": measure_redteam_defense(redteam_grades),
    }
    # Weighted overall over lanes that produced a rate (skip null lanes and
    # renormalize their weight so a missing optional lane doesn't tank the score).
    active = {k: v for k, v in lanes.items() if v.get("rate") is not None}
    wsum = sum(WEIGHTS[k] for k in active) or 1.0
    overall = sum(WEIGHTS[k] * active[k]["rate"] for k in active) / wsum

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "overall": round(overall, 4),
        "weights": WEIGHTS,
        "lanes": lanes,
    }


# ── Compare two scorecards ───────────────────────────────────────────────────

def compare(before_path: Path, after_path: Path) -> int:
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())

    def rate(sc, lane):
        return (sc["lanes"].get(lane) or {}).get("rate")

    print(f"\n  Pulse scorecard delta  ({before['git_sha']} → {after['git_sha']})")
    print("  " + "─" * 58)
    print(f"  {'lane':<22}{'before':>10}{'after':>10}{'Δ':>12}")
    print("  " + "─" * 58)

    regressed = False
    for lane in ("eval_deterministic", "eval_pytest", "redteam_defense", None):
        if lane is None:
            b, a = before["overall"], after["overall"]
            name = "OVERALL"
        else:
            b, a = rate(before, lane), rate(after, lane)
            name = lane
        if b is None and a is None:
            continue
        bs = "—" if b is None else f"{b:.3f}"
        as_ = "—" if a is None else f"{a:.3f}"
        if b is not None and a is not None:
            d = a - b
            arrow = "▲" if d > 1e-9 else ("▼" if d < -1e-9 else "=")
            delta = f"{arrow} {d:+.3f}"
            if d < -1e-9:
                regressed = True
        else:
            delta = ""
        sep = "  " + "─" * 58 if name == "OVERALL" else ""
        if sep:
            print(sep)
        print(f"  {name:<22}{bs:>10}{as_:>10}{delta:>12}")

    print("  " + "─" * 58)
    if regressed:
        print("  ✗ REGRESSION detected — do NOT keep this change as-is.\n")
        return 1
    print("  ✓ no regression.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pulse ground-truth scorecard")
    ap.add_argument("--out", help="Write scorecard JSON here")
    ap.add_argument("--redteam-grades", help="Optional graded red-team JSON to fold in")
    ap.add_argument("--brand", default="nibras")
    ap.add_argument(
        "--compare", nargs=2, metavar=("BEFORE", "AFTER"),
        help="Compare two scorecards and exit 1 on regression",
    )
    args = ap.parse_args()

    if args.compare:
        return compare(Path(args.compare[0]), Path(args.compare[1]))

    grades = Path(args.redteam_grades) if args.redteam_grades else None
    print("  → measuring Pulse baseline (deterministic + pytest eval)…", flush=True)
    sc = build_scorecard(grades)

    for lane, v in sc["lanes"].items():
        r = v.get("rate")
        rate_s = "—" if r is None else f"{r:.3f}"
        print(f"    {lane:<22} rate={rate_s}  ({v.get('passed', 0)}/{v.get('total', 0)})")
    print(f"    {'OVERALL':<22} {sc['overall']:.4f}   @ {sc['git_sha']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sc, indent=2, ensure_ascii=False))
        print(f"  ✓ saved → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
