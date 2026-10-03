"""Honest-status rules for the Tasks contract, banks, and lab meter.

These tests pin the falsifiable claims of docs/pulse/PULSE-TASKS-CONTRACT.md:
a signed board is never silently promoted, a stale/partial live bank never closes
T9, and the R7/R8/R12 holds stay holds (TL-1, TL-8, TL-10).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ai.eval.agent_deep_bench import (
    CLOSE_RUNS,
    bank_case_ids,
    covers_bank,
    score_agent_bench,
)
from ai.eval.tasks_retest import load_bank
from ai.eval.tasks_workbench import load_cases, score

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPO_ROOT / "docs" / "pulse" / "PULSE-TASKS-CONTRACT.md"
VALID_KINDS = {"observe", "refuse", "handoff"}


# ── contract document ───────────────────────────────────────────────────────

def test_contract_document_exists_and_declares_its_sections():
    text = CONTRACT.read_text(encoding="utf-8")
    for token in ("## 1. Principles", "## 2. Failure taxonomy", "## 3. Benchmark banks",
                  "## 4. Tasks-Production ladder"):
        assert token in text, token
    for prefix in ("TL-", "TF-", "TB-"):
        found = re.findall(rf"\b{prefix}\d+", text)
        assert len(set(found)) >= 10, (prefix, found)
    for level in ("TL0", "TL1", "TL2", "TL3", "TL4", "TL5"):
        assert level in text, level


def test_contract_never_claims_v2_l6_or_l7():
    text = CONTRACT.read_text(encoding="utf-8")
    # Normalize markdown emphasis so "do **not**" reads as "do not".
    flat = re.sub(r"[*`]", "", text).lower()
    for match in re.finditer(r"\bl[67]\b", flat):
        window = flat[max(0, match.start() - 60):match.end() + 60]
        assert any(
            guard in window
            for guard in ("not scored", "do not", "don't", "never", "no level", "not part")
        ), window


# ── retest bank shape ────────────────────────────────────────────────────────

def test_every_retest_case_is_well_formed():
    cases = load_bank()
    assert len(cases) >= 2
    seen: set[str] = set()
    for row in cases:
        cid = row["id"]
        assert cid not in seen, cid
        seen.add(cid)
        assert row.get("kind") in VALID_KINDS, cid
        objectives = row.get("objectives") or []
        assert objectives and all(str(o).startswith("T") for o in objectives), cid
        expect = row.get("expect") or {}
        assert expect, cid
        if row["kind"] == "observe":
            assert row.get("brief"), cid
        else:
            assert row.get("say"), cid


def test_no_retest_case_declares_a_write_surface():
    """Observe/refuse/handoff only — the live bank never writes the host."""
    for row in load_bank():
        expect = row.get("expect") or {}
        assert expect.get("no_mutation") is not False
        # No case may require a mutation; a write bank is TB-06 and needs STACK-HOLD.
        assert "tools_any" not in expect or all(
            "submit" not in tool and "create" not in tool for tool in expect["tools_any"]
        )


def test_bank_case_ids_match_the_loader():
    from ai.eval.tasks_retest import BANK

    doc = yaml.safe_load(BANK.read_text(encoding="utf-8")) or {}
    ids = {row["id"] for row in doc.get("cases") or []}
    assert ids == bank_case_ids()


# ── stale / partial never closes T9 ─────────────────────────────────────────

def _run(stamp: str, cases: list[str]) -> dict:
    return {
        "tier": "live_retest",
        "run_at": stamp,
        "partial": False,
        "pass": True,
        "bank": "tasks_retest_bank.yaml",
        "cases": [{"id": cid} for cid in cases],
        "objectives": {"T4": True, "T5": True, "T7": True, "T8": True, "T9": True},
        "latency": {"p50_ms": 3000},
    }


def test_three_stale_runs_keep_t9_partial():
    ids = sorted(bank_case_ids())
    stale = [_run(f"2026-01-0{i}", ids[:-1]) for i in range(1, CLOSE_RUNS + 1)]
    assert not all(covers_bank(r, set(ids)) for r in stale)
    report = score_agent_bench(
        plan_bank={"n": 1, "passed": 1, "misses": [], "gate_pass": True},
        soak={"soak_complete": True},
        retests=stale,
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T9"] == "partial"
    assert report["verdict"] != "reliable"


# ── pinned holds ─────────────────────────────────────────────────────────────

def test_r7_missing_r8_fail_r12_fail_stay_pinned():
    from ai.eval.tasks_prod_bench import score_kpis

    stub = {"honest": "reached", "note": "ok"}
    rows = {key: dict(stub) for key in (
        "grounded", "bind", "first_turn", "cockpit", "stability",
        "arabic", "latency", "chat",
    )}
    kpis = {k["id"]: k for k in score_kpis(rows)}
    assert kpis["R7"]["honest"] == "missing"
    assert kpis["R8"]["honest"] == "fail"
    assert kpis["R12"]["honest"] == "fail"


def test_workbench_never_scores_live():
    report = score()
    assert report["tier"] == "structural"
    assert "not a Tasks retest" in report["live"]
    assert len(load_cases()) == report["n"]


def test_core_workbench_is_fully_green():
    """The domain-free core (this surface) must pass; pack data is owned elsewhere."""
    core = [case for case in load_cases() if str(case["id"]).startswith("core.")]
    report = score(core)
    assert report["misses"] == [], report["misses"]
    assert report["gate_pass"] is True
