"""Conversation Compactor — LLM-based rolling summarization.

Replaces raw truncation with a semantic summary that preserves:
- Key decisions and commitments
- Factual claims (with citations)
- Pending questions/unresolved topics
- User preferences expressed

BE-02-3: Conversation compaction + per-run working notes.
"""
import logging
from typing import Optional

from ai.engine.llm.router import route_chat

logger = logging.getLogger("pulse.memory.compactor")

# ── Compaction thresholds ────────────────────────────────────────────────
NO_COMPACT_THRESHOLD = 20   # Below this: return raw messages, no compaction
MEDIUM_THRESHOLD = 50       # 20-50: compact oldest 60%, keep last 40%
# > 50: compact oldest 80%, keep last 20%

KEEP_RECENT_DEFAULT = 20    # Always keep at least this many raw recent messages


COMPACTION_PROMPT = """You are a conversation summarizer. Summarize this conversation, preserving:
1. Key decisions made and commitments
2. Factual claims (with sources if available)
3. Pending questions or unresolved topics
4. User preferences or constraints expressed
5. Context that would be needed to continue this conversation coherently

Existing summary: {existing_summary}

New messages to summarize:
{new_messages_block}

Return the updated summary as a single paragraph. Be concise but complete. Do NOT include greetings, apologies, or filler — only the substantive context needed to continue the conversation."""


class ConversationCompactor:
    """Compacts conversation history using an LLM summarization pass.

    Replaces raw truncation with a rolling summary. The summary is stored
    on the Conversation row and updated when enough new messages accumulate.
    """

    async def compact(
        self,
        instance_id: str,
        conversation_id: str,
        messages: list[dict],
        existing_summary: str = "",
        max_tokens: int = 2000,
    ) -> str:
        """Generate a rolling conversation summary.

        Strategy:
        - total < 20: return as-is (empty string = no compaction needed)
        - 20-50: compact oldest 60% into summary + keep last 40% raw
        - > 50: compact oldest 80% into summary + keep last 20% raw
        - If existing_summary provided: merge new messages into it
        """
        total = len(messages)
        if total < NO_COMPACT_THRESHOLD:
            return existing_summary or ""  # No compaction needed

        if total <= MEDIUM_THRESHOLD:
            # 20-50: compact oldest 60%, keep last 40% raw
            compact_count = int(total * 0.6)
            to_compact = messages[:compact_count]
        else:
            # > 50: compact oldest 80%, keep last 20% raw
            compact_count = int(total * 0.8)
            to_compact = messages[:compact_count]

        new_messages_block = _format_messages(to_compact)

        try:
            result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"compact-{conversation_id}",
                messages=[{
                    "role": "user",
                    "content": COMPACTION_PROMPT.format(
                        existing_summary=existing_summary or "(none)",
                        new_messages_block=new_messages_block,
                    ),
                }],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            summary = (result.get("content") or "").strip()
            if summary:
                logger.info(
                    "Compaction: %d messages → summary len=%d  conv=%s",
                    len(to_compact), len(summary), conversation_id[:8],
                )
            return summary
        except Exception as exc:
            logger.warning("Compaction LLM call failed: %s — falling back to no compaction", exc)
            return existing_summary or ""

    def apply_compaction(
        self,
        summary: str,
        recent_messages: list[dict],
        max_recent: int = KEEP_RECENT_DEFAULT,
    ) -> list[dict]:
        """Build the final message list for the LLM.

        If summary is non-empty, prepends a system message with the summary,
        followed by the recent messages.
        If summary is empty, returns recent messages as-is.
        """
        if not summary:
            return recent_messages[-max_recent:] if len(recent_messages) > max_recent else recent_messages

        system_content = (
            "Previous conversation summary (for context):\\n"
            f"{summary}"
        )

        messages: list[dict] = [{"role": "system", "content": system_content}]

        # Keep the most recent raw messages
        keep = recent_messages[-max_recent:] if len(recent_messages) > max_recent else recent_messages
        messages.extend(keep)

        return messages


def _format_messages(messages: list[dict]) -> str:
    """Format a list of {role, content} dicts into a readable block for the LLM."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Truncate very long messages to avoid overwhelming the summary prompt
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        lines.append(f"[{role}]: {content}")
    return "\n\n".join(lines)
