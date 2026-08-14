"""
Episodic memory — event-based memories with causal chains + decay policy.
Records significant system events, links them into causal chains,
and decays relevance scores over time based on event type.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from ai.engine.core.clock import utcnow

from ai.store import first, scope_q

from ai.engine.core.config import get_settings
from ai.engine.core.models import MemoryEpisodic, generate_uuid

logger = logging.getLogger("pulse.memory.episodic")

# Decay rates per event type — fraction of relevance lost per day after the
# event's half-life window expires. Errors and anomalies decay slowly because
# they remain diagnostically useful; conversational milestones decay quickly.
_DECAY_RATES: dict[str, float] = {
    "error": 0.01,               # 1%/day — slow, diagnostic
    "anomaly": 0.02,             # 2%/day
    "performance_shift": 0.03,   # 3%/day
    "schema_change": 0.04,       # 4%/day
    "user_correction": 0.05,     # 5%/day — corrections age out unless reinforced
    "milestone": 0.08,           # 8%/day — milestones are ephemeral
}

# Half-life window in days before decay begins. Episodes younger than this
# retain their full relevance_score regardless of type.
_HALF_LIFE_DAYS: dict[str, int] = {
    "error": 30,
    "anomaly": 14,
    "performance_shift": 14,
    "schema_change": 7,
    "user_correction": 7,
    "milestone": 3,
}

# Thresholds
_ARCHIVE_THRESHOLD: float = 0.1   # relevance_score drops below → archive
_SEARCH_WINDOW_DAYS: int = 7       # how far back to look for causal predecessors


class EpisodicMemory:
    """Event-based memory store with causal chain generation and decay."""

    def __init__(
        self,
        db_session,
        chroma_client=None,
    ):
        self.db = db_session
        from ai.engine.knowledge.vector_store import get_vector_store
        self._vector = get_vector_store(db_session)

    def _collection_name(self, instance_id: str) -> str:
        """Get the collection name for episodic memory."""
        return f"episodes_{instance_id[:8]}"

    async def record_event(
        self,
        instance_id: str,
        event_type: str,
        summary: str,
        details: dict | None = None,
        occurred_at: datetime | None = None,
        host_user_id: str | None = None,
        visibility: str = "private",
    ) -> str:
        """
        Record a system event.
        Event types: 'anomaly', 'user_correction', 'schema_change',
                     'performance_shift', 'error', 'milestone'
        Returns the episode ID.
        """
        episode_id = generate_uuid()
        occurred = occurred_at or utcnow()
        effective_visibility = visibility if host_user_id else "shared"

        # Auto-link: find a recent prior event of a related type within the
        # search window and set it as the causal predecessor.
        caused_by_id = await self._find_predecessor(
            instance_id, event_type, summary, occurred, host_user_id
        )

        episode = MemoryEpisodic(
            id=episode_id,
            instance_id=instance_id,
            event_type=event_type,
            summary=summary,
            details=json.dumps(details) if details else None,
            caused_by_episode_id=caused_by_id,
            occurred_at=occurred,
            host_user_id=host_user_id,
            visibility=effective_visibility,
        )
        self.db.add(episode)
        await self.db.commit()

        # Embed for semantic retrieval
        doc_text = f"[{event_type}] {summary}"
        await self._vector.upsert(
            collection=self._collection_name(instance_id),
            ids=[episode_id],
            documents=[doc_text],
            metadatas=[
                {
                    "instance_id": instance_id,
                    "event_type": event_type,
                    "occurred_at": occurred.isoformat(),
                    "host_user_id": host_user_id or "",
                    "visibility": effective_visibility,
                }
            ],
            instance_id=instance_id,
        )

        logger.info(
            "Recorded episode [%s]%s: %s...",
            event_type,
            f" (caused_by={caused_by_id[:8]})" if caused_by_id else "",
            summary[:80],
        )
        return episode_id

    async def _find_predecessor(
        self,
        instance_id: str,
        event_type: str,
        summary: str,
        occurred_at: datetime,
        host_user_id: str | None,
    ) -> str | None:
        """Find the most likely causal predecessor for a new episode.

        Searches recent episodes of the same type or error/anomaly types
        (which are common root causes) within the search window. Uses
        semantic similarity on summaries to pick the best match.
        """
        window_start = occurred_at - timedelta(days=_SEARCH_WINDOW_DAYS)
        related_types = {event_type}
        if event_type not in ("error", "anomaly"):
            related_types.update(("error", "anomaly"))

        try:
            results = await self._vector.query(
                collection=self._collection_name(instance_id),
                query_texts=[summary],
                n_results=3,
                instance_id=instance_id,
            )
        except Exception:
            return None

        if not results["ids"] or not results["ids"][0]:
            return None

        for candidate_id in results["ids"][0]:
            rows = await self.db.select(
                MemoryEpisodic,
                scope_q(MemoryEpisodic, instance_id, host_user_id),
                ("id", candidate_id),
                ("archived", False),
            )
            ep = first(rows)
            if ep and ep.occurred_at >= window_start and ep.occurred_at < occurred_at:
                if ep.event_type in related_types:
                    return ep.id

        return None

    # ------------------------------------------------------------------
    # Causal chain navigation
    # ------------------------------------------------------------------

    async def get_causal_chain(
        self, episode_id: str, direction: str = "backward"
    ) -> list[dict]:
        """Walk the causal chain from an episode.

        Args:
            episode_id: Starting episode.
            direction: 'backward' (toward root cause), 'forward' (toward effects),
                       or 'full' (both directions merged).

        Returns:
            Ordered list of episode dicts from root to leaf.
        """
        backward_chain: list[dict] = []
        forward_chain: list[dict] = []

        if direction in ("backward", "full"):
            backward_chain = await self._walk_backward(episode_id)
        if direction in ("forward", "full"):
            forward_chain = await self._walk_forward(episode_id)

        if direction == "backward":
            return backward_chain
        if direction == "forward":
            return forward_chain

        # "full": merge — backward (already root-first), then forward excluding
        # the pivot (which is already at the end of backward).
        seen_ids = {e["id"] for e in backward_chain}
        for ep in forward_chain:
            if ep["id"] not in seen_ids:
                backward_chain.append(ep)
        return backward_chain

    async def _walk_backward(self, episode_id: str, max_depth: int = 20) -> list[dict]:
        """Walk caused_by links backward to the root cause."""
        chain: list[dict] = []
        seen: set[str] = set()
        current_id = episode_id

        for _ in range(max_depth):
            if current_id in seen:
                break
            seen.add(current_id)

            rows = await self.db.select(MemoryEpisodic, ("id", current_id))
            ep = first(rows)
            if not ep:
                break

            chain.insert(0, self._episode_to_dict(ep))
            if not ep.caused_by_episode_id:
                break
            current_id = ep.caused_by_episode_id

        return chain

    async def _walk_forward(self, episode_id: str, max_depth: int = 20) -> list[dict]:
        """Walk caused_by links forward to find all effects."""
        chain: list[dict] = []
        frontier = [episode_id]
        seen: set[str] = set()

        for _ in range(max_depth):
            if not frontier:
                break
            next_frontier: list[str] = []
            for cid in frontier:
                if cid in seen:
                    continue
                seen.add(cid)

                rows = await self.db.select(MemoryEpisodic, ("id", cid))
                ep = first(rows)
                if ep:
                    chain.append(self._episode_to_dict(ep))

                # Find children
                child_rows = await self.db.select(
                    MemoryEpisodic,
                    ("caused_by_episode_id", cid),
                    ("archived", False),
                )
                for child in child_rows:
                    if child.id not in seen:
                        next_frontier.append(child.id)

            frontier = next_frontier

        return chain

    async def find_root_cause(self, episode_id: str) -> dict | None:
        """Walk backward to the originating event and return it."""
        chain = await self._walk_backward(episode_id)
        return chain[0] if chain else None

    # ------------------------------------------------------------------
    # Decay policy
    # ------------------------------------------------------------------

    async def apply_decay(
        self, instance_id: str, host_user_id: str | None = None
    ) -> int:
        """Apply time-based decay to all non-archived episodes for the given scope.

        Each episode's relevance_score is reduced based on its age, event_type,
        and the configured decay rate. Episodes below _ARCHIVE_THRESHOLD are
        archived. Episodes still within their half-life window are untouched.

        Returns the number of episodes that were archived during this sweep.
        """
        now = utcnow()
        archived_count = 0

        episodes = await self.db.select(
            MemoryEpisodic,
            scope_q(MemoryEpisodic, instance_id, host_user_id),
            ("archived", False),
        )

        for ep in episodes:
            half_life = _HALF_LIFE_DAYS.get(ep.event_type, 7)
            age_days = (now - ep.occurred_at).days

            if age_days <= half_life:
                # Within half-life — no decay
                continue

            decay_rate = _DECAY_RATES.get(ep.event_type, 0.05)
            days_past_half_life = age_days - half_life
            new_score = max(0.0, ep.relevance_score - decay_rate * days_past_half_life)

            ep.relevance_score = new_score
            if new_score < _ARCHIVE_THRESHOLD:
                ep.archived = True
                archived_count += 1
                logger.info(
                    "Archived episode %s [%s] — relevance %.3f below threshold",
                    ep.id[:8], ep.event_type, new_score,
                )
            else:
                logger.debug(
                    "Decayed episode %s [%s] to relevance %.3f (age=%dd)",
                    ep.id[:8], ep.event_type, new_score, age_days,
                )

        await self.db.commit()
        return archived_count

    def _decay_for_event_type(self, event_type: str) -> float:
        """Get the daily decay rate for an event type."""
        return _DECAY_RATES.get(event_type, 0.05)

    # ------------------------------------------------------------------
    # Causal chain generation (LLM)
    # ------------------------------------------------------------------

    async def generate_causal_chain(
        self, episode_id: str, llm_client=None
    ) -> str | None:
        """
        Use LLM to explain why an event happened based on its causal predecessors.
        This now assembles the full backward chain to provide richer context.
        Updates the episode's causal_chain field.
        """
        rows = await self.db.select(MemoryEpisodic, ("id", episode_id))
        episode = first(rows)
        if not episode:
            return None

        if not llm_client:
            from ai.engine.llm.provider import get_llm_client
            llm_client = get_llm_client()

        settings = get_settings()

        # Gather predecessor context
        predecessor_chain = await self._walk_backward(episode_id)
        predecessor_text = ""
        if len(predecessor_chain) > 1:
            predecessor_text = "Preceding events in causal chain:\n"
            for i, pred in enumerate(predecessor_chain[:-1]):  # exclude self
                predecessor_text += (
                    f"  {i + 1}. [{pred['event_type']}] {pred['summary']}\n"
                )

        details_str = ""
        if episode.details:
            if isinstance(episode.details, str):
                try:
                    details_str = json.dumps(json.loads(episode.details), indent=2)
                except json.JSONDecodeError:
                    details_str = episode.details
            else:
                details_str = json.dumps(episode.details, indent=2, default=str)

        prompt = (
            f"Analyze this system event and explain the likely cause-effect chain.\n\n"
            f"Event type: {episode.event_type}\n"
            f"Summary: {episode.summary}\n"
            f"Details: {details_str}\n"
            f"Occurred at: {episode.occurred_at.isoformat()}\n\n"
            f"{predecessor_text}\n"
            f"Provide a brief causal chain: what likely caused this, "
            f"what the immediate effects are, and what might happen next."
        )

        try:
            from ai.engine.llm.router import route_chat
            result = await route_chat(
                task="cognition",
                instance_id=episode.instance_id,
                conversation_id=f"causal-chain-{episode_id}",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            causal_chain = result.get("content", "")

            episode.causal_chain = causal_chain
            await self.db.commit()

            logger.info(f"Generated causal chain for episode {episode_id}")
            return causal_chain
        except Exception as e:
            logger.warning(f"Failed to generate causal chain: {e}")
            return None

    # ------------------------------------------------------------------
    # Retrieval (decay-aware)
    # ------------------------------------------------------------------

    async def get_relevant_episodes(
        self,
        instance_id: str,
        query: str,
        top_k: int = 5,
        since: datetime | None = None,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """Semantic search over episodic memory, optionally filtered by time.
        Results are filtered by the tenancy triplet and boosted by relevance_score.
        Archived episodes are excluded.
        """
        try:
            results = await self._vector.query(
                collection=self._collection_name(instance_id),
                query_texts=[query],
                n_results=top_k * 2,  # over-fetch to allow filtering
                instance_id=instance_id,
            )
        except Exception:
            return []

        if not results["ids"] or not results["ids"][0]:
            return []

        episode_ids = results["ids"][0]
        episodes: list[dict] = []
        for eid in episode_ids:
            rows = await self.db.select(
                MemoryEpisodic,
                scope_q(MemoryEpisodic, instance_id, host_user_id),
                ("id", eid),
                ("archived", False),
            )
            ep = first(rows)
            if not ep:
                continue

            if since and ep.occurred_at < since:
                continue

            ep_dict = self._episode_to_dict(ep)
            ep_dict["_score"] = ep.relevance_score  # used for sorting
            episodes.append(ep_dict)

            # Touch last_accessed_at
            ep.last_accessed_at = utcnow()

        await self.db.commit()

        # Sort by relevance_score descending, then take top_k
        episodes.sort(key=lambda e: e.get("_score", 0.0), reverse=True)
        return episodes[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _episode_to_dict(self, ep) -> dict:
        """Convert a MemoryEpisodic ORM object to a plain dict."""
        details = ep.details
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                pass

        return {
            "id": ep.id,
            "event_type": ep.event_type,
            "summary": ep.summary,
            "details": details,
            "causal_chain": ep.causal_chain,
            "caused_by_episode_id": ep.caused_by_episode_id,
            "relevance_score": ep.relevance_score,
            "occurred_at": ep.occurred_at.isoformat(),
            "archived": ep.archived,
        }
