"""Post-turn classifier: extracts correction/preference/context facts into LongTermMemory."""
import logging
from datetime import timedelta

from ai.engine.core.clock import utcnow
from ai.engine.llm.router import route_chat
from ai.engine.memory.long_term import LongTermMemory

logger = logging.getLogger("pulse.auto_memory")

_CLASSIFY_PROMPT = (
    "Classify the following user message into exactly one of these types:\n"
    "  preference — user states a persistent preference (e.g. 'I always want …')\n"
    "  feedback   — user corrects the assistant (e.g. 'no, that's wrong …', 'actually …')\n"
    "  context    — user declares ongoing work context (e.g. 'I\\'m working on …')\n"
    "  none       — routine query, greeting, or anything not worth remembering\n\n"
    "Rules:\n"
    "- Return ONLY the single word: preference, feedback, context, or none.\n"
    "- A bare question is always 'none'.\n"
    "- Only classify as preference/feedback/context if there is a clear, extractable fact.\n\n"
    "Message: {message}"
)

_TTL_DAYS: dict[str, int] = {"preference": 90, "feedback": 90, "context": 7}


class AutoMemoryExtractor:
    """Classifies user messages post-turn; persists corrections/preferences via LongTermMemory."""

    @classmethod
    async def try_extract(
        cls,
        user_message: str,
        instance_id: str,
        host_user_id: str | None,
        db_session,
    ) -> None:
        """Classify user_message and write to LongTermMemory if worth remembering.

        Fire-and-forget: never raises, never blocks the response.
        """
        try:
            prompt = _CLASSIFY_PROMPT.format(message=user_message[:500])
            result = await route_chat(
                task="eval",
                instance_id=instance_id,
                conversation_id="auto_memory",
                messages=[{"role": "user", "content": prompt}],
            )
            memory_type = (result.get("content") or "").strip().lower().split()[0] if result else "none"
            if memory_type not in _TTL_DAYS:
                return

            ttl = _TTL_DAYS[memory_type]
            valid_to = utcnow() + timedelta(days=ttl)

            mem = LongTermMemory(db_session)
            await mem.store_fact(
                instance_id=instance_id,
                category=memory_type,
                content=user_message[:500],
                source="auto_extract",
                confidence=0.85,
                host_user_id=host_user_id,
                visibility="private",
                valid_to=valid_to,
                memory_type=memory_type,
            )
            logger.info("AutoMemoryExtractor: stored %s fact for user=%s", memory_type, host_user_id)
        except Exception:
            logger.debug("AutoMemoryExtractor: extraction failed (non-fatal)", exc_info=True)
