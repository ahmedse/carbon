"""
Cognition synthesis — pattern detection, insight generation, and wisdom accumulation.

Three core operations:
1. synthesize_insights: Analyze recent snapshots, notifications, and memories to find patterns
2. reflect_on_insights: Consolidate old insights, supersede duplicates, raise confidence on recurring patterns
3. decay_stale_memories: Lower confidence on unused memories, archive very stale ones
"""
import json
import logging
from datetime import timedelta

from ai.engine.core.clock import utcnow

from ai.store import first, scope_q

from ai.engine.core.config import get_settings
from ai.engine.core.models import (
    Insight,
    Instance,
    MemoryEpisodic,
    MemoryLongTerm,
    Message,
    Notification,
    SystemSnapshot,
    generate_uuid,
)

logger = logging.getLogger("pulse.cognition.synthesis")


# ── 1. Synthesize Insights ───────────────────────────────────────────────

async def synthesize_insights(db, instance: Instance):
    """
    Analyze recent system data and generate insights.
    Looks at:
    - Recent snapshots and their diffs
    - Recent notifications (patterns in warnings/criticals)
    - Episodic memories (recurring event types)
    - Long-term memories (low-confidence or contradictory facts)
    """
    logger.info(f"Synthesizing insights for {instance.name}...")

    context = await _gather_synthesis_context(db, instance)

    if not context["has_data"]:
        logger.debug(f"No meaningful data to synthesize for {instance.name}")
        return

    # Check for existing recent insights to avoid duplicates.
    # Only count shared/instance-wide insights; private user insights don't affect synthesis.
    recent_cutoff = utcnow() - timedelta(hours=6)
    recent_count = (
        await db.aggregate(
            Insight,
            {"count": ("Count", "id")},
            scope_q(Insight, instance.id, None),
            ("created_at__gt", recent_cutoff),
        )
    )["count"] or 0
    if recent_count >= 5:
        logger.debug(f"Already {recent_count} recent insights for {instance.name}, skipping")
        return

    # Use LLM to find patterns
    from ai.engine.llm.router import route_chat

    prompt = _build_synthesis_prompt(context)

    try:
        router_result = await route_chat(
            task="cognition",
            instance_id=instance.id,
            conversation_id=f"cognition-synthesis-{instance.id}",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI operations analyst. Analyze system monitoring data "
                        "and produce structured insights. Return a JSON array of insight objects. "
                        "Each insight has: type (pattern|trend|anomaly|recommendation), "
                        "title (short), content (detailed explanation), confidence (0.0-1.0). "
                        "Only include genuinely useful insights. Return [] if nothing significant."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        raw = (router_result["content"] or "").strip()
        # Extract JSON from potential markdown code blocks
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        insights_data = json.loads(raw)
        if not isinstance(insights_data, list):
            insights_data = [insights_data]

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Synthesis LLM call failed for {instance.name}: {e}")
        # Fallback: generate statistical insights without LLM
        insights_data = _statistical_insights(context)

    # Store generated insights
    for item in insights_data[:3]:  # Cap at 3 per cycle
        insight = Insight(
            id=generate_uuid(),
            instance_id=instance.id,
            insight_type=item.get("type", "pattern"),
            title=item.get("title", "Untitled insight"),
            content=item.get("content", ""),
            evidence=json.dumps(context.get("evidence_summary", {})),
            confidence=min(max(float(item.get("confidence", 0.5)), 0.1), 1.0),
            host_user_id=None,       # Instance-wide insight (not user-private)
            visibility="shared",     # Visible to all users of this instance
        )
        db.add(insight)

    await db.commit()
    logger.info(f"Synthesized {len(insights_data[:3])} insights for {instance.name}")


async def _gather_synthesis_context(db, instance: Instance) -> dict:
    """Gather all relevant data for synthesis."""
    ctx: dict = {"has_data": False, "evidence_summary": {}}

    # Recent snapshots (last 5)
    snapshots = await db.select(
        SystemSnapshot,
        ("instance_id", instance.id),
    )
    snapshots.sort(key=lambda s: s.taken_at, reverse=True)
    snapshots = snapshots[:5]
    ctx["snapshots"] = []
    for s in snapshots:
        entry = {"taken_at": s.taken_at.isoformat() if s.taken_at else None, "summary": s.summary}
        if s.diff_from_previous:
            try:
                entry["diff"] = json.loads(s.diff_from_previous)
            except json.JSONDecodeError:
                pass
        ctx["snapshots"].append(entry)

    # Recent notifications (last 20) — instance-wide (host_user_id=None → shared + global only)
    notifications = await db.select(
        Notification,
        scope_q(Notification, instance.id, None),
    )
    notifications.sort(key=lambda n: n.created_at, reverse=True)
    notifications = notifications[:20]
    ctx["notifications"] = [
        {
            "severity": n.severity,
            "title": n.title,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]

    # Notification frequency by severity
    sev_counts = {}
    for n in notifications:
        sev_counts[n.severity] = sev_counts.get(n.severity, 0) + 1
    ctx["notification_frequency"] = sev_counts

    # Recent episodes (last 20) — shared/global only for instance-wide synthesis
    episodes = await db.select(
        MemoryEpisodic,
        scope_q(MemoryEpisodic, instance.id, None),
        ("archived", False),
    )
    episodes.sort(key=lambda e: e.occurred_at, reverse=True)
    episodes = episodes[:20]
    ctx["episodes"] = [
        {"event_type": e.event_type, "summary": e.summary}
        for e in episodes
    ]

    # Episode type frequency
    type_counts = {}
    for e in episodes:
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
    ctx["episode_frequency"] = type_counts

    # Memory stats — shared/global only for instance-wide synthesis.
    mem_count = (
        await db.aggregate(
            MemoryLongTerm,
            {"count": ("Count", "id")},
            scope_q(MemoryLongTerm, instance.id, None),
            ("archived", False),
        )
    )["count"] or 0
    ctx["memory_count"] = mem_count

    # Low-confidence memories — shared/global only for instance-wide synthesis
    low_conf = await db.select(
        MemoryLongTerm,
        scope_q(MemoryLongTerm, instance.id, None),
        ("archived", False),
        ("confidence__lt", 0.5),
    )
    low_conf = low_conf[:5]
    ctx["low_confidence_memories"] = [
        {"content": m.content, "confidence": m.confidence, "category": m.category}
        for m in low_conf
    ]

    ctx["has_data"] = bool(snapshots or notifications or episodes)
    ctx["evidence_summary"] = {
        "snapshots": len(snapshots),
        "notifications": len(notifications),
        "episodes": len(episodes),
        "memories": mem_count,
        "timestamp": utcnow().isoformat(),
    }

    return ctx


def _build_synthesis_prompt(ctx: dict) -> str:
    """Build the synthesis prompt from gathered context."""
    parts = [f"Analyze the following system monitoring data and identify patterns, trends, anomalies, or recommendations.\n"]

    if ctx["snapshots"]:
        parts.append("## Recent Snapshots")
        for s in ctx["snapshots"][:3]:
            parts.append(f"- {s.get('taken_at', '?')}: {s.get('summary', 'no summary')}")
            if s.get("diff"):
                parts.append(f"  Changes: {json.dumps(s['diff'], default=str)[:500]}")

    if ctx["notification_frequency"]:
        parts.append(f"\n## Notification Frequency: {json.dumps(ctx['notification_frequency'])}")
        parts.append("Recent notifications:")
        for n in ctx["notifications"][:5]:
            parts.append(f"- [{n['severity']}] {n['title']}")

    if ctx["episode_frequency"]:
        parts.append(f"\n## Episode Frequency: {json.dumps(ctx['episode_frequency'])}")
        for e in ctx["episodes"][:5]:
            parts.append(f"- [{e['event_type']}] {e['summary']}")

    if ctx["low_confidence_memories"]:
        parts.append("\n## Low-Confidence Memories (may need verification)")
        for m in ctx["low_confidence_memories"]:
            parts.append(f"- [{m['category']}] {m['content']} (confidence: {m['confidence']:.0%})")

    parts.append(f"\nTotal memories: {ctx['memory_count']}")
    parts.append("\nReturn JSON array of insights. Each: {type, title, content, confidence}")

    return "\n".join(parts)


def _statistical_insights(ctx: dict) -> list[dict]:
    """Generate simple statistical insights without LLM."""
    insights = []

    # Notification pattern
    sev = ctx.get("notification_frequency", {})
    if sev.get("critical", 0) >= 3:
        insights.append({
            "type": "anomaly",
            "title": f"High critical notification rate ({sev['critical']} recent)",
            "content": "Multiple critical notifications detected in the monitoring window. This may indicate a systemic issue requiring investigation.",
            "confidence": 0.8,
        })

    # Episode recurrence
    freq = ctx.get("episode_frequency", {})
    for etype, count in freq.items():
        if count >= 3:
            insights.append({
                "type": "pattern",
                "title": f"Recurring '{etype}' events ({count} occurrences)",
                "content": f"The event type '{etype}' has occurred {count} times recently. Consider investigating the root cause.",
                "confidence": 0.7,
            })

    return insights


# ── 2. Reflect on Insights ───────────────────────────────────────────────

async def reflect_on_insights(db, instance: Instance):
    """
    Meta-cognition: review existing insights, consolidate duplicates,
    and supersede outdated ones.
    """
    logger.info(f"Reflecting on insights for {instance.name}...")

    # Get all active insights — instance-wide synthesis; never touch private user rows
    insights = await db.select(
        Insight,
        scope_q(Insight, instance.id, None),
        ("archived", False),
    )
    insights.sort(key=lambda i: i.created_at, reverse=True)
    insights = insights[:50]

    if len(insights) < 2:
        return

    # Group by type and look for similar titles
    by_type: dict[str, list] = {}
    for ins in insights:
        by_type.setdefault(ins.insight_type, []).append(ins)

    for itype, group in by_type.items():
        if len(group) < 2:
            continue

        # Simple dedup: if two insights have very similar titles, supersede the older one
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                older, newer = group[j], group[i]  # group is ordered desc
                if _titles_similar(older.title, newer.title):
                    # Supersede older with newer, boost newer's confidence
                    older.superseded_by = newer.id
                    older.archived = True
                    newer.confidence = min(newer.confidence + 0.1, 1.0)
                    logger.info(f"Superseded insight '{older.title}' → '{newer.title}'")

    # Archive very old insights (>30 days) with low confidence
    cutoff = utcnow() - timedelta(days=30)
    old_insights = await db.select(
        Insight,
        scope_q(Insight, instance.id, None),
        ("archived", False),
        ("created_at__lt", cutoff),
        ("confidence__lt", 0.5),
    )
    for ins in old_insights:
        ins.archived = True
        logger.debug(f"Auto-archived stale insight: {ins.title}")

    await db.commit()
    logger.info(f"Reflection complete for {instance.name}: reviewed {len(insights)} insights")


def _titles_similar(a: str, b: str) -> bool:
    """Simple similarity check: shared significant words."""
    stop = {"the", "a", "an", "is", "in", "for", "of", "to", "and", "or"}
    words_a = {w.lower() for w in a.split() if w.lower() not in stop and len(w) > 2}
    words_b = {w.lower() for w in b.split() if w.lower() not in stop and len(w) > 2}
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
    return overlap > 0.6


# ── 3. Decay Stale Memories ──────────────────────────────────────────────

async def decay_stale_memories(db, instance: Instance):
    """
    Reduce confidence of memories that haven't been used recently.
    Auto-archive memories with very low confidence.
    """
    logger.info(f"Running memory decay for {instance.name}...")

    settings = get_settings()
    decay_days = settings.COGNITION_DECAY_AFTER_DAYS

    cutoff = utcnow() - timedelta(days=decay_days)

    # Get stale, unused memories — instance-wide; never touch private user rows
    stale_memories = await db.select(
        MemoryLongTerm,
        scope_q(MemoryLongTerm, instance.id, None),
        ("archived", False),
        ("last_used__lt", cutoff),
        ("confidence__gt", 0.1),
    )

    decayed = 0
    archived = 0
    for mem in stale_memories:
        # Decay: reduce by 10%
        mem.confidence = round(max(mem.confidence * 0.9, 0.05), 3)

        # Auto-archive if confidence drops very low and unused for 2x the decay window
        double_cutoff = utcnow() - timedelta(days=decay_days * 2)
        if mem.confidence < 0.15 and mem.last_used < double_cutoff:
            mem.archived = True
            archived += 1
        else:
            decayed += 1

    await db.commit()
    if decayed or archived:
        logger.info(
            f"Memory decay for {instance.name}: "
            f"{decayed} decayed, {archived} auto-archived"
        )


# ── 4. User Preference Learning ─────────────────────────────────────────

async def learn_user_preferences(db, instance: Instance):
    """
    Analyze conversation history per user to detect behavioral patterns
    and store them as preference memories for personalized interactions.

    Detects:
    - Frequent topics / entity types queried
    - Preferred conversation mode (normal vs deep)
    - Time-of-day usage patterns
    - Common page contexts (where they chat from)
    """
    from ai.engine.core.models import Conversation, Message

    logger.info(f"Learning user preferences for {instance.name}...")

    # Look at conversations from the last 30 days
    cutoff = utcnow() - timedelta(days=30)

    conversations = await db.select(
        Conversation,
        ("instance_id", instance.id),
        ("started_at__gte", cutoff),
        ("user_identifier__isnull", False),
    )
    conversations.sort(key=lambda c: c.started_at, reverse=True)

    if len(conversations) < 3:
        logger.debug(f"Too few conversations for preference learning ({len(conversations)})")
        return

    # Group by user
    user_convs: dict[str, list] = {}
    for conv in conversations:
        user_convs.setdefault(conv.user_identifier, []).append(conv)

    preferences_stored = 0
    for user_id, convs in user_convs.items():
        if len(convs) < 2:
            continue

        prefs = _extract_user_patterns(user_id, convs)
        if not prefs:
            continue

        # Check for existing preference for this user — shared visibility (auto-generated rows)
        existing = first(
            await db.select(
                MemoryLongTerm,
                scope_q(MemoryLongTerm, instance.id, None),
                ("category", "preference"),
                ("source", f"auto:user:{user_id}"),
                ("archived", False),
            )
        )

        pref_text = f"User '{user_id}' patterns: {prefs}"

        if existing:
            # Update existing preference
            existing.content = pref_text
            existing.confidence = min(0.6 + len(convs) * 0.02, 0.95)
            existing.last_used = utcnow()
        else:
            # Create new preference
            fact = MemoryLongTerm(
                id=generate_uuid(),
                instance_id=instance.id,
                category="preference",
                content=pref_text,
                source=f"auto:user:{user_id}",
                confidence=min(0.5 + len(convs) * 0.02, 0.9),
            )
            db.add(fact)

        preferences_stored += 1

    await db.commit()
    if preferences_stored:
        logger.info(
            f"Learned preferences for {preferences_stored} users in {instance.name}"
        )


def _extract_user_patterns(user_id: str, convs: list) -> str:
    """Extract human-readable preference summary from conversation history."""
    parts = []

    # Mode preference
    modes = [c.mode for c in convs if c.mode]
    if modes:
        from collections import Counter
        mode_dist = Counter(modes)
        dominant_mode = mode_dist.most_common(1)[0]
        if dominant_mode[1] > len(modes) * 0.7:
            parts.append(f"prefers {dominant_mode[0]} mode")

    # Page context (where they chat from)
    pages = [c.page_context for c in convs if c.page_context]
    if pages:
        from collections import Counter
        page_dist = Counter(pages)
        top_pages = page_dist.most_common(3)
        page_labels = [f"{p[0]} ({p[1]}x)" for p in top_pages]
        parts.append(f"usually chats from: {', '.join(page_labels)}")

    # Time patterns
    hours = [c.started_at.hour for c in convs if c.started_at]
    if hours:
        from collections import Counter
        hour_dist = Counter(hours)
        peak_hour = hour_dist.most_common(1)[0][0]
        if hour_dist.most_common(1)[0][1] >= 3:
            period = "morning" if peak_hour < 12 else "afternoon" if peak_hour < 17 else "evening"
            parts.append(f"most active in the {period} (around {peak_hour}:00)")

    # Conversation frequency
    if len(convs) >= 5:
        days_span = max((convs[0].started_at - convs[-1].started_at).days, 1)
        freq = len(convs) / days_span
        if freq > 1:
            parts.append(f"high usage ({len(convs)} conversations in {days_span} days)")
        elif freq > 0.3:
            parts.append(f"regular user ({len(convs)} conversations over {days_span} days)")

    return "; ".join(parts) if parts else ""


# ── 5. Recurring Query Pattern Detection ──────────────────────────────────

async def detect_recurring_queries(db, instance: Instance):
    """
    Analyse conversation history to find recurring query patterns.
    When a pattern is detected (same intent >3 times in 14 days),
    creates a proactive insight suggesting a scheduled report.
    """
    from collections import Counter
    from ai.engine.core.models import Conversation, Message

    instance_id = instance.id
    since = utcnow() - timedelta(days=14)

    # Get user messages from the last 14 days (join done in Python — Store has no joins)
    convs = await db.select(
        Conversation,
        ("instance_id", instance_id),
        ("started_at__gte", since),
    )
    conv_ids = [c.id for c in convs]
    if not conv_ids:
        return
    msg_rows = await db.select(
        Message,
        ("conversation_id__in", conv_ids),
        ("role", "user"),
    )
    msg_rows.sort(key=lambda m: m.timestamp, reverse=True)
    msg_rows = msg_rows[:500]
    messages = [m.content for m in msg_rows if m.content and len(m.content) > 10]

    if len(messages) < 5:
        return

    # Normalise: lowercase, strip punctuation, bucket by leading keywords
    import re
    normalised = []
    for m in messages:
        clean = re.sub(r"[^\w\s]", "", m.lower()).strip()
        # Take first 5 significant words as a fingerprint
        words = [w for w in clean.split() if len(w) > 2][:5]
        if words:
            normalised.append(" ".join(words))

    freq = Counter(normalised)
    recurring = [(pattern, count) for pattern, count in freq.most_common(10) if count >= 3]

    if not recurring:
        return

    # Check if we already surfaced a pattern insight recently (7 days)
    from ai.engine.knowledge_graph.models import KgProactiveInsight

    recent_pattern_insights = await db.select(
        KgProactiveInsight,
        ("instance_id", instance_id),
        ("insight_type", "recurring_query_pattern"),
        ("created_at__gte", utcnow() - timedelta(days=7)),
    )
    if first(recent_pattern_insights):
        return  # Already surfaced recently

    # Build the insight
    top_patterns = recurring[:5]
    pattern_lines = [f"- \"{p}\" ({c} times)" for p, c in top_patterns]

    insight_data = {
        "insight_type": "recurring_query_pattern",
        "severity": "info",
        "title": f"Recurring queries detected ({len(recurring)} patterns)",
        "narrative": (
            f"Over the last 14 days, these question patterns were asked repeatedly:\n"
            + "\n".join(pattern_lines)
            + "\n\nConsider setting up scheduled reports for these recurring information needs."
        ),
        "recommended_actions": [
            "Review these patterns and consider automating the most frequent ones.",
            "Use daily briefing to cover these topics automatically.",
        ],
        "context": {"patterns": [{"query": p, "count": c} for p, c in top_patterns]},
    }

    from ai.engine.proactive.delivery import deliver_insight
    await deliver_insight(db, instance_id, insight_data)

    logger.info(
        f"Detected {len(recurring)} recurring query patterns for {instance_id}"
    )


# ── 6. Per-User Weekly Self-Reflection ───────────────────────────────────

async def self_reflect(
    db, instance: Instance, host_user_id: str,
    llm_client=None,
) -> str | None:
    """
    Generate a private weekly-summary Insight for one host user.

    Gathers recent Messages, Episodes, and LongTerm facts for the user
    (past 7 days), builds a prompt, calls LLM_COGNITION_MODEL, and stores
    a ``weekly_summary`` Insight row.

    Idempotent: skips if an existing ``weekly_summary`` was created for this
    ``host_user_id`` within the past 6 days.

    Fail-open: any LLM error is logged and ``None`` is returned.
    """
    logger.debug("self_reflect: starting for user=%s in %s", host_user_id, instance.name)

    # ── Idempotency check ──────────────────────────────────────────────
    idem_cutoff = utcnow() - timedelta(days=6)
    existing = first(
        await db.select(
            Insight,
            ("instance_id", instance.id),
            ("insight_type", "weekly_summary"),
            ("host_user_id", host_user_id),
            ("created_at__gte", idem_cutoff),
        )
    )
    if existing is not None:
        logger.debug(
            "self_reflect: skipping user=%s — summary exists from %s",
            host_user_id, existing.created_at.isoformat() if existing.created_at else "?",
        )
        return None

    week_start = utcnow() - timedelta(days=7)

    # ── Gather data ────────────────────────────────────────────────────
    # Messages (last 50 user/assistant, past 7 days)
    msg_rows = await db.select(
        Message,
        ("host_user_id", host_user_id),
        ("timestamp__gte", week_start),
        ("role__in", ["user", "assistant"]),
    )
    msg_rows.sort(key=lambda m: m.timestamp, reverse=True)
    msg_rows = msg_rows[:50]

    # Episodes (last 20, past 7 days) — private rows for this user only
    ep_rows = await db.select(
        MemoryEpisodic,
        ("instance_id", instance.id),
        ("host_user_id", host_user_id),
        ("occurred_at__gte", week_start),
        ("archived", False),
    )
    ep_rows.sort(key=lambda e: e.occurred_at, reverse=True)
    ep_rows = ep_rows[:20]

    # Long-term facts (last 10 updated, past 7 days) — private rows for this user
    lt_rows = await db.select(
        MemoryLongTerm,
        ("instance_id", instance.id),
        ("host_user_id", host_user_id),
        ("last_used__gte", week_start),
        ("archived", False),
    )
    lt_rows.sort(key=lambda m: m.last_used, reverse=True)
    lt_rows = lt_rows[:10]

    if not msg_rows and not ep_rows and not lt_rows:
        logger.debug(
            "self_reflect: no data for user=%s in past 7 days, skipping", host_user_id
        )
        return None

    # ── Build prompt ───────────────────────────────────────────────────
    prompt = _build_self_reflect_prompt(
        host_user_id, msg_rows, ep_rows, lt_rows,
        week_start.strftime("%Y-%m-%d"), utcnow().strftime("%Y-%m-%d"),
    )

    # ── LLM call (fail-open) ───────────────────────────────────────────
    try:
        if llm_client is not None:
            # Test path — route through the central router for budget enforcement
            from ai.engine.llm.router import route_chat as _route_chat
            router_result = await _route_chat(
                task="cognition",
                instance_id=instance.id,
                conversation_id=f"cognition-self-reflect-{instance.id}-{host_user_id}",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an AI assistant that writes concise, helpful weekly "
                            "summaries for individual users. Focus on what the user worked on, "
                            "key questions asked, corrections given, and facts learned about "
                            "the user. Target 150–250 words. Be specific — reference actual "
                            "topics and data points mentioned. Write in second person ('you'). "
                            "Do NOT include meta-commentary about the summary itself."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            summary_text = (router_result["content"] or "").strip()
        else:
            from ai.engine.llm.router import route_chat as _route_chat
            router_result = await _route_chat(
                task="cognition",
                instance_id=instance.id,
                conversation_id=f"cognition-self-reflect-{instance.id}-{host_user_id}",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an AI assistant that writes concise, helpful weekly "
                            "summaries for individual users. Focus on what the user worked on, "
                            "key questions asked, corrections given, and facts learned about "
                            "the user. Target 150–250 words. Be specific — reference actual "
                            "topics and data points mentioned. Write in second person ('you'). "
                            "Do NOT include meta-commentary about the summary itself."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            summary_text = (router_result["content"] or "").strip()
    except Exception as e:
        logger.warning(
            "self_reflect: LLM call failed for user=%s in %s: %s",
            host_user_id, instance.name, e,
        )
        return None

    if not summary_text or len(summary_text) < 20:
        logger.debug("self_reflect: LLM returned empty/short summary for user=%s", host_user_id)
        return None

    # ── Store Insight ──────────────────────────────────────────────────
    title = (
        f"Weekly summary for {week_start.strftime('%Y-%m-%d')}"
        f" → {utcnow().strftime('%Y-%m-%d')}"
    )
    insight = Insight(
        id=generate_uuid(),
        instance_id=instance.id,
        insight_type="weekly_summary",
        title=title,
        content=summary_text,
        confidence=0.6,
        host_user_id=host_user_id,
        visibility="private",
    )
    db.add(insight)
    await db.commit()

    logger.info(
        "self_reflect: stored weekly_summary for user=%s in %s (%d chars)",
        host_user_id, instance.name, len(summary_text),
    )
    return insight.id


def _build_self_reflect_prompt(
    host_user_id: str,
    messages: list,
    episodes: list,
    long_term_facts: list,
    week_start_str: str,
    week_end_str: str,
) -> str:
    """Assemble the prompt for the self-reflection LLM call."""
    parts = [
        f"Write a weekly summary for user '{host_user_id}' covering {week_start_str} to {week_end_str}.",
        "Focus on: key topics discussed, questions asked, corrections the user gave, "
        "and facts Pulse learned about this user.",
        "",
    ]

    if messages:
        parts.append("## Recent Conversations")
        for i, m in enumerate(messages[:50], 1):
            role_label = "User" if m.role == "user" else "AI"
            content = (m.content or "")[:500]
            parts.append(f"{i}. {role_label}: {content}")
        parts.append("")

    if episodes:
        parts.append("## Notable Events / Episodes")
        for e in episodes[:20]:
            ts = e.occurred_at.strftime("%Y-%m-%d") if e.occurred_at else "?"
            parts.append(f"- [{ts}] [{e.event_type}] {e.summary}")
        parts.append("")

    if long_term_facts:
        parts.append("## Facts Pulse Learned About This User")
        for f in long_term_facts[:10]:
            parts.append(f"- [{f.category}] {f.content} (confidence: {f.confidence:.0%})")
        parts.append("")

    parts.append(
        "Write the summary now. Target 150–250 words. Use second person ('you'). "
        "Only include information from the data above."
    )
    return "\n".join(parts)


async def run_self_reflection(db, instance: Instance):
    """
    Entry point: run self-reflection for every active host user in this instance.

    Discovers users with Message activity in the past 14 days, then calls
    ``self_reflect()`` for each.
    """
    logger.info("Running self-reflection sweep for %s...", instance.name)

    since = utcnow() - timedelta(days=14)
    msg_rows = await db.select(
        Message,
        ("host_user_id__isnull", False),
        ("timestamp__gte", since),
    )
    user_ids: list[str] = []
    for row in msg_rows:
        uid = row.host_user_id
        if uid and uid not in user_ids:
            user_ids.append(uid)

    if not user_ids:
        logger.debug("No active users for self-reflection in %s", instance.name)
        return

    stored = 0
    for host_user_id in user_ids:
        try:
            result = await self_reflect(db, instance, host_user_id)
            if result:
                stored += 1
        except Exception as e:
            logger.warning(
                "self_reflect: error for user=%s in %s: %s",
                host_user_id, instance.name, e,
            )

    logger.info(
        "Self-reflection sweep for %s: %d summaries stored across %d users",
        instance.name, stored, len(user_ids),
    )
