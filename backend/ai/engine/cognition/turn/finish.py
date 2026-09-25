"""v21 finishes every op the understand call emits (ADR-0056).

``answer`` and ``set_slot`` are written by one writer call. ``navigate`` opens
the route the Decision named. Nothing here reads the user's wording to decide
what the turn is: the Decision already decided.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.engine.cognition.turn.decision import Command, Decision

logger = logging.getLogger("pulse.cognition.turn.finish")

ANSWER_TASK = (
    "TASK — Write the reply to the user's last message.\n"
    "Understanding already decided this turn is answered in words, with no "
    "live read. What it understood: {reason}\n"
    "Use the identity, state, history, knowledge and memory blocks above. "
    "Do not say you looked anything up, saved it, or changed it. "
    "Do not invent figures, names or dates. Reply in the user's language."
)


def navigation_for(cmd: Command, instance_config: dict | None, language: str):
    """The declared route the Decision named, or an empty resolution.

    The model is shown the route names; it names one. Matching words to
    routes is its job, so an unknown name is not guessed at here.
    """
    from ai.engine.cognition.turn.navigation import NavigationResolution, load_targets

    wanted = (cmd.target_id or cmd.name or "").strip()
    if not wanted:
        return NavigationResolution()
    for target in load_targets(instance_config):
        if target.name == wanted:
            return NavigationResolution(
                action="navigate", targets=[target], lang=language, matched=wanted,
            )
    return NavigationResolution()


def remember_slot(cmd: Command, state: Any) -> None:
    """``set_slot`` writes the value the user gave into ConversationState."""
    key = (cmd.key or "").strip()
    if not key or state is None:
        return
    slots = getattr(state, "slots", None)
    if not isinstance(slots, dict):
        return
    slots[key] = cmd.value


async def write_answer(
    decision: Decision,
    *,
    user_message: str,
    conversation_history: list[dict] | None,
    state: Any,
    user_info: dict | None,
    instance_config: dict | None,
    retrieval: Any,
    instance_id: str,
    conversation_id: str,
) -> tuple[str, dict]:
    """One writer call, retried once when empty or a number is not in the conversation.

    A second ungrounded or empty reply returns no text. The caller shows a
    typed error. The prose is never cut.
    """
    from ai.engine.cognition.context_pack import build_context_pack
    from ai.engine.cognition.turn.grounding import ungrounded_numbers
    from ai.engine.llm.call_meter import stage
    from ai.engine.llm.router import route_chat

    history = list(conversation_history or [])[-8:]
    pack = build_context_pack(
        state,
        surface="chat",
        stage="draft",
        user_info=user_info,
        instance_config=instance_config,
        conversation_history=history,
        retrieval=retrieval,
        language=decision.language,
        task_body=ANSWER_TASK.format(reason=(decision.reason or "").strip() or "-"),
        include_state=True,
        include_history=False,
        include_knowledge=True,
        include_memory=True,
    )
    allowed = [
        user_message or "",
        pack.system_prompt(),
        *(str(m.get("content") or "") for m in history if isinstance(m, dict)),
        *(
            str(row.get("digest") or "")
            for row in (getattr(state, "last_results", None) or [])
            if isinstance(row, dict)
        ),
    ]
    messages = [{"role": "system", "content": pack.system_prompt()}, *history]
    messages.append({"role": "user", "content": user_message or ""})
    note = ""
    text = ""
    usage = {"tokens": 0, "model": "", "cause": ""}
    for _attempt in range(2):
        sent = [*messages, {"role": "user", "content": note}] if note else messages
        with stage("answer"):
            result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"answer-{conversation_id}",
                messages=sent,
                temperature=0.3,
            )
        result = result if isinstance(result, dict) else {}
        usage["tokens"] += int(result.get("input_tokens") or 0) + int(result.get("output_tokens") or 0)
        usage["model"] = str(result.get("model") or usage["model"])
        text = str(result.get("content") or "").strip()
        bad = ungrounded_numbers(text, allowed)
        if not text:
            usage["cause"] = "empty_output"
            note = (
                "(Write a short reply from the conversation. "
                "Use only numbers that appear in it.)"
            )
            continue
        if bad:
            usage["cause"] = "ungrounded"
            note = (
                "(These numbers are not in the conversation: "
                f"{', '.join(bad[:8])}. Use only numbers that appear in it.)"
            )
            text = ""
            continue
        usage["cause"] = ""
        break
    return text, usage
