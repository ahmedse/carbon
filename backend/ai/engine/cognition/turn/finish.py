"""v21 finishes every op the understand call emits (ADR-0056).

An ``answer`` from the conversation is the Decision's own text when it passes
the writer's checks (Amendment 1). Any other ``answer`` and ``set_slot`` are
written by one writer call. ``navigate`` opens
the route the Decision named. Nothing here reads the user's wording to decide
what the turn is: the Decision already decided.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.engine.cognition.turn.decision import Command, Decision

logger = logging.getLogger("pulse.cognition.turn.finish")

ANSWER_TASK_PROMPT = (
    "TASK — Write the reply to the user's last message.\n"
    "Understanding already decided this turn is answered in words, with no "
    "live read. What it understood: {reason}\n"
    "Use the identity, state, history, knowledge and memory blocks above. "
    "The last view is context. Do not reprint it as the reply. "
    "Do not say you looked anything up, saved it, or changed it. "
    "Do not invent figures, names or dates. {language} Quote names, titles "
    "and other values from the record exactly as written."
)


def _record_spellings(state: Any) -> list[str]:
    """Multi-word record values as stored on the last read. No host words here."""
    found: list[str] = []
    for row in getattr(state, "last_results", None) or []:
        if not isinstance(row, dict):
            continue
        for part in str(row.get("digest") or "").split(","):
            if "=" not in part:
                continue
            value = part.split("=", 1)[1].strip()
            if " " not in value:
                continue
            if any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in value):
                found.append(value)
    return found


def _quotes_a_shown_record(text: str, state: Any) -> bool:
    """True when an Arabic reply kept a stored spelling, or quoted a figure.

    A digest value with a space and Latin letters is a name as stored. The
    reply may contain one of those, or a figure from the same digest. A reply
    that contains neither replaced the record with other words.
    """
    spellings = _record_spellings(state)
    if not spellings:
        return True
    if any(value in text for value in spellings):
        return True
    figures: list[str] = []
    for row in getattr(state, "last_results", None) or []:
        if not isinstance(row, dict):
            continue
        for part in str(row.get("digest") or "").split(","):
            if "=" not in part:
                continue
            value = part.split("=", 1)[1].strip()
            if value.isdigit():
                figures.append(value)
    return any(fig in text for fig in figures)


def _language_line(code: str) -> str:
    """The reply language Understanding decided, said to the writer."""
    if code == "ar":
        return "Reply in Arabic, with Arabic words even when the answer is one figure."
    if code == "en":
        return "Reply in English."
    return "Reply in the user's language."


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


def grounded_reply(
    cmd: Command,
    decision: Decision,
    *,
    user_message: str,
    conversation_history: list[dict] | None,
    state: Any,
) -> str:
    """The reply already on an answer command, when it can be shown as-is.

    Only an answer whose source is the conversation (ADR-0056 Amendment 1).
    Empty when the command has no reply, the language does not match, or a
    figure is not in what the understand call was shown. The caller then
    writes one with retrieval and memory.
    """
    from ai.engine.cognition.turn.decision import CONVERSATION_SOURCE
    from ai.engine.cognition.turn.grounding import ungrounded_numbers
    from ai.engine.text.word_match import has_arabic_script

    if cmd.op != "answer" or cmd.source != CONVERSATION_SOURCE:
        return ""
    text = (cmd.text or "").strip()
    if not text:
        return ""
    if decision.language == "ar" and not has_arabic_script(text):
        return ""
    if decision.language == "ar" and not _quotes_a_shown_record(text, state):
        return ""
    shown = _shown_to_understand(
        decision, user_message=user_message,
        conversation_history=conversation_history, state=state,
    )
    if ungrounded_numbers(text, shown):
        from ai.engine.cognition.turn.grounding import strip_ungrounded_numbers

        kept = strip_ungrounded_numbers(text, shown).strip()
        # A calculated date drops out. A reply whose only figure was invented
        # does not stay — there is nothing left to stand on.
        if not any(ch.isdigit() for ch in kept) or not any(ch.isalpha() for ch in kept):
            return ""
        text = kept
    return text


def _shown_to_understand(
    decision: Decision,
    *,
    user_message: str,
    conversation_history: list[dict] | None,
    state: Any,
) -> list[str]:
    """The texts the understand call read: its own messages when kept."""
    sent = (getattr(decision, "exchange", None) or {}).get("messages") or []
    shown = [str(m.get("content") or "") for m in sent if isinstance(m, dict)]
    if shown:
        return shown
    history = list(conversation_history or [])[-8:]
    return [
        user_message or "",
        *(str(m.get("content") or "") for m in history if isinstance(m, dict)),
        *(
            str(row.get("digest") or "")
            for row in (getattr(state, "last_results", None) or [])
            if isinstance(row, dict)
        ),
    ]


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
    page_context: str = "",
) -> tuple[str, dict]:
    """One writer call, retried once when empty or a number is not in the conversation.

    A second ungrounded or empty reply returns no text. The caller shows a
    typed error. The prose is never cut.
    """
    from ai.engine.cognition.context_pack import build_context_pack
    from ai.engine.cognition.turn.grounding import ungrounded_numbers
    from ai.engine.llm.call_meter import stage
    from ai.engine.llm.router import route_chat
    from ai.engine.text.word_match import has_arabic_script

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
        task_body=ANSWER_TASK_PROMPT.format(
            reason=(decision.reason or "").strip() or "-",
            language=_language_line(decision.language),
        ),
        include_state=True,
        include_history=False,
        include_knowledge=True,
        include_memory=True,
    )
    system = pack.system_prompt()
    page = str(page_context or "").strip()
    if page:
        system = f"{system}\n\n**Current page**:\n{page}"
    allowed = [
        user_message or "",
        system,
        *(str(m.get("content") or "") for m in history if isinstance(m, dict)),
        *(
            str(row.get("digest") or "")
            for row in (getattr(state, "last_results", None) or [])
            if isinstance(row, dict)
        ),
    ]
    messages = [{"role": "system", "content": system}, *history]
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
            usage["ungrounded"] = bad[:8]
            usage["rejected_head"] = text[:600]
            if _attempt == 0:
                note = (
                    "(These numbers are not in the conversation: "
                    f"{', '.join(bad[:8])}. Use only numbers that appear in it.)"
                )
                text = ""
                continue
            from ai.engine.cognition.turn.grounding import strip_ungrounded_numbers

            kept = strip_ungrounded_numbers(text, allowed).strip()
            if any(ch.isdigit() for ch in kept) and any(ch.isalpha() for ch in kept):
                text = kept
                usage["cause"] = ""
                break
            text = ""
            break
        if decision.language == "ar" and not _quotes_a_shown_record(text, state):
            if _attempt == 0:
                usage["cause"] = "record_spelling"
                kept = "; ".join(_record_spellings(state)[:6])
                note = (
                    "(Answer in Arabic. Copy these record values unchanged, "
                    f"do not translate them: {kept}.)"
                )
                text = ""
                continue
            text = ""
            break
        if _attempt == 0 and decision.language == "ar" and not has_arabic_script(text):
            logger.info("[answer] retry cause=wrong_language head=%r", text[:200])
            usage["cause"] = "wrong_language"
            note = (
                f"(Your reply «{text[:80]}» has no Arabic words, but this turn is "
                "answered in Arabic. Rewrite it as a short Arabic sentence; keep "
                "figures and quoted values as they are.)"
            )
            text = ""
            continue
        usage["cause"] = ""
        break
    return text, usage
