"""Sprint 10 (Phase 9-C) — learning bridge: consume judged AIMessage outcomes.

Translates each persisted ``AIMessage.outcome`` (Sprint 9) into durable engine
state:

  * ``KgFeedbackRecord`` (quality-scored signal, golden-pair capable) via
    ``record_feedback``.
  * ``MemoryLongTerm`` facts via ``LongTermMemory.store_fact`` for the
    learnable outcomes that carry durable knowledge (correction / accepted).

The batch entry point is ``learn_all_pending``; the single-message entry point
is ``learn_from_message``.  Idempotency is provided by ``AIMessage.learned_at``:
only rows with ``learned_at IS NULL`` are candidates, and ``learned_at`` is set
**only after** the engine write succeeds.

Import style is ``ai.*`` throughout (matching ``ai/store.py`` and the engine
internals) — never ``backend.ai.*``.
"""

import asyncio
import logging

from django.utils import timezone

from ai.models import AIMessage
from ai.store import DEFAULT_APP_IDENTIFIER, get_store
from ai.engine.knowledge_graph.feedback import record_feedback
from ai.engine.memory.long_term import LongTermMemory

logger = logging.getLogger("carbon.ai.learning")


# outcome -> engine feedback signal_type. "ignored" is intentionally absent:
# an explicit dismiss carries no learnable signal.
OUTCOME_SIGNAL_MAP = {
    "accepted": "explicit_positive",
    "rejected": "explicit_negative",
    "corrected": "correction",
}

LEARNABLE_OUTCOMES = list(OUTCOME_SIGNAL_MAP.keys())  # ["accepted", "rejected", "corrected"]


def learn_from_message(message) -> bool:
    """Consume one judged AIMessage into the engine. Returns True on success.

    No-op (returns False) when message.outcome is not learnable.
    Marks message.learned_at on success; leaves it null on failure (retry).
    """
    signal_type = OUTCOME_SIGNAL_MAP.get(message.outcome)
    if signal_type is None:
        return False
    asyncio.run(_learn_async(message, signal_type))
    message.learned_at = timezone.now()
    message.save(update_fields=["learned_at"])
    return True


async def _learn_async(message, signal_type) -> None:
    instance_id = DEFAULT_APP_IDENTIFIER
    conversation_id = str(message.conversation_id)
    message_id = str(message.id)
    user_id = str(message.conversation.user_id) if message.conversation.user_id else ""
    content = message.content or ""

    factory = get_store().get_session_factory(instance_id)
    session = factory()
    async with session:
        # 1) Record the feedback signal (KgFeedbackRecord + golden-pair logic).
        await record_feedback(
            db=session,
            instance_id=instance_id,
            conversation_id=conversation_id,
            message_id=message_id,
            signal_type=signal_type,
            user_id=user_id,
            original_utterance=content,
            resolved_utterance=content,
            generated_sql="",
            corrected_sql=None,       # chat/text answers carry no SQL; never fabricate
            user_comment=message.correction_text or None,
        )

        # 2) Persist long-term memory facts.
        memory = LongTermMemory(session)
        if signal_type == "correction" and message.correction_text:
            await memory.store_fact(
                instance_id=instance_id,
                category="correction",
                content=message.correction_text,
                source="feedback",
                confidence=1.0,
                host_user_id=str(message.conversation.user_id) if message.conversation.user_id else None,
                visibility="private",
            )
        elif signal_type == "explicit_positive" and content:
            await memory.store_fact(
                instance_id=instance_id,
                category="learned",
                content=content[:1000],
                source="feedback",
                confidence=1.0,
                host_user_id=str(message.conversation.user_id) if message.conversation.user_id else None,
                visibility="private",
            )


def learn_all_pending(limit=None) -> dict:
    """Process all unlearned judged messages. Returns a stats dict."""
    qs = (
        AIMessage.objects
        .filter(outcome__in=LEARNABLE_OUTCOMES, learned_at__isnull=True)
        .select_related("conversation")
        .order_by("created_at")
    )
    if limit:
        qs = qs[:limit]

    stats = {"processed": 0, "accepted": 0, "rejected": 0, "corrected": 0, "errors": 0}
    for message in qs:
        try:
            if learn_from_message(message):
                stats["processed"] += 1
                stats[message.outcome] += 1
        except Exception:
            logger.exception("learning failed for message %s", message.id)
            stats["errors"] += 1
    return stats
