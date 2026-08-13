"""
Playbook Assembler — assembles system prompts from versioned PlaybookBlocks.

Each instance's system prompt is built from individually-versioned blocks
(persona, domain rules, tool heuristics, lessons, etc.).  This replaces
the monolithic LLM-prompt-synthesis approach with a composable, surgically
editable playbook.

Design:
  - Blocks are loaded by instance_id, filtered to is_active=True.
  - Assembly order is _priority_ (descending) within each block_type group.
  - The block_type groups themselves have a canonical ordering (persona first,
    tone_voice last).
  - Runtime context (datetime, user, page, knowledge, memories) is NOT a
    PlaybookBlock — it is prepended separately by build_chat_prompt().
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from ai.engine.core.models import BLOCK_KINDS, PlaybookBlock, generate_uuid
from ai.store import first

logger = logging.getLogger("pulse.llm.playbook")

# ── Canonical block-type assembly order ──────────────────────────────────────
# Groups are emitted in this sequence. Within each group, blocks are sorted
# by priority descending.
BLOCK_TYPE_ORDER: tuple[str, ...] = (
    "persona",
    "scope_boundary",
    "domain_rule",
    "tool_heuristic",
    "lesson",
    "compliance",
    "tone_voice",
)


class PlaybookAssembler:
    """Assembles the system prompt from versioned PlaybookBlocks."""

    # ── Block loading ─────────────────────────────────────────────────────

    @staticmethod
    async def load_blocks(
        db,
        instance_id: str,
        block_filter: list[str] | None = None,
    ) -> list[PlaybookBlock]:
        """Load all active PlaybookBlocks for an instance, ordered for assembly.

        Args:
            db: Async database session.
            instance_id: The target instance.
            block_filter: Optional list of block_types to include.
                          If None, all block types are included.

        Returns:
            Ordered list of PlaybookBlock rows ready for assembly.
        """
        filters: dict = {"instance_id": instance_id, "is_active": True}
        if block_filter:
            filters["block_type__in"] = list(block_filter)

        blocks = await db.select(PlaybookBlock, filters)

        # Sort: canonical block-type order first, then priority descending
        type_rank = {t: i for i, t in enumerate(BLOCK_TYPE_ORDER)}
        blocks = sorted(
            blocks,
            key=lambda b: (type_rank.get(b.block_type, 99), -b.priority),
        )
        return blocks

    # ── Assembly ──────────────────────────────────────────────────────────

    async def assemble(
        self,
        db,
        instance_id: str,
        runtime_context: dict | None = None,
        block_filter: list[str] | None = None,
    ) -> str:
        """Assemble the full system prompt from PlaybookBlocks.

        Args:
            db: Async database session.
            instance_id: The target instance.
            runtime_context: Dict with keys like datetime, user_info,
                             page_context, relevant_knowledge, relevant_memories.
                             These are prepended BEFORE the assembled blocks.
            block_filter: Optional list of block_types to include.

        Returns:
            Complete system prompt string.
        """
        blocks = await self.load_blocks(db, instance_id, block_filter)

        if not blocks:
            logger.warning(
                f"No active PlaybookBlocks for instance={instance_id} — "
                f"returning fallback prompt"
            )
            return _fallback_prompt(runtime_context or {})

        # Build runtime header if context provided
        parts: list[str] = []
        if runtime_context:
            header = _build_runtime_header(runtime_context)
            if header:
                parts.append(header)

        # Build block sections
        current_type: str | None = None
        for block in blocks:
            if block.block_type != current_type:
                current_type = block.block_type
                parts.append(f"\n\n## {_block_type_heading(block.block_type)}")
            parts.append(f"\n{block.content}")

        result = "".join(parts).strip()
        logger.debug(
            f"Assembled playbook for {instance_id}: "
            f"{len(blocks)} blocks, {len(result)} chars"
        )
        return result

    # ── Single-block operations ───────────────────────────────────────────

    async def get_block(
        self,
        db,
        instance_id: str,
        block_type: str,
        title: str,
    ) -> PlaybookBlock | None:
        """Fetch a specific block by type + title (for surgical edits)."""
        rows = await db.select(PlaybookBlock, {
            "instance_id": instance_id,
            "block_type": block_type,
            "title": title,
            "is_active": True,
        })
        rows = sorted(rows, key=lambda b: b.version, reverse=True)
        return first(rows)

    async def upsert_block(
        self,
        db,
        instance_id: str,
        block_type: str,
        title: str,
        content: str,
        priority: int = 0,
        provenance: str | None = None,
        is_active: bool = True,
    ) -> PlaybookBlock:
        """Insert or update a block. Auto-increments version on content change.

        If a block with the same (instance_id, block_type, title) exists
        and is_active=True, update it — bumping the version if content changed.
        Otherwise, create a new block.
        """
        if block_type not in BLOCK_KINDS:
            raise ValueError(
                f"Unknown block_type={block_type!r}. Valid: {sorted(BLOCK_KINDS)}"
            )

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Look for existing active block
        rows = await db.select(PlaybookBlock, {
            "instance_id": instance_id,
            "block_type": block_type,
            "title": title,
            "is_active": True,
        })
        rows = sorted(rows, key=lambda b: b.version, reverse=True)
        existing = first(rows)

        if existing is not None:
            existing_hash = hashlib.sha256(existing.content.encode()).hexdigest()[:16]
            if existing_hash == content_hash:
                # Content unchanged — update metadata only
                existing.priority = priority
                if provenance:
                    existing.provenance = provenance
                await db.flush()
                logger.debug(
                    f"Block unchanged: {block_type}/{title} v{existing.version}"
                )
                return existing
            else:
                # Content changed — bump version
                existing.is_active = False
                await db.flush()
                logger.info(
                    f"Block superseded: {block_type}/{title} "
                    f"v{existing.version} → v{existing.version + 1}"
                )

        # Create new block
        new_block = PlaybookBlock(
            id=generate_uuid(),
            instance_id=instance_id,
            block_type=block_type,
            title=title,
            content=content,
            version=(existing.version + 1) if existing is not None else 1,
            is_active=is_active,
            priority=priority,
            provenance=provenance,
        )
        db.add(new_block)
        await db.flush()
        logger.info(
            f"Block created: {block_type}/{title} v{new_block.version}"
        )
        return new_block

    # ── Export ────────────────────────────────────────────────────────────

    async def export_playbook(
        self,
        db,
        instance_id: str,
    ) -> dict:
        """Export all blocks as a dict keyed by (block_type, title).

        Useful for archetype packing and cross-instance replication.
        """
        blocks = await self.load_blocks(db, instance_id)
        result: dict[str, dict] = {}
        for b in blocks:
            key = f"{b.block_type}:{b.title}"
            result[key] = {
                "block_type": b.block_type,
                "title": b.title,
                "content": b.content,
                "version": b.version,
                "priority": b.priority,
                "provenance": b.provenance,
            }
        return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _block_type_heading(block_type: str) -> str:
    """Human-readable heading for each block type group."""
    headings = {
        "persona": "Identity & Role",
        "scope_boundary": "Scope Boundaries",
        "domain_rule": "Domain Rules",
        "tool_heuristic": "Tool Heuristics",
        "lesson": "Learned Lessons",
        "compliance": "Compliance",
        "tone_voice": "Tone & Voice",
    }
    return headings.get(block_type, block_type.replace("_", " ").title())


def _build_runtime_header(ctx: dict) -> str:
    """Build the runtime header from context dict.

    This mirrors the header-building logic in build_chat_prompt()
    but operates on a dict rather than individual arguments.
    """
    lines = []
    if ctx.get("instance_name"):
        lines.append(f"# Pulse AI Copilot — {ctx['instance_name']}")
    if ctx.get("current_datetime"):
        lines.append(f"\n**Current time**: {ctx['current_datetime']}")
    if ctx.get("user_context"):
        lines.append(f"**Current user**: {ctx['user_context']}")
    if ctx.get("page_context"):
        lines.append(f"**Current page**: {ctx['page_context']}")

    if not lines:
        return ""

    header = "\n".join(lines)

    # Add knowledge and memories sections if present
    if ctx.get("relevant_knowledge"):
        header += f"\n\n## Current Context\n\n**Relevant knowledge from the knowledge graph:**\n{ctx['relevant_knowledge']}"
    if ctx.get("relevant_memories"):
        if "## Current Context" not in header:
            header += "\n\n## Current Context"
        header += f"\n\n**Relevant memories:**\n{ctx['relevant_memories']}"

    return header.strip()


def _fallback_prompt(ctx: dict) -> str:
    """Minimal fallback when no PlaybookBlocks exist."""
    instance_name = ctx.get("instance_name", "the platform")
    header = _build_runtime_header(ctx)
    body = (
        f"## Identity & Role\n\n"
        f"You are Pulse, an AI operations copilot for {instance_name}. "
        f"You help users understand their platform, answer questions about its data, "
        f"and perform operational tasks.\n\n"
        f"## Communication Rules\n\n"
        f"- Lead with the answer — no preamble.\n"
        f"- Use the platform's domain language.\n"
        f"- Never mention table names, SQL, or software internals.\n"
        f"- Never fabricate data — if a tool returns nothing, say so.\n\n"
        f"## Tools\n\n"
        f"- Use `call_host_api` for operational data.\n"
        f"- Use `query_host_db` for analytical queries.\n"
        f"- Use `search_knowledge` to understand concepts.\n\n"
        f"## Operational Rules\n\n"
        f"- Always be time-aware — flag stale data.\n"
        f"- Never explain AI/ML internals.\n"
        f"- Ask for confirmation before mutations.\n"
        f"- Learn from corrections using `learn_fact`."
    )
    parts = [header, body] if header else [body]
    return "\n\n".join(parts)


# ── Module-level singleton ───────────────────────────────────────────────────

playbook_assembler = PlaybookAssembler()
