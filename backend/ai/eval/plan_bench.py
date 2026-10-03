"""Pulse **Plan** report — offline bank + live bank status, one key.

This is the coordinator-facing report for the Plan surface. It is **reported,
never merged**: it never moves a Chat Ask objective, the Tasks board, or the
v2 intelligence ladder (RULE_36). Plan has its own gate.

* Offline: ``agent_plan_runner.score()`` (path bank + ADR-0052 contract
  goldens), 0-LLM, deterministic.
* Live: discover ``chat_plan_bank_pl*.yaml`` and read their dated evidence
  ``PV2-plan-<PL-ID>-*.json``. A bank reaches only when the last
  ``CLOSE_RUNS = 3`` consecutive full runs pass every row; no evidence →
  **missing**, never zero-fail.

CLI::

    python -m ai.eval.plan_bench            # print the report
    python -m ai.eval.plan_bench --write    # write docs/pulse/evidence/PV2-plan-report-<date>.json
    python -m ai.eval.plan_bench --list     # live bank turn sets; no network

Contract: ``docs/pulse/PULSE-PLAN-CONTRACT.md``.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from ai.eval.agent_plan_runner import EVIDENCE, inventory, score
from ai.eval.chat_plan_retest import BANKS, bank_doc

CLOSE_RUNS = 3
OUT_FILE = EVIDENCE / f"PV2-plan-report-{date.today().isoformat()}.json"


def latest_full_runs(bank_id: str, root: Path | None = None) -> list[dict]:
    """Full ``live_plan`` evidence rows for ``bank_id``, oldest → newest."""
    ev = root or EVIDENCE
    rows = []
    for path in sorted(ev.glob(f"PV2-plan-{bank_id.replace('-', '')}-*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and row.get("tier") == "live_plan" and not row.get("partial"):
            row["_file"] = path.name
            rows.append(row)
    return sorted(rows, key=lambda r: str(r.get("run_at") or ""))


def live_status(bank_id: str, root: Path | None = None) -> dict:
    runs = latest_full_runs(bank_id, root)
    last = runs[-CLOSE_RUNS:]
    if not runs:
        status = "missing"
    elif len(last) < CLOSE_RUNS:
        status = "partial"
    elif all(r.get("pass") for r in last):
        status = "reached"
    else:
        status = "fail"
    return {
        "status": status,
        "runs": len(runs),
        "close_runs": CLOSE_RUNS,
        "evidence": [r.get("_file") for r in last],
    }


def live_banks() -> list[dict]:
    rows = []
    for bank_id, path in sorted(BANKS.items()):
        doc = bank_doc(bank_id)
        rows.append({
            "bank": bank_id,
            "file": path.name,
            "purpose": doc.get("purpose"),
            "tier": doc.get("tier"),
            "sample_threads": doc.get("sample_threads"),
            "sample_turns": doc.get("sample_turns"),
            "language_threads": doc.get("language_threads"),
            "threshold": doc.get("threshold"),
            "precondition": doc.get("precondition"),
            "evidence_pattern": f"PV2-plan-{bank_id.replace('-', '')}-*.json",
            "honest": live_status(bank_id),
        })
    return rows


def build_report() -> dict:
    offline = score()
    live = live_banks()
    reached = sum(1 for b in live if b["honest"]["status"] == "reached")
    return {
        "date": date.today().isoformat(),
        "surface": "plan",
        "offline": {
            "total": offline["n"],
            "passed": offline["passed"],
            "gate_pass": offline["gate_pass"],
            "path_bank": offline["plan_bank"],
            "contract_bank": offline["contract_bank"],
            "inventory": inventory(),
        },
        "live_banks": live,
        "live_reached": reached,
        "live_total": len(live),
        "rule": (
            "Honest = worst of the last CLOSE_RUNS=3 full live runs. No live "
            "evidence → missing. Offline pass never closes a live Plan rung. "
            "Never merged into the Chat Ask / Tasks / ladder scores. L6/L7 not claimed."
        ),
        "blocked": (
            "The local cell is aastmt/carbon; the nibras cell is down. Live PL "
            "banks stay missing until a nibras cell is up — no brand switch, no "
            "STACK-HOLD (every PL bank is read-only)."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pulse Plan report")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--list", action="store_true", help="print the live bank turn sets; no network")
    args = parser.parse_args(argv)

    if args.list:
        from ai.eval.chat_plan_retest import main as retest_main

        return retest_main(["--list"])

    report = build_report()
    offline = report["offline"]
    print(
        f"plan offline  {offline['passed']}/{offline['total']}  "
        f"gate={'pass' if offline['gate_pass'] else 'FAIL'}"
    )
    for bank in report["live_banks"]:
        honest = bank["honest"]
        print(
            f"  {bank['bank']}  {honest['status']:8}  runs={honest['runs']}/{CLOSE_RUNS}  "
            f"{bank['file']}"
        )
    print(f"live reached {report['live_reached']}/{report['live_total']}")
    if args.write:
        OUT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {OUT_FILE}")
    return 0 if offline["gate_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
