"""
Session store — Stage 7.

Async Django Store persistence for ConversationSession objects.
Each conversation gets one row in `ai_kg_conversationcontextrecord`
(ai.models.core.ConversationContextRecord), with the full session
serialised as a JSON blob.

Usage:
    store = ConversationSessionStore()
    session = await store.load(conversation_id, instance_id, db)
    # ... modify session ...
    await store.save(session, conversation_id, db)
"""
import json
import logging
from typing import Optional

from ai.models.core import ConversationContextRecord
from ai.store import first
from ai.engine.knowledge_graph.conversation_context import ConversationSession

logger = logging.getLogger("pulse.knowledge_graph.session_store")


class ConversationSessionStore:
    """
    Load and save ConversationSession objects from/to PostgreSQL (Django Store).
    Stateless — one instance can serve all conversations concurrently.
    """

    async def load(
        self,
        conversation_id: str,
        instance_id: str,
        db,
    ) -> Optional[ConversationSession]:
        """
        Load an existing ConversationSession for *conversation_id*.
        Returns None if no record exists (caller should create a fresh session).
        """
        try:
            record = first(
                await db.select(
                    ConversationContextRecord,
                    ("conversation_id", conversation_id),
                )
            )
            if record is None:
                return None

            data = json.loads(record.session_json)
            session = ConversationSession.from_dict(data)
            # Ensure instance_id is current (may have been reassigned)
            session.instance_id = instance_id
            logger.debug(
                "session_store.load: conversation_id=%s turns=%d",
                conversation_id, len(session.turns)
            )
            return session
        except Exception as exc:
            logger.warning("session_store.load error: %s", exc)
            return None

    async def save(
        self,
        session: ConversationSession,
        conversation_id: str,
        db,
    ) -> None:
        """
        Upsert the ConversationSession for *conversation_id*.
        The operation is best-effort — a failure is logged but not re-raised.
        """
        try:
            session_json = json.dumps(session.to_dict(), ensure_ascii=False)

            record = first(
                await db.select(
                    ConversationContextRecord,
                    ("conversation_id", conversation_id),
                )
            )

            if record is None:
                record = ConversationContextRecord(
                    conversation_id=conversation_id,
                    instance_id=session.instance_id,
                    session_json=session_json,
                )
                db.add(record)
            else:
                record.session_json = session_json
                record.instance_id = session.instance_id

            await db.commit()
            logger.debug(
                "session_store.save: conversation_id=%s turns=%d",
                conversation_id, len(session.turns)
            )
        except Exception as exc:
            logger.warning("session_store.save error: %s", exc)
            try:
                await db.rollback()
            except Exception:
                pass
