"""Bounded self-repair for the understand call (ADR-0049 §9).

When validation drops a command, or the host rejects a decided read's
arguments, the model sees what was rejected and why, as a tool result on
its own ``emit_decision`` call, and decides once more. Feedback is typed
(``Rejection`` / host status), never a phrase list. One repair per turn;
after that, dropped commands stay dropped and an empty Decision falls
through to the legacy spine. Nothing here writes user-facing text.

Every repaired or unrepairable turn is nominated as a G6 golden candidate,
so a failure the runtime recovered from is also a case the bank learns.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pulse.cognition.turn.repair")

_NOMINATIONS_CAP = 500


def _nominations_file() -> Path:
    return Path(__file__).resolve().parents[3] / "eval" / "pending_understand_nominations.json"


def _reason(code: str, detail: str) -> str:
    if code == "not_on_surface":
        return "not in CATALOG for this user"
    if code == "invalid_args":
        return f"arguments do not match the CATALOG args: {detail}"
    if code == "missing_name":
        return "call_tool needs a CATALOG tool name"
    if code == "host_rejected":
        return f"the host rejected these arguments: {detail}"
    if code == "record_mismatch":
        return f"the read did not return the record the user named: {detail}"
    return detail or code


def rejection_feedback(rejections: list, *, kept: list[str]) -> dict[str, Any]:
    """Tool-result body for a rejected ``emit_decision``."""
    return {
        "status": "rejected",
        "rejected": [
            {"command": r.index, "name": r.name, "reason": _reason(r.code, r.detail)}
            for r in rejections
        ],
        "kept": kept,
        "instruction": (
            "Emit emit_decision again. Name only CATALOG tools and pass the "
            "args each CATALOG line lists. Keep the commands that were kept. "
            "If no CATALOG tool fits, emit answer, clarify, or handoff_agent "
            "in the user's language. Never mention tool names to the user."
        ),
    }


def malformed_feedback(cause: str) -> dict[str, Any]:
    """Tool-result body for an ``emit_decision`` whose shape did not parse."""
    from ai.engine.cognition.turn.decision import COMMAND_OPS

    return {
        "status": "malformed",
        "cause": cause,
        "instruction": (
            "Emit emit_decision again. commands is a JSON array (not a string) "
            "of one to three objects, each with op set to one of: "
            + ", ".join(sorted(COMMAND_OPS))
            + ". Follow the emit_decision schema exactly."
        ),
    }


def host_error_detail(payload: Any) -> str:
    """Short host rejection detail from a failed read payload."""
    if isinstance(payload, dict):
        err = payload.get("error") or payload.get("detail") or payload.get("message")
        if err:
            return str(err)[:300]
    return ""


def _call_of(result: dict | None) -> dict | None:
    for call in (result or {}).get("tool_calls") or []:
        fn = (call or {}).get("function") or {}
        if str(fn.get("name") or "") == "emit_decision":
            args = fn.get("arguments")
            if not isinstance(args, str):
                args = json.dumps(args or {}, ensure_ascii=False, default=str)
            return {
                "id": str(call.get("id") or "emit_decision_0"),
                "type": "function",
                "function": {"name": "emit_decision", "arguments": args},
            }
    return None


def repair_messages(
    messages: list[dict],
    result: dict | None,
    feedback: dict[str, Any],
) -> list[dict] | None:
    """The first exchange plus the rejection as a tool result. None without a call."""
    call = _call_of(result)
    if call is None:
        return None
    return [
        *messages,
        {"role": "assistant", "content": None, "tool_calls": [call]},
        {
            "role": "tool",
            "tool_call_id": call["id"],
            "content": json.dumps(feedback, ensure_ascii=False, default=str),
        },
    ]


def nominate_understand_case(
    *,
    utterance: str,
    audience: list[str] | None,
    raw_ops: list[str],
    final_ops: list[str],
    rejections: list,
    repaired: bool,
    conversation_id: str = "",
) -> None:
    """Queue a G6 candidate for human review. Never raises, never blocks a turn."""
    text = " ".join((utterance or "").split())
    if not text or not rejections:
        return
    codes = sorted({f"{r.code}:{r.name}" for r in rejections})
    item = {
        "utterance": text[:400],
        "audience": list(audience or []),
        "raw_ops": list(raw_ops),
        "final_ops": list(final_ops),
        "rejections": [r.to_dict() for r in rejections],
        "repaired": bool(repaired),
        "conversation_id": str(conversation_id or "")[:64],
        "nominated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_human_review",
    }
    path = _nominations_file()
    try:
        existing: list[dict] = []
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                existing = loaded if isinstance(loaded, list) else []
            except (OSError, ValueError):
                existing = []
        for prior in existing:
            prior_codes = sorted(
                {f"{r.get('code')}:{r.get('name')}" for r in prior.get("rejections") or []}
            )
            if prior.get("utterance") == item["utterance"] and prior_codes == codes:
                return
        existing.append(item)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(existing[-_NOMINATIONS_CAP:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001 — learning must never break a turn
        logger.debug("understand nomination skipped", exc_info=True)
