"""
P4.4b — KG node seeding from trajectory user messages.

Scans recent unprocessed trajectories for novel entities (noun phrases
extracted from user messages) and seeds low-confidence KgNode rows
with source='observation'.

Sleep-time job — no LLM calls, no hot-path impact.
"""
import json
import logging
import re

from ai.store import first

from ai.engine.core.models import KgNode, Trajectory, generate_uuid

logger = logging.getLogger("pulse.cognition.kg_seeding")

# ── Constants ────────────────────────────────────────────────────────────────

_MAX_TRAJECTORIES = 100  # Max trajectories to scan per sweep
_MIN_WORD_LENGTH = 2     # Minimum characters for an entity candidate
_DEFAULT_CONFIDENCE = 0.3  # Low confidence — validation comes later

# Words to skip during noun-phrase extraction
_STOPWORDS: frozenset[str] = frozenset({
    "I", "Me", "We", "You", "He", "She", "It", "They",
    "The", "A", "An", "Is", "Are", "Was", "Were",
    "Can", "Will", "Would", "Could", "Should",
    "This", "That", "These", "Those",
    "What", "How", "Why", "When", "Where", "Who",
    "My", "Your", "His", "Her", "Our", "Their",
    "And", "Or", "But", "If", "So", "For", "To", "In", "On", "At", "From", "With",
    "Of", "By", "As", "All", "Not", "No",
})


# ═══════════════════════════════════════════════════════════════════════════════
# Noun-phrase extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_entities(text: str) -> list[str]:
    """Extract potential entity names from user message text.

    Entities are words that:
    - Start with an uppercase letter (TitleCase) or are all-uppercase
    - Have >= _MIN_WORD_LENGTH characters
    - Are not in the stopword set

    Returns deduplicated list, preserving first-seen order.
    """
    # Strip trailing punctuation from each token
    raw_tokens = text.split()
    cleaned: list[str] = []
    for tok in raw_tokens:
        # Remove leading punctuation, and trailing punctuation/possessives
        stripped = re.sub(r"^[^\w]+|[^\w]+$|'s$", '', tok)
        if stripped:
            cleaned.append(stripped)

    seen: set[str] = set()
    entities: list[str] = []

    for token in cleaned:
        if len(token) < _MIN_WORD_LENGTH:
            continue
        if token in _STOPWORDS:
            continue
        # Must be TitleCase or UPPERCASE (first char uppercase)
        if not token[0].isupper():
            continue
        if token.lower() in seen:
            continue
        seen.add(token.lower())
        entities.append(token)

    return entities


# ═══════════════════════════════════════════════════════════════════════════════
# Node seeding
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_nodes_from_trajectories(
    db,
    instance_id: str,
) -> int:
    """Scan recent unprocessed trajectories for novel entities and seed KG nodes.

    For each noun phrase extracted from trajectory user messages, creates
    a low-confidence ``KgNode`` (source='observation', confidence=0.3) if
    one doesn't already exist for the instance.

    Args:
        db: Open async session.
        instance_id: The instance to scan trajectories for.

    Returns:
        Number of new KgNode rows created.
    """
    # 1. Fetch recent unprocessed trajectories
    trajectories = await db.select(
        Trajectory,
        ("instance_id", instance_id),
        ("consolidation_round", 0),
    )
    trajectories.sort(key=lambda t: t.created_at, reverse=True)
    trajectories = trajectories[:_MAX_TRAJECTORIES]

    if not trajectories:
        logger.debug("seed_nodes_from_trajectories: no trajectories for %s", instance_id)
        return 0

    # 2. Extract all novel entities
    all_entities: list[str] = []
    for traj in trajectories:
        if traj.user_message:
            entities = _extract_entities(traj.user_message)
            all_entities.extend(entities)

    if not all_entities:
        logger.debug("seed_nodes_from_trajectories: no entities extracted for %s", instance_id)
        return 0

    # 3. Deduplicate and check against existing KG nodes
    created = 0
    seen_in_batch: set[str] = set()

    for entity in all_entities:
        canonical = entity.lower()
        if canonical in seen_in_batch:
            continue
        seen_in_batch.add(canonical)

        # Check if already exists
        existing = await db.select(
            KgNode,
            ("instance_id", instance_id),
            ("name", entity),
        )
        if first(existing) is not None:
            logger.debug("seed_nodes_from_trajectories: skipping existing '%s'", entity)
            continue

        # Create low-confidence observation node
        node = KgNode(
            instance_id=instance_id,
            type="entity",
            name=entity,
            canonical_ref=canonical,
            source="observation",
            confidence=_DEFAULT_CONFIDENCE,
            properties="{}",
            embedding=None,
        )
        db.add(node)
        created += 1
        logger.debug("seed_nodes_from_trajectories: created KgNode '%s'", entity)

    if created:
        await db.commit()
        logger.info(
            "seed_nodes_from_trajectories: %d new nodes for instance %s "
            "from %d trajectories",
            created, instance_id, len(trajectories),
        )

    return created
