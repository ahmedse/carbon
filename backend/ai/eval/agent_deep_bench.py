"""Pulse Tasks / Agent deep benchmark — T1–T10.

Chat has a live retest bank. Tasks does not. This scorer reads the offline
plan bank, the ESS soak, the dated process SIM, and the unit consent gates.
It must not promote a missing live Tasks bank to reached.

Night 2026-09-23 FAIL stays. L6/L7 are not scored.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ai.eval.agent_plan_runner import score as score_plan_bank
from ai.eval.intelligence_ladder import SOAK_FILE, _load

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"
OUT_FILE = EVIDENCE / "PV2-agent-deep-2026-09-26.json"
TASKS_RETEST_GLOB = "PV2-tasks-retest-*.json"
CLOSE_RUNS = 3
AGENT_P50_BUDGET_MS = 180_000


@dataclass
class Row:
    tid: str
    name: str
    honest: str
    note: str
    sources: tuple[str, ...]


def load_tasks_retests(root: Path = EVIDENCE) -> list[dict[str, Any]]:
    """Full Tasks live retest runs. None exist on 2026-09-26."""
    runs = []
    for path in sorted(root.glob(TASKS_RETEST_GLOB)):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and row.get("tier") == "live_retest" and not row.get("partial"):
            row["_file"] = path.name
            runs.append(row)
    return sorted(runs, key=lambda r: str(r.get("run_at") or ""))


def _soak() -> dict[str, Any]:
    row = _load(SOAK_FILE)
    return row if isinstance(row, dict) else {}


def score_agent_objectives(
    *,
    plan_bank: dict[str, Any] | None = None,
    soak: dict[str, Any] | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> list[Row]:
    bank = plan_bank if plan_bank is not None else score_plan_bank()
    nights = soak if soak is not None else _soak()
    runs = load_tasks_retests() if retests is None else list(retests)
    bank_ok = bool(bank.get("gate_pass")) and int(bank.get("passed") or 0) == int(bank.get("n") or 0)
    soak_ok = bool(nights.get("soak_complete"))
    live_tasks = "reached" if len(runs) >= CLOSE_RUNS and all(
        r.get("pass") for r in runs[-CLOSE_RUNS:]
    ) else ("partial" if runs else "missing")
    last = runs[-CLOSE_RUNS:] if runs else []

    def from_retest(oid: str, dated: str) -> str:
        if live_tasks == "missing":
            return dated
        if len(last) < CLOSE_RUNS:
            return "partial"
        if all((r.get("objectives") or {}).get(oid) for r in last):
            return "reached"
        return "partial"

    t10 = "missing"
    if len(last) >= CLOSE_RUNS:
        p50s = [
            (r.get("latency") or {}).get("p50_ms")
            for r in last
            if isinstance(r.get("latency"), dict)
        ]
        if len(p50s) == CLOSE_RUNS and all(isinstance(v, (int, float)) for v in p50s):
            t10 = (
                "reached"
                if all(int(v) <= AGENT_P50_BUDGET_MS for v in p50s)
                else "fail"
            )

    rows = [
        Row(
            "T1", "Mode contract",
            "reached" if bank_ok else "fail",
            "ADR-0046 cancels edit_plan on Chat (ap-012). Writes stay on Agent.",
            ("agent_plan_bank.yaml", "ADR-0046"),
        ),
        Row(
            "T2", "RULE_21 consent",
            "reached" if soak_ok else "partial",
            "ESS leave/loan/attendance write is the consent step. Unit templates exist. Soak 5/5 after 23 FAIL.",
            (SOAK_FILE, "PV2-a5-consent-copy-2026-09-23q.md"),
        ),
        Row(
            "T3", "Discuss / apply",
            "reached" if bank_ok else "fail",
            f"Offline plan bank {bank.get('passed')}/{bank.get('n')}. Typed plan_revision, 0-LLM apply.",
            ("agent_plan_bank.yaml",),
        ),
        Row(
            "T4", "Process bind",
            from_retest("T4", "partial"),
            "Nibras process SIM 2026-09-21 PASS. Live Tasks bank must re-bind payroll / GOSI / attendance reads.",
            ("docs/ops/SIM-QA-CHAT-AGENT/SCOREBOARD.md", TASKS_RETEST_GLOB),
        ),
        Row(
            "T5", "SoD / host gate",
            from_retest("T5", "partial"),
            "ADR-0045 unit gates hold. Live Tasks bank must refuse an ungated write and keep Chat off the host.",
            ("ADR-0045", "test_host_sod.py", TASKS_RETEST_GLOB),
        ),
        Row(
            "T6", "Chat → Agent ESS",
            "reached" if soak_ok else "fail",
            "Nightly Chat→Agent→Approve as emp_1067. Streak 5. Night 2026-09-23 FAIL stays on the record.",
            (SOAK_FILE,),
        ),
        Row(
            "T7", "Output honesty",
            from_retest("T7", "partial"),
            "Phantom-success unit exists. Live Tasks bank must match host fields and hide unasked pay.",
            ("test_phantom_success_guard.py", TASKS_RETEST_GLOB),
        ),
        Row(
            "T8", "Cockpit honesty",
            from_retest("T8", "partial"),
            "ADR-0043 four-view cockpit. Live observe results must not claim a host write.",
            ("ADR-0043", TASKS_RETEST_GLOB),
        ),
        Row(
            "T9", "Live Tasks retest",
            live_tasks,
            "Three full PV2-tasks-retest-*.json passes. A partial or browser note does not close T9.",
            (TASKS_RETEST_GLOB,),
        ),
        Row(
            "T10", "Run latency",
            t10,
            f"Agent case p50 ≤ {AGENT_P50_BUDGET_MS} ms on the last {CLOSE_RUNS} full Tasks retests. Not Chat C8.",
            (TASKS_RETEST_GLOB,),
        ),
    ]
    if live_tasks == "missing":
        for row in rows:
            if row.tid in {"T4", "T5", "T7", "T8"} and row.honest == "reached":
                row.honest = "partial"
            if row.tid == "T10" and row.honest == "reached":
                row.honest = "missing"
    return rows


def score_agent_bench(
    *,
    plan_bank: dict[str, Any] | None = None,
    soak: dict[str, Any] | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = score_agent_objectives(plan_bank=plan_bank, soak=soak, retests=retests)
    honest = [r.honest for r in rows]
    reached = sum(1 for s in honest if s == "reached")
    failed = sum(1 for s in honest if s == "fail")
    missing = sum(1 for s in honest if s == "missing")
    if missing or failed:
        verdict = "unmeasured" if missing >= 2 and failed == 0 else "partial"
    elif reached == 10:
        verdict = "reliable"
    else:
        verdict = "partial"
    return {
        "date": "2026-09-26",
        "surface": "tasks",
        "verdict": verdict,
        "reached": reached,
        "failed": failed,
        "partial": sum(1 for s in honest if s == "partial"),
        "missing": missing,
        "n_objectives": 10,
        "rule": (
            "Honest = worst of dated live, unit/offline bank, and last "
            f"{CLOSE_RUNS} full Tasks retest runs. No Tasks retest file → T9 missing. "
            "Stub and Chat scores never upgrade a Tasks miss. L6/L7 not scored."
        ),
        "l6_l7": "not scored",
        "night_2026_09_23": "FAIL stays",
        "objectives": [asdict(r) | {"sources": list(r.sources)} for r in rows],
        "plan_bank": plan_bank if plan_bank is not None else score_plan_bank(),
        "soak": {
            "file": SOAK_FILE,
            "soak_complete": bool((soak if soak is not None else _soak()).get("soak_complete")),
        },
        "tasks_retest_runs": [r.get("_file") for r in (retests if retests is not None else load_tasks_retests())],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pulse Tasks / Agent deep bench")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    report = score_agent_bench()
    print(
        f"tasks {report['reached']}/{report['n_objectives']} "
        f"verdict={report['verdict']} missing={report['missing']}"
    )
    for row in report["objectives"]:
        print(f"  {row['tid']} {row['honest']:8} {row['name']}")
    if args.write:
        OUT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
