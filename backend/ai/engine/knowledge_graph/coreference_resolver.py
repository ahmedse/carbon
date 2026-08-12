"""
Coreference resolver — Stage 7.

Rewrites a user's conversational utterance into a fully self-contained
question that the query planner can handle without needing to know prior
context.

Only calls the LLM when:
  • active_context is non-empty (there IS something to resolve)
  • turn_type is NOT NEW_TOPIC (new topics never have dangling references)
  • the utterance actually contains a pronoun / reference worth resolving

If those conditions are not met the original utterance is returned unchanged,
saving an unnecessary LLM round-trip.
"""
import logging
import re

from ai.engine.knowledge_graph.conversation_context import (
    ConversationSession,
    TurnType,
)

logger = logging.getLogger("pulse.knowledge_graph.coreference_resolver")

# Pronoun / shorthand patterns that indicate the utterance refers to prior context
_REFERENCE_PATTERNS = [
    r"\b(it|its|they|them|their|that|those|this|these)\b",
    r"\bthe\s+(same|above|previous|prior|last|current)\b",
    r"\bthe\s+(result|data|numbers|figures|rows|dataset)\b",
    r"\bthose\s+(numbers|results|rows|figures)\b",
    r"\bdo\s+(so|it)\b",
    r"\bthe\s+\w+\s+one(s)?\b",         # "the highest ones", "the red ones"
    r"\bbut\s+(without|excluding)\b",
    r"\balso\s+show\b",
    r"^(and|but|also|plus|with|without)\s",  # starts with a conjunction
    r"^(add|remove|include|exclude)\b",      # imperative with implicit object
    r"^(sort|order|filter|group)\b",         # imperative — implicit subject
    r"^(top|bottom)\s+\d+\b",               # "top 5" with no subject
    r"^(show|display|list)\s+(me\s+)?(just|only|the)?\b",
]


def _has_references(utterance: str) -> bool:
    for p in _REFERENCE_PATTERNS:
        if re.search(p, utterance, re.IGNORECASE):
            return True
    return False


class CoreferenceResolver:
    """
    Resolves pronouns and shorthand references in a user utterance by
    rewriting it as a standalone question.
    """

    def __init__(self, llm_client, model: str):
        self._llm = llm_client
        self._model = model

    async def resolve(
        self,
        utterance: str,
        session: ConversationSession,
        turn_type: TurnType,
    ) -> str:
        """
        Return a rewritten, self-contained version of *utterance*.
        Returns the original string if no resolution is needed.
        """
        # Skip for new topics — nothing to resolve
        if turn_type == TurnType.NEW_TOPIC:
            return utterance

        # Skip if context is empty
        if session.active_context.is_empty():
            return utterance

        # Skip if no reference patterns detected (cheap fast path)
        if not _has_references(utterance):
            logger.debug("coreference_resolver: no references detected — skipping LLM")
            return utterance

        try:
            return await self._llm_resolve(utterance, session)
        except Exception as exc:
            logger.warning("coreference_resolver LLM call failed: %s — returning original", exc)
            return utterance

    async def _llm_resolve(self, utterance: str, session: ConversationSession) -> str:
        context_summary = session.active_context.to_summary_text()

        # Include last 2 turns for even richer context
        recent = session.recent_turns(2)
        turn_lines: list[str] = []
        for t in recent:
            turn_lines.append(f"  User:   {t.user_utterance}")
            if t.result_summary:
                turn_lines.append(f"  Result: {t.result_summary}")
        turn_history = "\n".join(turn_lines) or "  (none)"

        system = (
            "You are a coreference resolver for a data analytics assistant.\n"
            "Your task: rewrite the USER'S NEW MESSAGE as a fully self-contained question "
            "that does not rely on any pronouns or implicit references from the conversation history.\n\n"
            "Rules:\n"
            "  • Preserve the user's intent exactly — do not add new constraints.\n"
            "  • Replace pronouns (it, they, that, those…) with the actual entity/metric they refer to.\n"
            "  • If the message is already self-contained, return it unchanged.\n"
            "  • Return ONLY the rewritten question — no explanation, no JSON, no quotes."
        )

        user_msg = (
            f"Active query context:\n{context_summary}\n\n"
            f"Recent conversation:\n{turn_history}\n\n"
            f"User's new message: \"{utterance}\"\n\n"
            "Rewritten, self-contained question:"
        )

        response = await self._llm.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=200,
        )

        resolved = response.choices[0].message.content.strip().strip('"').strip("'")

        if not resolved:
            return utterance

        logger.debug(
            "coreference_resolver: '%s' → '%s'", utterance[:60], resolved[:60]
        )
        return resolved
