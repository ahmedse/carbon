"""Offline scorer for the Pulse **Plan** surface.

No LLM, no network, no Django. Each case calls the same functions the turn
uses: plan-id seed detection, typed ``plan_revision`` state, the shared
affirmation module, the 0-LLM handoff, the ADR-0046 Chat guard, the
read-vs-goal proposal boundary, await-user pause/resume, guard typing, and the
ADR-0052 plan contract.

Two banks, one gate:

* ``agent_plan_bank.yaml`` — path cases (seed, continuity, commit, guard,
  proposal, await_user, affirmation).
* ``plan_contract_bank.yaml`` — the ADR-0052 contract goldens (shapes, not
  model output).

CLI::

    python -m ai.eval.agent_plan_runner            # print
    python -m ai.eval.agent_plan_runner --gate     # exit 1 on any miss
    python -m ai.eval.agent_plan_runner --write    # write docs/pulse/evidence/PV2-plan-offline-<date>.json
    python -m ai.eval.agent_plan_runner --list     # inventory, no scoring

Contract: ``docs/pulse/PULSE-PLAN-CONTRACT.md``. Numbers reported here are
offline only; they never claim a live rung.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ai.engine.cognition.dialogue.affirmation import (
    is_affirmation,
    is_commit_affirmation,
    starts_with_affirmation,
)
from ai.engine.cognition.plan.contract import (
    apply_plan_contract,
    evidence_rows,
    guard_choice,
    guard_outcome,
)
from ai.engine.cognition.plan.loop import (
    pause_for_user_answer,
    resume_answered_clarification,
)
from ai.engine.cognition.plan.planner import PlanStep, _is_agent_discuss_turn
from ai.engine.cognition.state_store import (
    ConversationState,
    resolve_against_state,
    update_state_from_turn,
)
from ai.engine.cognition.turn.plan_proposal import (
    draft_was_cancelled,
    is_task_plan,
    proposal_payload,
    stick_to_open_draft,
)
from ai.engine.cognition.turn.plan_revision import (
    KIND,
    build_revision_handoff,
    build_revision_question,
    is_discuss_turn,
    linked_plan_ref,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"

BANK_PATH = Path(__file__).resolve().parent / "agent_plan_bank.yaml"
CONTRACT_BANK_PATH = Path(__file__).resolve().parent / "plan_contract_bank.yaml"

_PLAN_ID = "e20c2937-7ece-45b0-8db6-3f40e89ee35d"
_REVISION = "Improved brief: compute variance, validate, report."


# ── ADR-0052 catalog (shapes only; mirrors the plan contract goldens) ─────────
# The same catalog the contract goldens are authored against. Duplicated here so
# the runner scores ``plan_contract_bank.yaml`` with no Django / test import.

PLAN_CONTRACT_CATALOG: list[dict[str, Any]] = [
    {"name": "list_payroll_runs", "method": "GET", "path": "/payroll-runs/",
     "returns": ["id", "status"]},
    {"name": "validate_payroll_run", "method": "POST",
     "path": "/payroll-runs/{id}/validate/", "requires_confirmation": True},
    {"name": "analyze_employees", "method": "GET", "path": "/people/analytics/",
     "parameters": {"type": "object", "required": ["dimension"],
                    "properties": {"dimension": {"enum": ["org_unit"]}}},
     "returns": ["headcount"]},
    {"name": "list_payslip_lines", "method": "GET", "path": "/payslip-lines/",
     "returns": ["id", "employee", "line_type", "amount", "payroll_run"]},
    {"name": "list_employees", "method": "GET", "path": "/employees/"},
    {"name": "analyze_committed_pay", "method": "GET",
     "path": "/payslip-lines/summary/",
     "returns": ["label", "headcount", "average", "median", "min", "max", "total",
                 "period_end", "dimension", "line_type", "status"]},
    {"name": "analyze_kuwaitization", "method": "GET",
     "path": "/people/compliance/kuwaitization/",
     "returns": ["label", "contract_no", "required", "actual", "deficit",
                 "fill_rate_pct", "status"]},
    {"name": "analyze_leave_utilization", "method": "GET",
     "path": "/leave-entitlements/summary/",
     "returns": ["label", "headcount", "entitled_days", "used_days",
                 "remaining_days", "utilization_pct"]},
    {"name": "analyze_loan_book", "method": "GET", "path": "/loans/summary/",
     "returns": ["label", "count", "principal_total", "remaining_total"]},
    {"name": "analyze_gosi_committed", "method": "GET",
     "path": "/payslip-lines/gosi-summary/",
     "returns": ["label", "headcount", "average", "median", "min", "max", "total",
                 "period_end", "dimension", "line_type", "status"]},
    {"name": "analyze_cert_expiry", "method": "GET", "path": "/certifications/summary/",
     "returns": ["label", "expired", "expiring", "current"]},
    {"name": "analyze_leave_presence", "method": "GET",
     "path": "/leave-records/presence/",
     "returns": ["label", "on_leave_count", "days"]},
    {"name": "list_leave_entitlements", "method": "GET",
     "path": "/leave-entitlements/",
     "returns": ["id", "employee", "employee_no", "employee_name", "leave_type",
                 "entitled_days", "used_days", "carried_forward"]},
    {"name": "list_loans", "method": "GET", "path": "/loans/",
     "returns": ["id", "employee", "employee_no", "employee_name", "loan_type",
                 "principal", "interest_rate", "term_months", "start_date", "status"]},
]
PLAN_CONTRACT_NAMES = {e["name"] for e in PLAN_CONTRACT_CATALOG}


# ── Bank loading ──────────────────────────────────────────────────────────────


def load_bank(path: Path | None = None) -> list[dict[str, Any]]:
    raw = yaml.safe_load((path or BANK_PATH).read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else []
    return [c for c in cases if isinstance(c, dict) and c.get("id")]


def load_contract_bank(path: Path | None = None) -> list[dict[str, Any]]:
    raw = yaml.safe_load((path or CONTRACT_BANK_PATH).read_text(encoding="utf-8"))
    cases = (raw or {}).get("cases") if isinstance(raw, dict) else raw
    return [c for c in (cases or []) if isinstance(c, dict) and c.get("id")]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_message() -> str:
    return (
        f'I\'d like to refine plan (plan {_PLAN_ID}): "Compute payroll variance".\n\n'
        "DISCUSSION ONLY — reply in Chat with one improved brief."
    )


def _after_discuss_reply() -> ConversationState:
    state = ConversationState()
    ref = linked_plan_ref(state, _seed_message())
    update_state_from_turn(
        state,
        decision="answer",
        user_message=_seed_message(),
        response_text=_REVISION,
        open_question=build_revision_question(ref or {"plan_id": _PLAN_ID}, _REVISION),
    )
    return state


def _step(data: dict[str, Any]) -> PlanStep:
    return PlanStep(
        step_id=data["step_id"],
        intent=data.get("intent", ""),
        tool_name=data.get("tool_name"),
        tool_args=data.get("tool_args") or {},
        depends_on=data.get("depends_on") or [],
        is_mutation=bool(data.get("is_mutation", False)),
        gap=data.get("gap"),
        guard=data.get("guard"),
        await_user=bool(data.get("await_user", False)),
        agent_role=data.get("agent_role", "orchestrator"),
    )


def _int_keys(mapping: dict | None) -> dict:
    out: dict = {}
    for key, value in (mapping or {}).items():
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            out[key] = value
    return out


def _contract_steps_and_findings(raw_steps: list[dict], utterance: str = ""):
    steps = [_step(s) for s in raw_steps]
    findings = apply_plan_contract(
        steps, api_catalog=PLAN_CONTRACT_CATALOG,
        catalog_names=PLAN_CONTRACT_NAMES, utterance=utterance,
    )
    plan = {
        "id": "runner-plan",
        "steps": [
            {"step_id": s.step_id, "intent": s.intent, "tool_name": s.tool_name,
             "tool_args": s.tool_args, "depends_on": s.depends_on, "gap": s.gap,
             "is_mutation": s.is_mutation}
            for s in steps
        ],
    }
    return steps, findings, plan


# ── Plan-bank checks ──────────────────────────────────────────────────────────


def _check(case: dict[str, Any]) -> str:
    """Return '' when the case holds, otherwise a short reason."""
    kind = case.get("check")
    expect = case.get("expect") or {}
    message = str(case.get("message") or "")
    process = case.get("process")

    if kind == "seed":
        state = ConversationState()
        discuss = is_discuss_turn(message, state, process)
        if discuss != bool(expect.get("discuss")):
            return f"discuss={discuss}"
        if "plan_id" in expect:
            ref = linked_plan_ref(state, message) or {}
            if ref.get("plan_id") != expect["plan_id"]:
                return f"plan_id={ref.get('plan_id')}"
        if "seed" in expect and _is_agent_discuss_turn(message) != bool(expect["seed"]):
            return f"seed={_is_agent_discuss_turn(message)}"
        return ""

    if kind == "continuity":
        state = _after_discuss_reply()
        if is_discuss_turn(message, state, process or "plan") != bool(expect.get("discuss", True)):
            return "continuity lost"
        resolved = resolve_against_state(message, state) is not None
        if resolved != bool(expect.get("resolved")):
            return f"resolved={resolved}"
        return ""

    if kind == "commit":
        state = _after_discuss_reply()
        confirm = resolve_against_state(message, state)
        resolved = confirm is not None and confirm.get("kind") == KIND
        if resolved != bool(expect.get("resolved", True)):
            return f"resolved={resolved}"
        if expect.get("discuss") and not is_discuss_turn(message, state, "plan"):
            return "left discuss"
        if not resolved:
            return ""
        response = build_revision_handoff(confirm, message)
        if "llm_calls" in expect and response.llm_calls != expect["llm_calls"]:
            return f"llm_calls={response.llm_calls}"
        action = (response.actions or [{}])[0]
        if expect.get("action_type") and action.get("type") != expect["action_type"]:
            return f"action={action.get('type')}"
        if expect.get("panel") and action.get("panel") != expect["panel"]:
            return f"panel={action.get('panel')}"
        if expect.get("plan_id") and action.get("plan_id") != expect["plan_id"]:
            return f"plan_id={action.get('plan_id')}"
        if expect.get("plan_id") and not action.get("revision"):
            return "revision missing"
        if expect.get("label") and action.get("label") != expect["label"]:
            return f"label={action.get('label')}"
        return ""

    if kind == "ess_confirm":
        state = ConversationState()
        state.open_question = {
            "kind": "confirm_api",
            "confirm": {"api": "get_my_leave_balance"},
            "text": "Show your balance?",
        }
        resolved = resolve_against_state(message, state) is not None
        if resolved != bool(expect.get("resolved")):
            return f"resolved={resolved}"
        return ""

    if kind == "chat_guard":
        from ai.engine.agent.guardrails import HookContext, chat_surface_hook

        ctx = HookContext(
            tool_name=str(case.get("tool_name") or "edit_plan"),
            tool_args={"plan_id": _PLAN_ID},
            instance_id="x",
            host_user_id=1,
            surface="chat",
            process_mode="plan",
            user_message="apply",
        )
        result = asyncio.run(chat_surface_hook(ctx))
        if result.action != expect.get("action"):
            return f"action={result.action}"
        if expect.get("flag") and expect["flag"] not in (result.flags or []):
            return f"flags={result.flags}"
        return ""

    if kind == "proposal":
        if "message" in case:
            cancelled = draft_was_cancelled(message)
            if cancelled != bool(expect.get("cancelled")):
                return f"cancelled={cancelled}"
            return ""
        raw_steps = (case.get("plan") or {}).get("steps") or []
        if case.get("contract"):
            _, findings, plan = _contract_steps_and_findings(raw_steps, str(case.get("brief") or ""))
        else:
            findings = None
            plan = case.get("plan") or {}
        if "is_task" in expect and is_task_plan(plan) != bool(expect["is_task"]):
            return f"is_task={is_task_plan(plan)}"
        payload = proposal_payload(
            plan, brief=str(case.get("brief") or ""),
            findings=findings, single_read=bool(case.get("single_read")),
        )
        if "payload" in expect and (payload is not None) != bool(expect["payload"]):
            return f"payload={payload is not None}"
        if payload is None:
            return ""
        if expect.get("kind") and payload.get("kind") != expect["kind"]:
            return f"kind={payload.get('kind')}"
        if "blocked_count" in expect and payload.get("blocked_count") != expect["blocked_count"]:
            return f"blocked_count={payload.get('blocked_count')}"
        if "blocks_create" in expect and bool(payload.get("blocks_create")) != bool(expect["blocks_create"]):
            return f"blocks_create={payload.get('blocks_create')}"
        return ""

    if kind == "stick":
        state = _after_discuss_reply()
        state.open_question = {
            "kind": "plan_proposal", "brief": "lowest 20 salaries",
            "plan_json": {"steps": [{"step_id": 1, "intent": "Read"}]},
        }
        held = stick_to_open_draft(state.open_question, change=bool(case.get("change")))
        if (held is not None) != bool(expect.get("held")):
            return f"held={held is not None}"
        return ""

    if kind == "await_user":
        step = _step(case["step"])
        if "answered_token" in case:
            result = resume_answered_clarification(step, case.get("answered_token"))
            if (result is not None) != bool(expect.get("resumed")):
                return f"resumed={result is not None}"
            if result is not None and "executed" in expect and result.executed != bool(expect["executed"]):
                return f"executed={result.executed}"
            return ""
        result = pause_for_user_answer(step, case.get("tool_output"))
        if (result is not None) != bool(expect.get("paused")):
            return f"paused={result is not None}"
        if result is not None:
            if "executed" in expect and result.executed != bool(expect["executed"]):
                return f"executed={result.executed}"
            if expect.get("draft_text") and result.draft_text != expect["draft_text"]:
                return f"draft_text={result.draft_text!r}"
        return ""

    if kind == "guard":
        step = _step(case["step"]) if case.get("step") else None
        outputs = _int_keys(case.get("outputs"))
        if "outcome" in expect and step is not None:
            got = guard_outcome(step, outputs)
            if got != expect["outcome"]:
                return f"outcome={got}"
        if "choice_kind" in expect and step is not None:
            choice = guard_choice(step)
            if choice.get("kind") != expect["choice_kind"]:
                return f"choice_kind={choice.get('kind')}"
            if expect.get("choice_step") is not None and choice.get("step") != expect["choice_step"]:
                return f"choice_step={choice.get('step')}"
            if expect.get("choice_values") is not None:
                values = [o.get("value") for o in choice.get("options") or []]
                if values != expect["choice_values"]:
                    return f"choice_values={values}"
        if "evidence_ok" in expect:
            rows = evidence_rows(case.get("depends_on") or [], _int_keys(case.get("statuses")))
            if [r["ok"] for r in rows] != expect["evidence_ok"]:
                return f"evidence_ok={[r['ok'] for r in rows]}"
        return ""

    if kind == "affirmation":
        checks = {
            "is_affirmation": is_affirmation(message),
            "is_commit": is_commit_affirmation(message),
            "starts_with": starts_with_affirmation(message),
        }
        for key in ("is_affirmation", "is_commit", "starts_with"):
            if key in expect and checks[key] != bool(expect[key]):
                return f"{key}={checks[key]}"
        return ""

    if kind == "contract":
        steps, findings, _ = _contract_steps_and_findings(
            case.get("steps") or [], str(case.get("brief") or ""),
        )
        blocked = [f.code for f in findings if f.blocks]
        if blocked != (case.get("blocking") or []):
            return f"blocking={blocked} want={case.get('blocking')}"
        if "tool_names" in expect:
            got = {s.step_id: s.tool_name for s in steps}
            for sid, name in (expect["tool_names"] or {}).items():
                if got.get(int(sid), "__missing__") != name:
                    return f"step {sid} tool={got.get(int(sid))!r} want={name!r}"
        return ""

    return f"unknown check {kind}"


# ── Scoring ───────────────────────────────────────────────────────────────────


def score_plan(path: Path | None = None) -> dict[str, Any]:
    cases = load_bank(path)
    misses = []
    for case in cases:
        why = _check(case)
        if why:
            misses.append({"id": case["id"], "why": why})
    n = len(cases)
    return {
        "n": n,
        "passed": n - len(misses),
        "misses": misses,
        "gate_pass": n > 0 and not misses,
    }


def score_contract(path: Path | None = None) -> dict[str, Any]:
    cases = load_contract_bank(path)
    misses = []
    for case in cases:
        steps = [_step(s) for s in case.get("steps") or []]
        findings = apply_plan_contract(
            steps, api_catalog=PLAN_CONTRACT_CATALOG,
            catalog_names=PLAN_CONTRACT_NAMES,
        )
        blocked = [f.code for f in findings if f.blocks]
        if blocked != (case.get("blocking") or []):
            misses.append({
                "id": case["id"],
                "why": f"blocking={blocked} want={case.get('blocking')}",
            })
    n = len(cases)
    return {
        "n": n,
        "passed": n - len(misses),
        "misses": misses,
        "gate_pass": n > 0 and not misses,
    }


def score(path: Path | None = None, contract_path: Path | None = None) -> dict[str, Any]:
    """Combined offline gate: path cases + ADR-0052 contract goldens."""
    plan = score_plan(path)
    contract = score_contract(contract_path)
    misses = list(plan["misses"]) + [
        {**m, "id": f"{m['id']} [contract]"} for m in contract["misses"]
    ]
    n = plan["n"] + contract["n"]
    passed = plan["passed"] + contract["passed"]
    return {
        "n": n,
        "passed": passed,
        "misses": misses,
        "gate_pass": n > 0 and not misses,
        "plan_bank": plan,
        "contract_bank": contract,
    }


def inventory(path: Path | None = None, contract_path: Path | None = None) -> list[dict[str, Any]]:
    rows = []
    for case in load_bank(path):
        rows.append({"id": case["id"], "check": case.get("check"), "bank": "agent_plan_bank"})
    for case in load_contract_bank(contract_path):
        rows.append({"id": case["id"], "check": "contract", "bank": "plan_contract_bank"})
    return rows


# ── CLI ───────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pulse Plan offline bank")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--write", action="store_true", help="write the dated offline evidence file")
    parser.add_argument("--list", action="store_true", help="print the case inventory; no scoring")
    args = parser.parse_args(argv)

    if args.list:
        rows = inventory()
        for row in rows:
            print(f"{row['bank']:20s} {row['check'] or '':12s} {row['id']}")
        print(f"total {len(rows)} cases")
        return 0

    result = score()
    plan = result["plan_bank"]
    contract = result["contract_bank"]
    print(
        f"plan bank  {result['passed']}/{result['n']}  "
        f"path={plan['passed']}/{plan['n']} contract={contract['passed']}/{contract['n']}  "
        f"gate={'pass' if result['gate_pass'] else 'FAIL'}"
    )
    for miss in result["misses"]:
        print(f"  {miss['id']}: {miss['why']}")

    if args.write:
        payload = {
            "tier": "plan_offline",
            "surface": "agent_plan",
            "run_at": date.today().isoformat(),
            "bank_files": [BANK_PATH.name, CONTRACT_BANK_PATH.name],
            "total": result["n"],
            "passed": result["passed"],
            "gate_pass": result["gate_pass"],
            "plan_bank": plan,
            "contract_bank": contract,
            "inventory": inventory(),
            "honest": (
                "Offline, 0-LLM, deterministic. A pass here does not close a "
                "live Plan rung (PULSE-PLAN-CONTRACT §5/§6)."
            ),
        }
        path = EVIDENCE / f"PV2-plan-offline-{date.today().isoformat()}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    if args.gate and not result["gate_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
