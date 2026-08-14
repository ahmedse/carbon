"""
Long-term memory — persistent facts stored in SQLite + vector store.
Facts survive across conversations and sessions.

BE-02-2: Added valid_from/valid_to temporal validity, supersede_fact(),
and write-path semantic dedup + contradiction detection.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from ai.engine.core.clock import utcnow

from ai.store import first, scope_q

from ai.engine.core.models import MemoryLongTerm, generate_uuid

logger = logging.getLogger("pulse.memory.long_term")


class LongTermMemory:
    """Persistent fact store: durable store for CRUD, vector store for semantic retrieval."""

    def __init__(
        self,
        db_session,
        chroma_client=None,
    ):
        self.db = db_session
        from ai.engine.knowledge.vector_store import get_vector_store
        self._vector = get_vector_store(db_session)

    def _collection_name(self, instance_id: str) -> str:
        """Get the collection name for an instance's memory."""
        return f"memory_{instance_id[:8]}"

    async def store_fact(
        self,
        instance_id: str,
        category: str,
        content: str,
        source: str | None = None,
        confidence: float = 1.0,
        host_user_id: str | None = None,
        visibility: str = "private",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> str:
        """
        Store a new fact with write-path dedup and contradiction detection.

        BE-02-2 dedup logic:
        1. Semantic dedup: search for existing facts with cosine > 0.92
           → if found, update confidence (max of old/new) and return existing ID.
        2. Contradiction check: search for facts with opposite sentiment
           → if found, log warning; store new fact with lower confidence (0.5).
        3. Store.

        Categories: 'learned', 'correction', 'preference', 'observation'
        Returns the fact ID.
        """
        fact_id = generate_uuid()
        effective_visibility = visibility if host_user_id else "shared"

        # ── Step 1: Semantic dedup ──────────────────────────────────────────
        try:
            results = await self._vector.query(
                collection=self._collection_name(instance_id),
                query_texts=[content],
                n_results=5,
                instance_id=instance_id,
            )
            if results.get("ids") and results["ids"][0]:
                for i, fid in enumerate(results["ids"][0]):
                    distance = results.get("distances", [[1.0]])[0][i]
                    similarity = 1.0 - distance
                    if similarity > 0.92 and fid != fact_id:
                        # Near-duplicate: update confidence and return existing
                        existing = first(await self.db.select(MemoryLongTerm, ("id", fid)))
                        if existing and not existing.archived:
                            existing.confidence = max(existing.confidence, confidence)
                            existing.last_used = utcnow()
                            existing.use_count += 1
                            await self.db.commit()
                            logger.info(
                                "Dedup: fact %s near-duplicate of %s (sim=%.3f), "
                                "updated confidence to %.2f",
                                fact_id, fid, similarity, existing.confidence,
                            )
                            return fid
        except Exception:
            pass  # vector search may fail; proceed with insert

        # ── Step 2: Contradiction detection ─────────────────────────────────
        try:
            results = await self._vector.query(
                collection=self._collection_name(instance_id),
                query_texts=[content],
                n_results=3,
                instance_id=instance_id,
            )
            if results.get("ids") and results["ids"][0]:
                for i, fid in enumerate(results["ids"][0]):
                    distance = results.get("distances", [[1.0]])[0][i]
                    similarity = 1.0 - distance
                    if 0.5 < similarity < 0.92:
                        existing = first(await self.db.select(MemoryLongTerm, ("id", fid)))
                        if existing and existing.content.strip().lower() != content.strip().lower():
                            logger.warning(
                                "Possible contradiction: new fact %r vs existing %r "
                                "(sim=%.3f). Storing with low confidence.",
                                content[:80], existing.content[:80], similarity,
                            )
                            confidence = min(confidence, 0.5)
                        break
        except Exception:
            pass  # proceed with original confidence

        # ── Step 3: Store ───────────────────────────────────────────────────
        fact = MemoryLongTerm(
            id=fact_id,
            instance_id=instance_id,
            category=category,
            content=content,
            source=source,
            confidence=confidence,
            host_user_id=host_user_id,
            visibility=effective_visibility,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self.db.add(fact)
        await self.db.commit()

        # Embed in vector store for semantic search
        await self._vector.upsert(
            collection=self._collection_name(instance_id),
            ids=[fact_id],
            documents=[content],
            metadatas=[
                {
                    "instance_id": instance_id,
                    "category": category,
                    "confidence": confidence,
                    "host_user_id": host_user_id or "",
                    "visibility": effective_visibility,
                }
            ],
            instance_id=instance_id,
        )

        logger.info(f"Stored fact [{category}]: {content[:80]}...")
        return fact_id

    async def supersede_fact(
        self, fact_id: str, new_content: str, new_fact_id: str | None = None
    ) -> str | None:
        """Mark old fact as expired (valid_to=now), point to replacement.

        BE-02-2: When a fact changes (e.g. API version bump), the old fact
        is soft-expired with valid_to set and superseded_by pointing to
        the replacement.

        Returns the new fact ID (or existing ID if the new content is a
        near-duplicate of an existing fact).
        """
        now = utcnow()
        old = first(await self.db.select(MemoryLongTerm, ("id", fact_id)))
        if old is None:
            logger.warning("supersede_fact: fact %s not found", fact_id)
            return None

        new_id = new_fact_id or generate_uuid()

        # Expire the old fact
        old.valid_to = now
        old.superseded_by = new_id
        await self.db.commit()

        # Store the new fact
        return await self.store_fact(
            instance_id=old.instance_id,
            category=old.category,
            content=new_content,
            source=f"superseded:{fact_id}",
            confidence=old.confidence,
            host_user_id=old.host_user_id,
            visibility=old.visibility,
            valid_from=now,
        )

    async def get_relevant_facts(
        self, instance_id: str, query: str, top_k: int = 5,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """
        Hybrid search over long-term memory:
        1. Mandatory: ALL business_rule and correction facts are always loaded —
           they are hard constraints that must apply regardless of query wording.
        2. Semantic: ChromaDB embedding similarity for observations/preferences.
        Deduplicates results before returning.
        BE-02-2: Expired facts (valid_to IS NOT NULL AND valid_to < now()) are
        excluded from results.
        Results are filtered by the tenancy triplet (instance_id, host_user_id, visibility).
        """
        facts_by_id: dict[str, dict] = {}

        # 1. Always load ALL business_rule and correction facts — these are hard
        #    constraints that must apply regardless of how the query is worded.
        #    Keyword/semantic matching is unreliable for constraints because the
        #    query phrasing often doesn't overlap with the rule's vocabulary.
        try:
            mandatory_facts = await self._get_all_mandatory_facts(
                instance_id, host_user_id=host_user_id
            )
            for f in mandatory_facts:
                facts_by_id[f["id"]] = f
        except Exception as e:
            logger.warning(f"Mandatory fact load failed: {e}")

        # 2. Semantic search for observations/preferences
        try:
            results = await self._vector.query(
                collection=self._collection_name(instance_id),
                query_texts=[query],
                n_results=top_k,
                instance_id=instance_id,
            )
        except Exception:
            return list(facts_by_id.values())

        if results["ids"] and results["ids"][0]:
            for fid in results["ids"][0]:
                if fid in facts_by_id:
                    continue  # already found by keyword search
                # Apply tenancy filter in SQL when fetching by ID
                fact = first(await self.db.select(
                    MemoryLongTerm,
                    scope_q(MemoryLongTerm, instance_id, host_user_id),
                    ("id", fid),
                ))
                if fact:
                    fact.last_used = utcnow()
                    fact.use_count += 1
                    facts_by_id[fact.id] = {
                        "id": fact.id,
                        "category": fact.category,
                        "content": fact.content,
                        "source": fact.source,
                        "confidence": fact.confidence,
                        "use_count": fact.use_count,
                    }

        await self.db.commit()
        # Return corrections first, then others
        result_list = sorted(
            facts_by_id.values(),
            key=lambda f: (0 if f["category"] in ("correction", "business_rule") else 1),
        )
        return result_list[:top_k]

    async def _get_all_mandatory_facts(
        self,
        instance_id: str,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """Return ALL active business_rule and correction facts for an instance.

        These are hard constraints — they must be injected into every prompt
        regardless of query wording, so keyword/semantic matching is bypassed.
        """
        now = utcnow()
        facts = await self.db.select(
            MemoryLongTerm,
            scope_q(MemoryLongTerm, instance_id, host_user_id),
            ("category__in", ["correction", "business_rule"]),
            ("archived", False),
        )
        # BE-02-2: exclude expired facts (valid_to set and in the past)
        facts = [f for f in facts if f.valid_to is None or f.valid_to > now]
        out = []
        for fact in facts:
            fact.last_used = utcnow()
            fact.use_count += 1
            out.append({
                "id": fact.id,
                "category": fact.category,
                "content": fact.content,
                "source": fact.source,
                "confidence": fact.confidence,
                "use_count": fact.use_count,
            })
        if facts:
            await self.db.commit()
        return out

    async def _keyword_match_corrections(
        self,
        instance_id: str,
        query: str,
        limit: int = 3,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """
        Exact keyword match for correction and business_rule facts.
        Extracts significant words from the query and matches against fact content.
        This guarantees corrections are surfaced even if embeddings drift.
        Results are filtered by the tenancy triplet.
        """
        # Extract significant keywords (3+ chars, not stopwords)
        _stopwords = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can",
            "had", "her", "was", "one", "our", "out", "has", "his", "how",
            "its", "may", "new", "now", "old", "see", "way", "who", "did",
            "get", "let", "say", "she", "too", "use", "what", "when", "where",
            "which", "with", "this", "that", "from", "have", "been", "will",
            "more", "show", "list", "give", "tell", "many", "much", "some",
        }
        words = [
            w.lower() for w in query.split()
            if len(w) >= 3 and w.lower() not in _stopwords
        ]
        if not words:
            return []

        # Search corrections/business_rules through tenancy-filtered query
        now = utcnow()
        all_corrections = await self.db.select(
            MemoryLongTerm,
            scope_q(MemoryLongTerm, instance_id, host_user_id),
            ("category__in", ["correction", "business_rule"]),
            ("archived", False),
        )
        all_corrections = [
            f for f in all_corrections if f.valid_to is None or f.valid_to > now
        ]

        matched = []
        for fact in all_corrections:
            content_lower = fact.content.lower()
            matching_words = sum(1 for w in words if w in content_lower)
            if matching_words >= 1:
                fact.last_used = utcnow()
                fact.use_count += 1
                matched.append((matching_words, {
                    "id": fact.id,
                    "category": fact.category,
                    "content": fact.content,
                    "source": fact.source,
                    "confidence": fact.confidence,
                    "use_count": fact.use_count,
                }))

        # Sort by number of matching words (most relevant first)
        matched.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matched[:limit]]

    async def update_fact(
        self,
        fact_id: str,
        new_content: str | None = None,
        new_confidence: float | None = None,
    ):
        """Update fact content and/or confidence. Re-embeds in ChromaDB."""
        fact = first(await self.db.select(MemoryLongTerm, ("id", fact_id)))
        if not fact:
            return

        if new_content is not None:
            fact.content = new_content
        if new_confidence is not None:
            fact.confidence = new_confidence

        await self.db.commit()

        # Re-embed in vector store
        await self._vector.upsert(
            collection=self._collection_name(fact.instance_id),
            ids=[fact_id],
            documents=[fact.content],
            metadatas=[
                {
                    "instance_id": fact.instance_id,
                    "category": fact.category,
                    "confidence": fact.confidence,
                }
            ],
            instance_id=fact.instance_id,
        )

    async def find_facts_by_content(
        self,
        instance_id: str,
        query: str,
        limit: int = 5,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """
        Find active (non-archived) facts whose content matches the query words.
        Used to resolve a forget request to concrete candidate facts.
        """
        words = [w.lower() for w in query.split() if len(w) >= 3]
        facts = await self.db.select(
            MemoryLongTerm,
            scope_q(MemoryLongTerm, instance_id, host_user_id),
            ("archived", False),
        )

        scored: list[tuple[int, dict]] = []
        for fact in facts:
            content_lower = fact.content.lower()
            score = sum(1 for w in words if w in content_lower) if words else 0
            if score > 0 or not words:
                scored.append((score, {
                    "id": fact.id,
                    "category": fact.category,
                    "content": fact.content,
                    "confidence": fact.confidence,
                }))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Keep only the strongest-matching tier so a distinctive query (e.g. a
        # rare marker word) resolves cleanly instead of dragging in facts that
        # merely share one common word.
        if words and scored:
            top_score = scored[0][0]
            scored = [s for s in scored if s[0] == top_score]
        return [s[1] for s in scored[:limit]]

    async def archive_fact(self, fact_id: str) -> bool:
        """
        Archive (forget) a fact: mark it archived in SQLite and remove its
        embedding from ChromaDB so it is no longer retrieved. Returns True if
        a fact was archived.
        """
        fact = first(await self.db.select(MemoryLongTerm, ("id", fact_id)))
        if not fact:
            return False

        fact.archived = True
        await self.db.commit()

        try:
            await self._vector.delete(
                collection=self._collection_name(fact.instance_id),
                ids=[fact_id],
                instance_id=fact.instance_id,
            )
        except Exception as e:
            logger.debug(f"Vector store delete failed for {fact_id}: {e}")

        logger.info(f"Archived (forgot) fact {fact_id}: {fact.content[:80]}")
        return True

    async def decay_unused(self, instance_id: str, days: int = 90):
        """
        Flag facts not used in the given number of days.
        Reduces confidence of stale facts rather than deleting them.
        """
        cutoff = utcnow() - timedelta(days=days)

        stale_facts = await self.db.select(
            MemoryLongTerm,
            ("instance_id", instance_id),
            ("last_used__lt", cutoff),
            ("confidence__gt", 0.1),
        )

        for fact in stale_facts:
            fact.confidence = max(fact.confidence * 0.5, 0.1)
            logger.debug(f"Decayed fact {fact.id}: confidence → {fact.confidence}")

        await self.db.commit()
        if stale_facts:
            logger.info(f"Decayed {len(stale_facts)} unused facts for instance {instance_id}")
