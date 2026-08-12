"""
Daily episodic→semantic distillation sweep (PR-14).

Reads recent Message rows grouped by host user, uses a cheap LLM to
distill conversation turns into candidate long-term memory facts, and
stores them with low initial confidence.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from ai.engine.core.clock import utcnow
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import (
    MemoryLongTerm,
    Message,
    generate_uuid,
)

logger = logging.getLogger("pulse.cognition.distill.episodic_to_semantic")

# How many recent messages to consider per user per sweep
_MAX_MESSAGES_PER_USER = 40
# Lookback window
_LOOKBACK_HOURS = 24


async def run_distillation(db: AsyncSession, instance, llm_client=None):
    """Top-level entry point called by the cognition scheduler.

    Args:
        db: Active async DB session.
        instance: The Instance ORM row being processed.
        llm_client: Optional pre-created LLM client for testing.
    """
    sweeper = DistillationSweep(db, llm_client=llm_client)
    count = await sweeper.sweep(instance.id)
    logger.info(
        "Distillation sweep for %s: %d facts stored", instance.name, count
    )
    return count


class DistillationSweep:
    """Distills recent conversation messages into candidate long-term facts."""

    def __init__(self, db: AsyncSession, llm_client=None):
        self.db = db
        self._llm = llm_client

    async def _get_llm(self):
        """DEPRECATED: use _call_llm_for_facts which now routes through route_chat."""
        if self._llm is not None:
            return self._llm
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sweep(self, instance_id: str) -> int:
        """Run one distillation sweep for an instance.

        Returns the number of new facts stored.
        """
        # 1. Find distinct host_user_ids with recent message activity
        user_ids = await self._active_users(instance_id)
        if not user_ids:
            logger.debug("No active users for distillation in %s", instance_id)
            return 0

        total_stored = 0
        for host_user_id in user_ids:
            try:
                stored = await self._distill_user(instance_id, host_user_id)
                total_stored += stored
            except Exception as e:
                logger.warning(
                    "Distillation failed for user %s in %s: %s",
                    host_user_id, instance_id, e,
                )

        return total_stored

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _active_users(self, instance_id: str) -> list[str]:
        """Return distinct host_user_ids with message activity in the lookback window."""
        since = utcnow() - timedelta(hours=_LOOKBACK_HOURS)
        stmt = (
            select(Message.host_user_id)
            .where(
                Message.conversation_id.in_(
                    select(Message.conversation_id)
                    .where(
                        Message.host_user_id == Message.host_user_id,
                        Message.timestamp >= since,
                        Message.host_user_id.isnot(None),
                        Message.host_user_id != "",
                    )
                ),
                Message.host_user_id.isnot(None),
                Message.host_user_id != "",
            )
            .distinct()
        )
        # Simpler query: distinct host_user_ids with recent messages
        stmt = (
            select(Message.host_user_id)
            .where(
                Message.timestamp >= since,
                Message.host_user_id.isnot(None),
                Message.host_user_id != "",
                Message.role.in_(["user", "assistant"]),
            )
            .distinct()
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all() if row[0]]

    async def _distill_user(
        self, instance_id: str, host_user_id: str
    ) -> int:
        """Distill facts for a single host user from their recent messages."""
        messages = await self._recent_messages(host_user_id)
        if not messages:
            return 0

        prompt = self._build_distillation_prompt(messages)
        facts = await self._call_llm_for_facts(prompt, instance_id)

        return await self._store_facts(instance_id, host_user_id, facts)

    async def _recent_messages(self, host_user_id: str) -> list[dict]:
        """Fetch recent user/assistant messages for one host user, chronological."""
        since = utcnow() - timedelta(hours=_LOOKBACK_HOURS)
        stmt = (
            select(Message)
            .where(
                Message.host_user_id == host_user_id,
                Message.timestamp >= since,
                Message.role.in_(["user", "assistant"]),
            )
            .order_by(Message.timestamp.asc())
            .limit(_MAX_MESSAGES_PER_USER)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "role": row.role,
                "content": row.content[:500],
                "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            }
            for row in rows
        ]

    def _build_distillation_prompt(self, messages: list[dict]) -> str:
        """Assemble a prompt asking the LLM to extract learnable facts."""
        conversation = ""
        for i, msg in enumerate(messages, 1):
            role_label = "User" if msg["role"] == "user" else "AI"
            content = (msg.get("content") or "")[:300]
            conversation += f"{i}. {role_label}: {content}\n"

        return (
            "You are a knowledge distillation assistant. Review the conversation "
            "below and extract 1–3 concise, standalone facts that the AI system "
            "should remember for future interactions. Each fact must be a single "
            "declarative sentence. Prefer facts about:\n"
            "- User preferences or corrections\n"
            "- Data observations the system made\n"
            "- Workflows or procedures the user described\n\n"
            "Do NOT extract:\n"
            "- Greetings, small talk, or pleasantries\n"
            "- Transient facts (e.g. 'the user is typing')\n"
            "- Information already obvious from the system prompt\n\n"
            "Return ONLY a JSON array of strings, like:\n"
            '["The user prefers power forecasts in MW, not GW.", '
            '"The April 21 data was corrected to 8,879 MW."]\n\n'
            f"{conversation}"
        )

    async def _call_llm_for_facts(self, prompt: str, instance_id: str) -> list[str]:
        """Call the LLM and parse the JSON array response."""
        # If an explicit LLM client is wired (tests, backward compat), use it
        llm = await self._get_llm()
        if llm is not None:
            settings = get_settings()
            try:
                response = await llm.chat.completions.create(
                    model=settings.LLM_COGNITION_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=300,
                )
                raw = response.choices[0].message.content.strip()
                return self._parse_facts(raw)
            except Exception as e:
                logger.warning("LLM distillation call failed: %s", e)
                return []

        # Production path: route through route_chat for budget tracking
        from ai.engine.llm.router import route_chat

        try:
            result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"distill-{instance_id}",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            raw = (result.get("content") or "").strip()
            return self._parse_facts(raw)
        except Exception as e:
            logger.warning("LLM distillation call failed: %s", e)
            return []

    def _parse_facts(self, raw: str) -> list[str]:
        """Parse the LLM response into a list of fact strings."""
        # Handle markdown code fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
            if raw.endswith("```"):
                raw = raw[:-3]

        raw = raw.strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(f) for f in parsed if isinstance(f, str) and f.strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: treat each non-empty line as a fact
        return [line.strip("- ").strip() for line in raw.split("\n")
                if line.strip() and not line.startswith("[")]

    async def _store_facts(
        self, instance_id: str, host_user_id: str, facts: list[str]
    ) -> int:
        """Store distilled facts as MemoryLongTerm rows with low confidence."""
        stored = 0
        for fact_text in facts:
            if not fact_text or len(fact_text) < 10:
                continue

            # Set decay_at to 30 days from now (monthly decay sweep)
            decay_at = utcnow() + timedelta(days=30)

            fact = MemoryLongTerm(
                id=generate_uuid(),
                instance_id=instance_id,
                category="learned",
                content=fact_text,
                source="distillation",
                confidence=0.4,  # low initial confidence
                decay_at=decay_at,
                host_user_id=host_user_id,
                visibility="private",
            )
            self.db.add(fact)
            stored += 1

        if stored:
            await self.db.commit()
            logger.debug(
                "Stored %d distilled facts for user %s", stored, host_user_id
            )

        return stored

