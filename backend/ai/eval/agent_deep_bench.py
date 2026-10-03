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

import yaml

from ai.eval.agent_plan_runner import score as score_plan_bank
from ai.eval.intelligence_ladder import SOAK_FILE, _load

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"
OUT_FILE = EVIDENCE / "PV2-agent-deep-2026-09-26.json"
TASKS_RETEST_GLOB = "PV2-tasks-retest-*.json"
TASKS_RETEST_BANK = "tasks_retest_bank.yaml"
BANK_FILE = Path(__file__).resolve().parent / TASKS_RETEST_BANK
CLOSE_RUNS = 3
AGENT_P50_BUDGET_MS = 180_000
#: A lab meter row is grounded in one of these tiers. A missing live tier keeps
#: a live-only objective `missing`; it is never promoted by a stub or a unit bank.
TIERS = ("offline", "unit", "live", "derived")


@dataclass
class Row:
    tid: str
    name: str
    honest: str
    note: str
    sources: tuple[str, ...]
    falsified_by: str
    tier: str


def retest_is_full(row: Any) -> bool:
    """A retest run counts toward T9/T10 only when it is a full live bank.

    ``tier == "live_retest"`` names the live Tasks retest; ``partial`` is only
    ever set by ``--only`` and never closes a bank (TL-8). A run that names a
    different bank is not this surface's evidence.
    """
    if not isinstance(row, dict):
        return False
    if str(row.get("tier") or "") != "live_retest":
        return False
    if bool(row.get("partial")):
        return False
    bank = str(row.get("bank") or "")
    if bank and bank != TASKS_RETEST_BANK:
        return False
    return bool(row.get("cases"))


def bank_case_ids(path: Path = BANK_FILE) -> set[str]:
    """The current bank's case ids. A full run must cover these to close T9."""
    if not path.is_file():
        return set()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = doc.get("cases") if isinstance(doc, dict) else doc
    return {
        str(row["id"])
        for row in rows or []
        if isinstance(row, dict) and row.get("id")
    }


def covers_bank(row: Any, ids: set[str]) -> bool:
    """True when a full run walked every case id of the current bank.

    A bank that grew after a run makes that run stale: it still proves the old
    objectives, but it cannot close T9 for cases it never walked (TL-7).
    """
    if not ids or not isinstance(row, dict):
        return False
    run_ids = {
        str(case.get("id"))
        for case in row.get("cases") or []
        if isinstance(case, dict)
    }
    return ids.issubset(run_ids)


def load_tasks_retests(root: Path = EVIDENCE) -> list[dict[str, Any]]:
    """Full Tasks live retest runs (tier=live_retest, partial=false)."""
    runs = []
    for path in sorted(root.glob(TASKS_RETEST_GLOB)):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if retest_is_full(row):
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
    if retests is None:
        runs = load_tasks_retests()
    else:
        runs = [r for r in retests if retest_is_full(r)]
    ids = bank_case_ids()
    last = runs[-CLOSE_RUNS:] if runs else []
    closed = (
        len(last) == CLOSE_RUNS
        and all(r.get("pass") for r in last)
        and all(covers_bank(r, ids) for r in last)
    )
    stale = bool(runs) and bool(ids) and not all(covers_bank(r, ids) for r in last)
    if not runs:
        live_tasks = "missing"
    elif closed:
        live_tasks = "reached"
    else:
        live_tasks = "partial"
    bank_ok = bool(bank.get("gate_pass")) and int(bank.get("passed") or 0) == int(bank.get("n") or 0)
    soak_ok = bool(nights.get("soak_complete"))
    stale_note = ""
    if stale:
        walked = sorted({
            str(case.get("id"))
            for case in (last[-1].get("cases") or [])
            if isinstance(case, dict)
        })
        stale_note = (
            f" Stale: bank has {len(ids)} cases, last full run walked {len(walked)}. "
            "Fresh full runs are pending."
        )

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
            "agent_plan_runner ap-012 miss — a Chat edit_plan is not cancelled; failure = T1 'fail'.",
            "offline",
        ),
        Row(
            "T2", "RULE_21 consent",
            "reached" if soak_ok else "partial",
            "ESS leave/loan/attendance write is the consent step. Unit templates exist. Soak 5/5 after 23 FAIL.",
            (SOAK_FILE, "PV2-a5-consent-copy-2026-09-23q.md"),
            "PV2-6B-nights.json soak_complete=false, or a night with chat_mutated=true; failure = T2 not reached.",
            "live",
        ),
        Row(
            "T3", "Discuss / apply",
            "reached" if bank_ok else "fail",
            f"Offline plan bank {bank.get('passed')}/{bank.get('n')}. Typed plan_revision, 0-LLM apply.",
            ("agent_plan_bank.yaml",),
            "agent_plan_runner < 12/12, or an apply case with llm_calls != 0; failure = T3 'fail'.",
            "offline",
        ),
        Row(
            "T4", "Process bind",
            from_retest("T4", "partial"),
            "Nibras process SIM 2026-09-21 PASS. Live Tasks bank must re-bind payroll / GOSI / attendance reads.",
            ("docs/ops/SIM-QA-CHAT-AGENT/SCOREBOARD.md", TASKS_RETEST_GLOB),
            "a full retest whose observe tools lack list_payroll_runs / analyze_gosi_committed / list_my_attendance; failure = T4 'partial'.",
            "live",
        ),
        Row(
            "T5", "SoD / host gate",
            from_retest("T5", "partial"),
            "ADR-0045 unit gates hold. Live Tasks bank must refuse an ungated write and keep Chat off the host.",
            ("ADR-0045", "test_host_sod.py", TASKS_RETEST_GLOB),
            "test_host_sod.py red, or a retest with host_write=true; failure = T5 'partial'.",
            "live",
        ),
        Row(
            "T6", "Chat → Agent ESS",
            "reached" if soak_ok else "fail",
            "Nightly Chat→Agent→Approve as emp_1067. Streak 5. Night 2026-09-23 FAIL stays on the record.",
            (SOAK_FILE,),
            "PV2-6B-nights.json soak_complete=false, or host_row_after_agent=false after a confirm 200; failure = T6 'fail'.",
            "live",
        ),
        Row(
            "T7", "Output honesty",
            from_retest("T7", "partial"),
            "Phantom-success unit exists. Live Tasks bank must match host fields and hide unasked pay.",
            ("test_phantom_success_guard.py", TASKS_RETEST_GLOB),
            "test_phantom_success_guard.py red, or a retest observe with a mutation step / leaked pay; failure = T7 'partial'.",
            "live",
        ),
        Row(
            "T8", "Cockpit honesty",
            from_retest("T8", "partial"),
            "ADR-0043 four-view cockpit. Live observe results must not claim a host write.",
            ("ADR-0043", TASKS_RETEST_GLOB),
            "a retest missing plan id/steps/status, or a Result line claiming a write; failure = T8 'partial'.",
            "live",
        ),
        Row(
            "T9", "Live Tasks retest",
            live_tasks,
            (
                "Three full PV2-tasks-retest-*.json passes that cover every current "
                "bank case. A partial, a stale run, or a browser note does not close T9."
                + stale_note
            ),
            (TASKS_RETEST_GLOB, TASKS_RETEST_BANK),
            (
                f"fewer than {CLOSE_RUNS} full PV2-tasks-retest-*.json, a partial:true "
                f"file in the last {CLOSE_RUNS}, or a full run whose cases do not cover "
                f"the current {TASKS_RETEST_BANK}; failure = T9 'reached' without "
                f"{CLOSE_RUNS} covering passes."
            ),
            "live",
        ),
        Row(
            "T10", "Run latency",
            t10,
            (
                f"Agent case p50 ≤ {AGENT_P50_BUDGET_MS} ms on the last {CLOSE_RUNS} "
                "full Tasks retests. Not Chat C8."
                + stale_note
            ),
            (TASKS_RETEST_GLOB,),
            f"a full retest with no latency.p50_ms, or any of the last {CLOSE_RUNS} p50 > {AGENT_P50_BUDGET_MS}; failure = T10 'reached' without {CLOSE_RUNS} p50 values.",
            "live",
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
        "close_runs": CLOSE_RUNS,
        "bank_cases": sorted(bank_case_ids()),
        "rule": (
            "Honest = worst of dated live, unit/offline bank, and last "
            f"{CLOSE_RUNS} full Tasks retest runs. A full run is tier=live_retest, "
            "partial=false, bank=tasks_retest_bank.yaml, with cases that cover every "
            "case id of the current bank. No full retest file → T9/T10 missing; a "
            "partial or a stale run (bank grew after it) never closes a bank. Stub "
            "and Chat scores never upgrade a Tasks miss. L6/L7 not scored."
        ),
        "l6_l7": "not scored",
        "night_2026_09_23": "FAIL stays",
        "objectives": [asdict(r) | {"sources": list(r.sources)} for r in rows],
        "plan_bank": plan_bank if plan_bank is not None else score_plan_bank(),
        "soak": {
            "file": SOAK_FILE,
            "soak_complete": bool((soak if soak is not None else _soak()).get("soak_complete")),
        },
        "tasks_retest_runs": [
            (r.get("_file") or r.get("run_at"))
            for r in (retests if retests is not None else load_tasks_retests())
        ],
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
