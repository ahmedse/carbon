"""Offline scorer for the Agent / plan bank.

No LLM, no network, no Django. Each case calls the same functions the turn
uses: plan-id seed detection, typed ``plan_revision`` state, the shared
affirmation module, the 0-LLM handoff, and the ADR-0046 Chat guard.

CLI::

    python -m ai.eval.agent_plan_runner            # print
    python -m ai.eval.agent_plan_runner --gate     # exit 1 on any miss
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml

from ai.engine.cognition.plan.planner import _is_agent_discuss_turn
from ai.engine.cognition.state_store import ConversationState, resolve_against_state, update_state_from_turn
from ai.engine.cognition.turn.plan_revision import (
    KIND,
    build_revision_handoff,
    build_revision_question,
    is_discuss_turn,
    linked_plan_ref,
)

BANK_PATH = Path(__file__).resolve().parent / "agent_plan_bank.yaml"

_PLAN_ID = "e20c2937-7ece-45b0-8db6-3f40e89ee35d"
_REVISION = "Improved brief: compute variance, validate, report."


def load_bank(path: Path | None = None) -> list[dict[str, Any]]:
    raw = yaml.safe_load((path or BANK_PATH).read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else []
    return [c for c in cases if isinstance(c, dict) and c.get("id")]


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
        if is_discuss_turn(message, state, "plan") != bool(expect.get("discuss", True)):
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
            tool_name="edit_plan",
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

    return f"unknown check {kind}"


def score(path: Path | None = None) -> dict[str, Any]:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent / plan bank")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)
    result = score()
    print(f"agent plan bank  {result['passed']}/{result['n']}  gate={'pass' if result['gate_pass'] else 'FAIL'}")
    for miss in result["misses"]:
        print(f"  {miss['id']}: {miss['why']}")
    if args.gate and not result["gate_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
