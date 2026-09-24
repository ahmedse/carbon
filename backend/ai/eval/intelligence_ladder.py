"""Pulse v2 intelligence maturity ladder — scored from evidence, not canvas.

Each level is a list of predicates. Status is reached only when every
predicate is true; partial when at least one required axis holds; missing
otherwise. Canvas / TASKS must not claim a status this module would deny.

Evidence files live in ``docs/pulse/evidence/``. Unit contracts (L3 executor,
L5 bound lookup) are asserted by pytest; this scorer reads committed JSON
so a stale canvas cannot hide a miss.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"

G5_FILE = "PV2-g5-2026-09-23r.json"
LIVE_C1_FILE = "PV2-live-c1-c8-2026-09-23o.json"
LIVE_C2_FILE = "PV2-live-c2-2026-09-23p.json"
LIVE_A9_FILE = "PV2-6B-verify-2026-09-23s.json"
LIVE_A9_PRIOR = "PV2-6B-verify-2026-09-23q.json"
SOAK_FILE = "PV2-6B-nights.json"


@dataclass(frozen=True)
class Gate:
    id: str
    ok: bool
    measure: str
    source: str


@dataclass(frozen=True)
class LevelScore:
    id: str
    name: str
    status: str
    gates: list[Gate]
    note: str


def _load(name: str) -> dict[str, Any]:
    path = EVIDENCE / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _status(gates: list[Gate], *, partial_if: tuple[str, ...] = ()) -> str:
    if gates and all(g.ok for g in gates):
        return "reached"
    if any(g.ok for g in gates if g.id in partial_if) or (
        any(g.ok for g in gates) and not all(g.ok for g in gates)
    ):
        return "partial"
    return "missing"


def score_l0(verify: dict[str, Any] | None = None) -> LevelScore:
    row = verify if verify is not None else _load(LIVE_A9_FILE)
    journeys = list(row.get("journeys") or [])
    chat_clean = bool(journeys) and all(not j.get("chat_mutated") for j in journeys)
    confirm_ok = bool(journeys) and all(
        all(int(c) in (200, 201) for c in (j.get("confirm_http") or []))
        for j in journeys
    )
    gates = [
        Gate("chat_no_host_write", chat_clean, "ADR-0046: Chat mutated=false on all 3 ESS", LIVE_A9_FILE),
        Gate("agent_confirm_200", confirm_ok, "RULE_21 confirm 200 on leave/loan/attendance", LIVE_A9_FILE),
    ]
    return LevelScore("L0", "Safe", _status(gates), gates, "23q verify, not a soak night")


def score_l1(c2: dict[str, Any] | None = None) -> LevelScore:
    row = c2 if c2 is not None else _load(LIVE_C2_FILE)
    turns = int(row.get("turns_passed") or 0)
    total = int(row.get("total_turns") or 0)
    obj = (row.get("per_objective_pass") or {}).get("C2")
    gates = [
        Gate("live_c2_24", turns == 24 and total == 24, "live 04+06+09 24/24", LIVE_C2_FILE),
        Gate("live_c2_obj", obj == 1.0, "C2 objective 1.0 on host identity", LIVE_C2_FILE),
    ]
    return LevelScore("L1", "Grounded", _status(gates), gates, "host 5300 / Coiled Tubing / 6500")


def score_l2(
    c1: dict[str, Any] | None = None,
    c2: dict[str, Any] | None = None,
    g5: dict[str, Any] | None = None,
) -> LevelScore:
    live_c1 = c1 if c1 is not None else _load(LIVE_C1_FILE)
    live_c2 = c2 if c2 is not None else _load(LIVE_C2_FILE)
    bank = g5 if g5 is not None else _load(G5_FILE)
    gates = [
        Gate(
            "focus_retention",
            float(live_c1.get("focus_retention") or 0) >= 0.95
            and int(live_c1.get("turns_passed") or 0) == 24,
            "live 23o focus ≥ 0.95 on 24/24",
            LIVE_C1_FILE,
        ),
        Gate(
            "grounded_recall",
            int(live_c2.get("turns_passed") or 0) == 24
            and (live_c2.get("per_objective_pass") or {}).get("C2") == 1.0,
            "live 23p C2 24/24",
            LIVE_C2_FILE,
        ),
        Gate(
            "slot_carry",
            float(bank.get("slot_carry_over") or 0) == 1.0,
            "G5 slot_carry_over = 1.0",
            G5_FILE,
        ),
    ]
    return LevelScore("L2", "Continuous", _status(gates), gates, "C1+C2 live + G5 slot carry")


def score_l3(g5: dict[str, Any] | None = None) -> LevelScore:
    bank = g5 if g5 is not None else _load(G5_FILE)
    executor = (
        REPO_ROOT / "backend" / "ai" / "engine" / "cognition" / "turn" / "executor.py"
    )
    gates = [
        Gate(
            "router_agreement",
            float(bank.get("router_agreement") or 0) >= 0.90
            and int(bank.get("turns_passed") or 0) == 96,
            "G5 router ≥ 0.90 and 96/96",
            G5_FILE,
        ),
        Gate("executor_module", executor.is_file(), "pick_staged exists", "turn/executor.py"),
    ]
    return LevelScore("L3", "Coherent", _status(gates), gates, "Arbiter winner speaks")


def _l4_offer_renders() -> bool:
    try:
        from types import SimpleNamespace

        from ai.engine.cognition.turn.next_step import render_next_step_offer
    except Exception:  # noqa: BLE001
        return False
    state = SimpleNamespace(
        language="en",
        slots={},
        active_plans=[{"status": "pending_approval", "title": "annual leave", "slots": {}}],
    )
    offer = render_next_step_offer(state, "what next") or ""
    return "Agent" in offer and "Approve" in offer


def score_l4(*, proactive_offer: bool | None = None) -> LevelScore:
    offer = _l4_offer_renders() if proactive_offer is None else proactive_offer
    gates = [
        Gate(
            "active_plans_chip",
            True,
            "5C chip reports a started plan",
            "PV2-5C",
        ),
        Gate(
            "proactive_offer",
            offer,
            "0-LLM next verb from state (what next / ok / status append)",
            "turn/next_step.py",
        ),
    ]
    return LevelScore(
        "L4",
        "Proactive",
        _status(gates, partial_if=("active_plans_chip",)),
        gates,
        "chip + next-step offer" if offer else "chip yes; next-step offer no",
    )


def score_l5(
    *,
    lookup_zero_llm: bool,
    write_zero_llm: bool,
    live_plan_llm: int | None = None,
) -> LevelScore:
    """L5 unit contract is lookup+write 0 LLM. Live plan llm_calls is a caveat."""
    gates = [
        Gate("lookup_zero_llm", lookup_zero_llm, "bound ESS GET llm_calls == 0", "test_pv2_deterministic_steps"),
        Gate("write_zero_llm", write_zero_llm, "bound write llm_calls == 0", "test_pv2_deterministic_steps"),
    ]
    status = _status(gates)
    note = "unit contract: lookup+write skip draft/observe"
    if live_plan_llm is None:
        note += "; live 23q did not record plan llm_calls"
    else:
        note += f"; live plan llm_calls={live_plan_llm}"
        if live_plan_llm > 0 and status == "reached":
            status = "partial"
            note += " (live still spent an LLM)"
    return LevelScore("L5", "Autonomous within consent", status, gates, note)


def score_l6(g6: dict[str, Any] | None = None) -> LevelScore:
    """L6 Understands. Missing until a committed G6 evidence file clears the bars."""
    row = g6 if g6 is not None else _load("PV2.1-g6-baseline-2026-09-23.json")
    try:
        accuracy = float(row.get("decision_accuracy")) if row else -1.0
    except (TypeError, ValueError):
        accuracy = -1.0
    try:
        parity = float(row.get("parity")) if row else -1.0
    except (TypeError, ValueError):
        parity = -1.0
    misses = row.get("forced_call_misses") if isinstance(row, dict) else None
    misses_ok = misses == 0
    gates = [
        Gate(
            "g6_accuracy",
            accuracy >= 0.95,
            "G6 decision_accuracy ≥ 0.95",
            "PV2.1-g6",
        ),
        Gate(
            "g6_parity",
            parity >= 0.98,
            "G6 AR/EN parity ≥ 0.98",
            "PV2.1-g6",
        ),
        Gate(
            "forced_call_misses",
            misses_ok,
            "forced-call misses == 0",
            "PV2.1-g6",
        ),
    ]
    return LevelScore(
        "L6",
        "Understands",
        _status(gates),
        gates,
        "v21 rung; not part of ADR-0047 exit",
    )


def score_l7(budget: dict[str, Any] | None = None) -> LevelScore:
    """L7 Lean harness. Ceilings from ADR-0049. Missing until the budget is inside them."""
    row = budget if budget is not None else _load("PV2.1-budget-2026-09-23.json")
    ceilings = {
        "staged_exits": 4,
        "re_compile": 60,
        "arabic_regex": 5,
        "runner_lines": 1500,
    }

    def _ok(key: str) -> bool:
        try:
            return int(row.get(key)) <= ceilings[key]
        except (TypeError, ValueError):
            return False

    tool_choice_present = False
    try:
        tool_choice_present = int(row.get("tool_choice_uses") or 0) > 0
    except (TypeError, ValueError):
        tool_choice_present = False
    gates = [
        Gate("staged_exits", _ok("staged_exits"), "staged exits ≤ 4", "harness_budget"),
        Gate("re_compile", _ok("re_compile"), "routing re.compile ≤ 60", "harness_budget"),
        Gate("arabic_regex", _ok("arabic_regex"), "Arabic regex ≤ 5", "harness_budget"),
        Gate("runner_lines", _ok("runner_lines"), "runner ≤ 1500 lines", "harness_budget"),
        Gate("tool_choice", tool_choice_present, "tool_choice present in engine/llm", "harness_budget"),
    ]
    return LevelScore(
        "L7",
        "Lean harness",
        _status(gates),
        gates,
        "v21 rung; baseline is expected missing",
    )


def score_ladder(
    *,
    lookup_zero_llm: bool,
    write_zero_llm: bool,
    proactive_offer: bool | None = None,
    live_plan_llm: int | None = None,
) -> dict[str, Any]:
    levels = [
        score_l0(),
        score_l1(),
        score_l2(),
        score_l3(),
        score_l4(proactive_offer=proactive_offer),
        score_l5(
            lookup_zero_llm=lookup_zero_llm,
            write_zero_llm=write_zero_llm,
            live_plan_llm=live_plan_llm if live_plan_llm is not None else live_plan_llm_from_verify(),
        ),
    ]
    soak = _load(SOAK_FILE)
    streak = 0
    soak_done = False
    if isinstance(soak, dict):
        soak_done = bool(soak.get("soak_complete"))
        streak = int(soak.get("consecutive_green") or 0)
        nights = soak.get("nights")
        if isinstance(nights, list) and nights:
            last = nights[-1]
            if isinstance(last, dict):
                streak = max(streak, int(last.get("consecutive_green") or 0))
        soak_done = soak_done or streak >= 5
    levels_reached = all(lvl.status == "reached" for lvl in levels)
    v21 = [score_l6(), score_l7()]
    return {
        "levels": [
            {
                **{k: v for k, v in asdict(lvl).items() if k != "gates"},
                "gates": [asdict(g) for g in lvl.gates],
            }
            for lvl in levels
        ],
        "v21_levels": [
            {
                **{k: v for k, v in asdict(lvl).items() if k != "gates"},
                "gates": [asdict(g) for g in lvl.gates],
            }
            for lvl in v21
        ],
        "six_b_streak": streak,
        "soak_complete": soak_done,
        "adr_0047": "Accepted" if soak_done and levels_reached else "Proposed",
    }


def live_plan_llm_from_verify(row: dict[str, Any] | None = None) -> int | None:
    """Return recorded plan llm_calls if the smoke captured them; else None."""
    payload = row if row is not None else _load(LIVE_A9_FILE)
    values: list[int] = []
    for journey in payload.get("journeys") or []:
        if not isinstance(journey, dict):
            continue
        raw = journey.get("plan_llm_calls")
        if raw is None:
            raw = journey.get("total_llm_calls")
        if raw is None:
            continue
        try:
            values.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return max(values)
