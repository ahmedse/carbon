"""Typed plan-revision state for Agent → Discuss in Chat (ADR-0046 · ADR-0049 P9).

**Chat proposes; Agent applies.**

Refining an Agent plan in Chat used to be held together by prose: the turn
scanned the last twelve messages for a ``DISCUSSION ONLY`` marker to know it
was still discussing, matched the user's reply against a phrase allowlist to
know they wanted to apply, regex-searched the transcript for a plan id, and
then told the draft model to call ``edit_plan`` — which the ADR-0046 Chat
guard cancels on every Chat surface. Four fragile layers, one dead end.

This module replaces all four with one typed object on ``ConversationState``:

    open_question = {
        "kind": "plan_revision",
        "plan_id": "<uuid>",
        "title": "<plan brief>",
        "revision": "<assistant's proposed brief / steps>",
        "confirm": {"kind": "plan_revision", "plan_id": ..., "revision": ..., "title": ...},
    }

* The discuss turn (Plan dial, linked plan) **writes** it after the assistant
  proposes a revision.
* The next turn resolves the user's reply against it through the shared
  affirmation module (I2 ``open_question.confirm`` route) — no phrase list.
* A confirmed revision is a **0-LLM handoff** to Agent: an ``open_panel`` CTA
  that carries the revision to the Tasks panel, where the existing replan +
  diff review (RULE_21) applies it. Chat never calls ``edit_plan``.

No ``re.compile``. No new ``stage_exit``. The plan id on the seed turn is
parsed with :class:`uuid.UUID`, and after that it lives in state.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

import uuid
from typing import Any

KIND = "plan_revision"

_REVISION_MAX = 2000
_TITLE_MAX = 160

#: Plan statuses a Chat refine may target. Anything else is history.
_REVISABLE = T("turn/plan_revision.py::_REVISABLE")


# ── Reading state ────────────────────────────────────────────────────────


def pending_revision(state: Any) -> dict | None:
    """The typed ``plan_revision`` question, if one is open on ``state``."""
    question = getattr(state, "open_question", None) or {}
    if not isinstance(question, dict):
        return None
    if question.get("kind") != KIND or not question.get("plan_id"):
        return None
    return question


def _uuid_in(text: str) -> str:
    for raw in (text or "").replace(":", " ").replace('"', " ").split():
        token = raw.strip(".,;()[]{}")
        if len(token) != 36:
            continue
        try:
            return str(uuid.UUID(token))
        except ValueError:
            continue
    return ""


def linked_plan_ref(state: Any, user_message: str = "") -> dict | None:
    """Which plan is this Chat thread refining?

    Order: an already-open ``plan_revision`` question → ``state.active_plans``
    (written by ``PlansService`` on every lifecycle event) → a plan id the
    Discuss seed carried (``buildDiscussDraft.js`` writes it explicitly).
    """
    pending = pending_revision(state)
    if pending:
        return {"plan_id": pending["plan_id"], "title": str(pending.get("title") or "")}

    seed_id = _uuid_in(user_message)
    plans = [p for p in (getattr(state, "active_plans", None) or []) if isinstance(p, dict)]
    if seed_id:
        for p in plans:
            if str(p.get("plan_id") or "") == seed_id:
                return {"plan_id": seed_id, "title": str(p.get("title") or "")[:_TITLE_MAX]}
        return {"plan_id": seed_id, "title": ""}

    for p in plans:
        pid = str(p.get("plan_id") or "").strip()
        if pid and str(p.get("status") or "") in _REVISABLE:
            return {"plan_id": pid, "title": str(p.get("title") or "")[:_TITLE_MAX]}
    return None


def is_discuss_turn(user_message: str, state: Any, process_mode: str | None) -> bool:
    """Is Chat refining an Agent plan right now?

    True on the Plan dial when a ``plan_revision`` question is open, or when
    the FE seeded this turn as a Discuss handoff and a plan can be linked.
    No transcript scanning: the second turn onward reads state only.
    """
    if str(process_mode or "").strip().lower() != "plan":
        return False
    if pending_revision(state):
        return True
    from ai.engine.cognition.plan.planner import _is_agent_discuss_turn

    return _is_agent_discuss_turn(user_message) and linked_plan_ref(state, user_message) is not None


# ── Writing state ────────────────────────────────────────────────────────


def build_revision_question(plan_ref: dict, revision_text: str) -> dict:
    """Typed open question the discuss turn attaches to its response."""
    plan_id = str(plan_ref.get("plan_id") or "").strip()
    title = str(plan_ref.get("title") or "").strip()[:_TITLE_MAX]
    revision = " ".join((revision_text or "").split())[:_REVISION_MAX]
    confirm = {"kind": KIND, "plan_id": plan_id, "title": title, "revision": revision}
    return {"kind": KIND, "plan_id": plan_id, "title": title, "revision": revision, "confirm": confirm}


# ── Handoff (0-LLM) ──────────────────────────────────────────────────────


def build_revision_handoff(confirm: dict, user_message: str = ""):
    """``AgentResponse`` that hands the confirmed revision to Agent.

    Copy is product language (RULE_23). The CTA is ``open_panel`` → Tasks with
    ``plan_id`` and the revision text; the Tasks panel applies it through the
    existing replan + diff review, so consent stays in Agent.
    """
    from ai.engine.agent.chat_surface import detect_locale
    from ai.engine.agent.reasoning import AgentResponse

    plan_id = str(confirm.get("plan_id") or "").strip()
    title = str(confirm.get("title") or "").strip()
    revision = str(confirm.get("revision") or "").strip()
    locale = detect_locale(user_message)
    if locale == "ar":
        headline = "المراجعة جاهزة للتطبيق في الوكيل"
        body = (
            "الدردشة تقترح التغييرات فقط. افتح الخطة في الوكيل لمراجعة الفرق "
            "واعتماد المراجعة — لن يعمل أي شيء قبل الموافقة."
        )
        label, summary = "تطبيق في الوكيل", "مراجعة واعتماد التغيير في الوكيل"
    else:
        headline = "Revision ready to apply in Agent"
        body = (
            "Chat only proposes changes. Open the plan in Agent to review the "
            "diff and apply the revision — nothing runs until you approve."
        )
        label, summary = "Apply in Agent", "Review and apply the change in Agent"
    plan_line = f"\n\n_{title}_" if title else ""
    text = f"**{headline}**{plan_line}\n\n{body}"
    action = {
        "type": "open_panel",
        "panel": "tasks",
        "plan_id": plan_id,
        "label": label,
        "summary": summary,
        "process_hint": "plan",
        "revision": revision,
    }
    return AgentResponse(
        text=text,
        sources_cited=[],
        tools_used=[],
        confidence=1.0,
        total_tokens=0,
        llm_calls=0,
        model="",
        response_type="data_grounded",
        confidence_label="high",
        actions=[action],
        summary=summary,
    )
