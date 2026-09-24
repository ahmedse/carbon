"""One vocabulary for *where a turn is running* (ADR-0014 · ADR-0046).

Pulse used to say this three ways, and they disagreed:

1. a ``[Pulse mode: …]`` prose prefix glued onto the user's message, which a
   dozen modules stripped back off before any lexical check;
2. a ``process_mode`` transport field that could only express ask / plan, so
   Agent was not representable at all;
3. a ``surface`` string that every call site passed as the literal ``"chat"``.

(3) is what the write guardrail and the handoff copy read, so a Plan-dial turn
was told it was Chat and users saw "Open in Agent" while their dial already
read Plan.

Bare ``"plan"`` made it worse by meaning two opposite things: the Chat-side
Ask/Plan dial (advisory — must not write) and the Agent-side plan loop (may
stage with consent). Dotted names make that collision unrepresentable, and
``resolve`` is the only place legacy strings are interpreted.
"""
from __future__ import annotations

from enum import Enum

#: Replay-only. Old stored turns and recorded eval transcripts still carry the
#: retired prose prefix; live turns must send ``process_mode`` instead.
_LEGACY_PLAN_PREFIX = "[Pulse mode: Plan."
_LEGACY_AGENT_PREFIX = "[Pulse mode: Agent."


class Surface(str, Enum):
    """Where a tool call runs. The write permission follows from the name."""

    #: Chat dial on Ask — answers and advice.
    CHAT_ASK = "chat.ask"
    #: Chat dial on Plan — drafts a reviewable plan. Still Chat: no host writes.
    CHAT_PLAN = "chat.plan"
    #: Agent building a plan from a brief.
    AGENT_DISCOVERY = "agent.discovery"
    #: Agent plan loop / ReAct.
    AGENT_PLAN = "agent.plan"
    #: Agent executing an approved plan.
    AGENT_RUN = "agent.run"

    # Log lines and f-strings must show ``chat.plan``, not ``Surface.CHAT_PLAN``.
    __str__ = str.__str__

    @property
    def is_chat(self) -> bool:
        return self.value.startswith("chat.")

    @property
    def may_host_mutate(self) -> bool:
        """True where propose→confirm / RULE_21 consent can stage a host effect."""
        return not self.is_chat

    @property
    def dial_label_en(self) -> str:
        return _DIAL_LABELS[self][0]

    @property
    def dial_label_ar(self) -> str:
        return _DIAL_LABELS[self][1]

    def dial_label(self, locale: str = "en") -> str:
        return self.dial_label_ar if locale == "ar" else self.dial_label_en

    @classmethod
    def resolve(
        cls,
        surface: "str | Surface | None" = None,
        *,
        process_mode: str | None = None,
        user_message: str = "",
    ) -> "Surface":
        """Canonical surface for a turn. Fail-closed to the most restrictive.

        ``surface`` names the engine path (Chat pipeline vs Agent loop);
        ``process_mode`` is the user's dial within Chat. An explicit dotted
        value wins, then the Agent-side legacy names, then the dial.
        """
        if isinstance(surface, cls):
            return surface
        raw = (surface or "").strip().lower()
        if raw in _BY_VALUE:
            return _BY_VALUE[raw]
        # Agent-side legacy names are unambiguous about write permission, so
        # they outrank the Chat dial: an Agent plan loop is not Chat even when
        # the originating brief was typed with the dial on Plan.
        agent_side = _LEGACY_AGENT_SIDE.get(raw)
        if agent_side is not None:
            return agent_side
        dial = (process_mode or "").strip().lower()
        if dial in _BY_DIAL:
            return _BY_DIAL[dial]
        text = (user_message or "").lstrip()
        if text.startswith(_LEGACY_AGENT_PREFIX):
            return cls.AGENT_RUN
        if text.startswith(_LEGACY_PLAN_PREFIX):
            return cls.CHAT_PLAN
        return cls.CHAT_ASK


_BY_VALUE: dict[str, Surface] = {s.value: s for s in Surface}

#: Legacy ``surface=`` strings that named an Agent path.
_LEGACY_AGENT_SIDE: dict[str, Surface] = {
    "plan": Surface.AGENT_PLAN,
    "agent_plan": Surface.AGENT_PLAN,
    "agent_discovery": Surface.AGENT_DISCOVERY,
    "agent": Surface.AGENT_RUN,
    "run": Surface.AGENT_RUN,
}

#: Dial positions the composer can send. ``agent`` is now representable.
_BY_DIAL: dict[str, Surface] = {
    "ask": Surface.CHAT_ASK,
    "chat": Surface.CHAT_ASK,
    "plan": Surface.CHAT_PLAN,
    "agent": Surface.AGENT_RUN,
}

#: Values the transport accepts for ``process_mode`` / ``pulse_mode``. One
#: tuple so the serializer, the provider, and the store cannot drift.
PULSE_DIAL_MODES: tuple[str, ...] = ("ask", "plan", "agent")

#: What the user sees on the dial. Presentation only — never a routing input.
_DIAL_LABELS: dict[Surface, tuple[str, str]] = {
    Surface.CHAT_ASK: ("Chat", "الدردشة"),
    Surface.CHAT_PLAN: ("Plan", "الخطّة"),
    Surface.AGENT_DISCOVERY: ("Agent", "الوكيل"),
    Surface.AGENT_PLAN: ("Agent", "الوكيل"),
    Surface.AGENT_RUN: ("Agent", "الوكيل"),
}


class HandoffLoopError(AssertionError):
    """A handoff pointed the user at the surface they were already using.

    Raised instead of silently rendering "Open in Agent" to someone whose dial
    already reads Agent. Callers in production degrade to honest copy; tests
    let it raise so the plumbing regression is caught before a user sees it.
    """
