"""Map a high-confidence intent onto tool_choice (ADR-0049 P3).

On unless ``PULSE_TOOL_CHOICE=off``. When intent already names one host read
at confidence ≥ 0.9, Draft is forced with named ``tool_choice``.
"""
from __future__ import annotations

import os
from typing import Any

FLAG = "PULSE_TOOL_CHOICE"

# Host self-reads Intent may name. These are call_host_api arguments, not LLM
# function names — inject the GET when Draft skipped them (Q1 leave-force replacement).
_ESS_SELF_READ_APIS = frozenset(
    {
        "get_my_leave_balance",
        "list_my_leave",
        "list_my_loans",
        "list_my_payslips",
        "list_my_attendance_permissions",
        "list_attendance",
    }
)


def tool_choice_enabled() -> bool:
    """Default on (P3). ``PULSE_TOOL_CHOICE=off`` is the kill switch."""
    raw = os.environ.get(FLAG)
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() in {"1", "on", "true"}


def choice_from_resolution(resolution: Any) -> str | dict | None:
    """Named when one host tool is certain. ``required`` when two or three are.

    Returns None when the flag is off, confidence is below 0.9, or no host
    read is needed — Draft then behaves exactly as before.
    """
    if not tool_choice_enabled() or resolution is None:
        return None
    try:
        confidence = float(getattr(resolution, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if confidence < 0.9 or not getattr(resolution, "needs_host_data", False):
        return None
    names: list[str] = []
    for cand in getattr(resolution, "candidates", None) or []:
        name = str(getattr(cand, "name", "") or "").strip()
        if name and name not in names:
            names.append(name)
    if len(names) == 1:
        return {"name": names[0]}
    if 2 <= len(names) <= 3:
        return "required"
    return None


def draft_force_kwargs(resolution: Any, function_names: set[str] | None) -> dict:
    """Kwargs for ``DraftWitness.draft``. Empty when the flag is off."""
    choice = choice_from_resolution(resolution)
    names = function_names or set()
    if choice == "required":
        return {"tool_choice": "required"}
    if isinstance(choice, dict):
        target = str(choice.get("name") or "")
        if target in names:
            return {"tool_choice": {"name": target}}
        if "call_host_api" in names:
            # Host APIs are arguments of call_host_api, not LLM functions.
            return {"tool_choice": {"name": "call_host_api"}}
    return {}


def ensure_forced_call(draft: Any, resolution: Any, turn_id: str, function_names: set[str] | None) -> Any:
    """If Intent named a host GET with certainty, inject call_host_api when Draft skipped it.

    Runs for ESS self-read APIs always (replaces the leave-only post-draft force).
    For other APIs, requires ``PULSE_TOOL_CHOICE=on``.
    """
    choice = choice_from_resolution(resolution)
    api = ""
    if isinstance(choice, dict):
        api = str(choice.get("name") or "")
    elif resolution is not None:
        try:
            confidence = float(getattr(resolution, "confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence >= 0.9 and getattr(resolution, "needs_host_data", False):
            for cand in getattr(resolution, "candidates", None) or []:
                name = str(getattr(cand, "name", "") or "").strip()
                if name in _ESS_SELF_READ_APIS:
                    api = name
                    break
    if not api:
        return draft
    names = function_names or set()
    if api in names:
        return draft
    from dataclasses import replace

    from ai.engine.cognition.turn.ess_read import (
        build_ess_self_tool_call,
        tool_calls_include_api,
    )

    calls = list(getattr(draft, "tool_calls", None) or [])
    if tool_calls_include_api(calls, api):
        return draft
    # Drop the empty history twin when forcing a balance API.
    if api == "get_my_leave_balance":
        calls = [
            tc for tc in calls if not tool_calls_include_api([tc], "list_my_leave")
        ]
    calls.append(build_ess_self_tool_call(api, turn_id or ""))
    return replace(draft, tool_calls=calls, text="")
