"""ADR-0056 step 4 — replay real conversations through the understand call.

Every stored user turn in the instance DB is re-asked with its own prior
messages and its owner's persona, through the same prompt, catalog and
validation the runtime uses (``g6_runner.understand_decision``). The report
counts the turns v21 could not finish:

* ``malformed`` — no Decision came back;
* ``unrepairable`` — every command was dropped, even after the one repair;
* ``unknown_route`` — navigate named a place that is not a NAV route;
* ``unknown_handoff`` — handoff_agent named neither ``plan`` nor a catalog write.

Needs the LLM provider and the engine DB. No host call is made.

    cd backend && python -m ai.eval.replay_v21 --write /tmp/replay.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

UNFINISHED = ("malformed", "unrepairable", "unknown_route", "unknown_handoff")


def _turns(limit: int | None) -> list[dict[str, Any]]:
    from ai.models import AIConversation

    turns: list[dict[str, Any]] = []
    for conv in AIConversation.objects.select_related("user").order_by("created_at"):
        history: list[dict[str, str]] = []
        user = conv.user
        user_info = {
            "username": getattr(user, "username", "") or "",
            "is_staff": bool(getattr(user, "is_staff", False)),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
        }
        for msg in conv.messages.order_by("created_at"):
            text = str(msg.content or "").strip()
            if msg.role == "user" and text:
                turns.append({
                    "conversation": str(conv.id),
                    "user_info": user_info,
                    "text": text,
                    "history": list(history),
                })
            if msg.role in {"user", "assistant"} and text:
                history.append({"role": msg.role, "content": text[:1500]})
    return turns[:limit] if limit else turns


def classify(decision: Any, caps: Any, routes: set[str]) -> str:
    """``finished`` or the reason v21 could not finish this Decision."""
    from ai.engine.cognition.turn.pipeline_v21 import lead_command
    from ai.engine.cognition.turn.decision import PLAN_PROCESS_ID

    if decision is None:
        return "malformed"
    lead = lead_command(decision)
    if lead is None:
        return "unrepairable"
    if lead.op == "navigate" and str(lead.target_id or "") not in routes:
        return "unknown_route"
    if lead.op == "handoff_agent":
        target = str(lead.process_id or "")
        if target != PLAN_PROCESS_ID and target not in caps.writes:
            return "unknown_handoff"
    return "finished"


async def _write_checked(decision: Any, turn: dict[str, Any], instance_id: str) -> dict[str, Any]:
    """One writer call. Numbers must be in the message or its history."""
    from ai.engine.cognition.turn.finish import write_answer
    from ai.engine.cognition.turn.grounding import ungrounded_numbers

    try:
        text, _usage = await write_answer(
            decision,
            user_message=turn["text"],
            conversation_history=turn["history"],
            state=None,
            user_info=turn["user_info"],
            instance_config=None,
            retrieval=None,
            instance_id=instance_id,
            conversation_id=turn["conversation"],
        )
    except Exception as exc:  # noqa: BLE001 — one bad write does not stop the replay
        return {"reply": "", "ungrounded": [], "write_error": f"{type(exc).__name__}: {exc}"[:200]}
    allowed = [turn["text"], *(m.get("content") or "" for m in turn["history"])]
    return {
        "reply": (text or "")[:500],
        "ungrounded": ungrounded_numbers(text, allowed),
        "write_error": "" if (text or "").strip() else "empty",
    }


async def replay(*, instance_id: str = "nibras", limit: int | None = None, writer: bool = False) -> dict[str, Any]:
    from asgiref.sync import sync_to_async

    from ai.engine.core.archetypes import load_instance_config
    from ai.engine.cognition.turn.runner_helpers import _scoped_navigation_routes
    from ai.eval.g6_runner import understand_decision

    cfg = load_instance_config(instance_id)
    turns = await sync_to_async(_turns, thread_sensitive=True)(limit)
    rows: list[dict[str, Any]] = []
    for turn in turns:
        routes = {
            str(r.get("name") or "")
            for r in _scoped_navigation_routes(cfg, turn["user_info"]) or []
            if isinstance(r, dict)
        }
        try:
            summary, decision, caps = await understand_decision(
                turn["text"], history=turn["history"], instance_config=cfg,
                instance_id=instance_id, user_info=turn["user_info"], with_decision=True,
            )
            outcome = classify(decision, caps, routes)
        except Exception as exc:  # noqa: BLE001 — record, keep replaying
            summary, outcome, decision = {"op": "error", "detail": f"{type(exc).__name__}: {exc}"[:200]}, "error", None
        rows.append({
            "conversation": turn["conversation"],
            "user": turn["user_info"]["username"],
            "text": turn["text"][:300],
            "outcome": outcome,
            **summary,
        })
        if writer and outcome == "finished" and summary.get("op") == "answer" and decision is not None:
            rows[-1].update(await _write_checked(decision, turn, instance_id))
    ops = Counter(r.get("op") for r in rows)
    outcomes = Counter(r["outcome"] for r in rows)
    unfinished = sum(outcomes.get(k, 0) for k in UNFINISHED)
    written = [r for r in rows if "reply" in r]
    identical = [
        reply for reply, texts in (
            {} if not written else _same_reply(written)
        ).items()
        if len(texts) > 1
    ]
    ungrounded = sum(1 for r in written if r.get("ungrounded") or r.get("write_error"))
    gate = unfinished == 0 and not outcomes.get("error")
    if writer:
        gate = gate and ungrounded == 0 and not identical
    return {
        "instance": instance_id,
        "turns": len(rows),
        "finished": outcomes.get("finished", 0),
        "unfinished": unfinished,
        "errors": outcomes.get("error", 0),
        "outcomes": dict(outcomes),
        "ops": dict(ops),
        "repaired": sum(1 for r in rows if r.get("repaired")),
        "answers_written": len(written),
        "ungrounded_or_empty": ungrounded,
        "identical_replies": len(identical),
        "gate_pass": gate,
        "rows": rows,
    }


def _same_reply(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for row in rows:
        reply = (row.get("reply") or "").strip()
        if reply:
            grouped.setdefault(reply, set()).add(row.get("text") or "")
    return grouped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay stored user turns through understand (ADR-0056)")
    parser.add_argument("--instance", default="nibras")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", metavar="PATH", default=None)
    parser.add_argument("--writer", action="store_true", help="Also write answer turns and check grounding")
    args = parser.parse_args(argv)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    report = asyncio.run(replay(instance_id=args.instance, limit=args.limit, writer=args.writer))
    summary = {k: v for k, v in report.items() if k != "rows"}
    summary["unfinished_rows"] = [
        {k: r.get(k) for k in ("text", "outcome", "op", "api", "process", "detail") if r.get(k) is not None}
        for r in report["rows"] if r["outcome"] != "finished"
    ]
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.write:
        Path(args.write).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"evidence → {args.write}")
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
