"""Dialogue handlers for empty responses and knowledge gaps.

FallbackHandler   — fires ONLY when DraftResult.text is empty (routing failure,
                    LLM outage, token truncation). Returns a navigable reply.
                    NOT used for knowledge gaps.

HonestUncertaintyHandler — fires when S4 Critic detects a knowledge gap
                    (LLM hedged or produced an uncertain short response on a
                    specific query). Returns an honest statement of ignorance,
                    never a fake clarification request.

Both are domain-agnostic: no domain terms in either class.
"""
from __future__ import annotations

import re

_AMBIGUOUS_MARKERS = re.compile(
    r"\b(which|either|or|between|versus|vs\.?|compare)\b",
    re.IGNORECASE,
)


class FallbackHandler:
    """Intercepts EMPTY draft text (routing/outage failure) — NOT knowledge gaps.

    If you find yourself tempted to add domain logic here, stop.
    Domain knowledge gaps belong in HonestUncertaintyHandler.
    """

    def handle(self, user_message: str, draft_text: str) -> str:
        """Return draft_text unchanged if non-empty; otherwise produce a minimal fallback."""
        if draft_text.strip():
            return draft_text
        return self._produce_fallback(user_message)

    def _produce_fallback(self, user_message: str) -> str:
        if self._is_ambiguous(user_message):
            return (
                "Could you clarify which of those options you'd like to focus on? "
                "Once you do, I can give you a precise answer."
            )
        # Genuine routing/outage failure — say so plainly.
        return (
            "I wasn't able to generate a response. This may be a temporary issue. "
            "Please try again or rephrase your question."
        )

    def _is_ambiguous(self, user_message: str) -> bool:
        return bool(_AMBIGUOUS_MARKERS.search(user_message))


class HonestUncertaintyHandler:
    """Produces an honest 'I don't know' response when the LLM lacks knowledge.

    The contract: never fabricate, never ask for clarification when the query
    was already specific. Surface what IS known (partial_knowledge) and admit
    what is not.
    """

    def handle(self, user_message: str, partial_knowledge: str) -> str:
        """Build an honest response from whatever partial knowledge the LLM produced.

        partial_knowledge is the LLM's own hedging text (e.g. "I'm not sure…").
        We surface it as-is if it contains useful content, then add an honest frame.
        """
        # Strip any fake clarification requests from the partial knowledge.
        cleaned = self._strip_fake_clarification(partial_knowledge)

        if cleaned:
            return (
                f"{cleaned}\n\n"
                "If you need a more detailed answer on this topic, I may not have "
                "complete knowledge here. You could try rephrasing or consult a "
                "specialist source for this specific area."
            )
        # Partial knowledge was empty or just hedging noise — pure honest ignorance.
        return (
            "I don't have reliable knowledge about this specific topic. "
            "I'd rather tell you that honestly than give you an uncertain answer. "
            "If you can share more context or a related aspect I might know better, "
            "I'll do my best to help."
        )

    def _strip_fake_clarification(self, text: str) -> str:
        """Remove generic 'please clarify' noise from a hedging LLM response."""
        _FAKE_CLARIFY_RE = re.compile(
            r"(I want to give you the most useful answer.*?\.|Could you clarify which specific.*?\.|"
            r"Once you do, I can help you precisely\.?)",
            re.IGNORECASE | re.DOTALL,
        )
        cleaned = _FAKE_CLARIFY_RE.sub("", text).strip()
        # If stripping left almost nothing, treat as empty.
        return cleaned if len(cleaned) > 40 else ""
