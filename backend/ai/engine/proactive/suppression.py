"""
Suppression & Fatigue Management — prevents alert overload through:
  - Cooldown: don't re-fire a trigger within its cooldown period
  - Deduplication: group co-occurring triggers into composite insights
  - Severity decay: expire unacknowledged info-level insights
  - Feedback learning: adjust triggers based on dismissal patterns
"""
import json
import logging
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow
from collections import defaultdict

from ai.store import first

from ai.engine.core.config import get_settings
from ai.engine.knowledge_graph.models import KgProactiveInsight, KgProactiveTrigger

logger = logging.getLogger("pulse.proactive.suppression")


def is_in_cooldown(trigger: dict) -> bool:
    """Check if a trigger is within its cooldown period."""
    last_fired = trigger.get("last_fired_at")
    if not last_fired:
        return False
    cooldown = trigger.get("cooldown_seconds", 3600)
    if isinstance(last_fired, str):
        last_fired = datetime.fromisoformat(last_fired)
    return utcnow() < last_fired + timedelta(seconds=cooldown)


def deduplicate_results(trigger_results: list, window_minutes: int = 30) -> list:
    """
    Group co-occurring trigger results into composite insights.
    Triggers that fire within the same window and share data sources
    get grouped under a single group_id.

    Returns enriched trigger results with group_id attached.
    """
    if not trigger_results:
        return []

    fired = [r for r in trigger_results if r.fired]
    if len(fired) <= 1:
        for r in fired:
            r._group_id = None
        return fired

    # Group by overlapping data sources
    groups = _cluster_by_data(fired)

    # Assign group IDs – single-member groups get no group_id
    enriched = []
    for group in groups:
        if len(group) > 1:
            # Use the highest-severity trigger as the group's primary
            group.sort(key=lambda r: {"critical": 0, "warning": 1, "info": 2}.get(r.severity, 9))
            group_id = f"grp_{group[0].trigger_id}_{utcnow().strftime('%H%M%S')}"
            for r in group:
                r._group_id = group_id
            enriched.extend(group)
        else:
            group[0]._group_id = None
            enriched.append(group[0])

    return enriched


def _cluster_by_data(results: list) -> list[list]:
    """
    Cluster trigger results by shared data tables in their snapshots.
    Simple single-pass: if two triggers reference the same table, group them.
    """
    table_map = defaultdict(list)

    for r in results:
        tables = set()
        snapshot = r.data_snapshot or {}
        if "table" in snapshot:
            tables.add(snapshot["table"])
        for sig in snapshot.get("signals", []):
            if isinstance(sig, dict) and "table" in sig:
                tables.add(sig["table"])

        if tables:
            for t in tables:
                table_map[t].append(r)
        else:
            table_map[f"_isolated_{r.trigger_id}"].append(r)

    # Merge overlapping groups
    seen = set()
    groups = []
    for key, members in table_map.items():
        group_members = []
        for m in members:
            if m.trigger_id not in seen:
                seen.add(m.trigger_id)
                group_members.append(m)
        if group_members:
            groups.append(group_members)

    return groups


async def record_dismissal(
    db,
    insight_id: str,
    reason: str,
) -> bool:
    """
    Record that a user dismissed an insight.
    Valid reasons: 'already_knew', 'not_relevant', 'false_positive'.
    Feeds back into trigger tuning.
    """
    settings = get_settings()

    insight = first(await db.select(KgProactiveInsight, ("id", insight_id)))
    if not insight:
        return False

    reason_map = {
        "already_knew": "dismissed_known",
        "not_relevant": "dismissed_irrelevant",
        "false_positive": "dismissed_false_positive",
    }
    insight.disposition = reason_map.get(reason, f"dismissed_{reason}")
    insight.dismissed_reason = reason
    await db.commit()

    # Feed back to trigger tuning if enabled
    if settings.KG_PROACTIVE_DISMISS_LEARNING and insight.trigger_id:
        await _learn_from_dismissal(db, insight.trigger_id, reason)

    logger.info(f"Insight {insight_id} dismissed: {reason}")
    return True


async def record_engagement(
    db,
    insight_id: str,
    action: str,
) -> bool:
    """
    Record positive engagement with an insight (read, acted_on).
    """
    valid_actions = {"read", "acted_on"}
    if action not in valid_actions:
        return False

    insight = first(await db.select(KgProactiveInsight, ("id", insight_id)))
    if not insight:
        return False

    insight.disposition = action
    await db.commit()
    return True


async def get_dismissal_stats(
    db,
    instance_id: str,
    days: int = 30,
) -> list[dict]:
    """
    Get dismissal statistics per trigger — identifies triggers that need tuning.
    Returns triggers sorted by dismissal rate.
    """
    cutoff = utcnow() - timedelta(days=days)

    insights = await db.select(
        KgProactiveInsight,
        ("instance_id", instance_id),
        ("created_at__gte", cutoff),
        ("trigger_id__isnull", False),
    )

    # Aggregate per trigger
    trigger_stats = defaultdict(lambda: {"total": 0, "dismissed": 0, "engaged": 0, "pending": 0})
    for insight in insights:
        stats = trigger_stats[insight.trigger_id]
        disposition = insight.disposition or ""
        stats["total"] += 1
        if disposition.startswith("dismissed"):
            stats["dismissed"] += 1
        elif disposition in ("read", "acted_on"):
            stats["engaged"] += 1
        else:
            stats["pending"] += 1

    # Calculate rates and sort
    result_list = []
    for trigger_id, stats in trigger_stats.items():
        total = stats["total"]
        dismissal_rate = stats["dismissed"] / total if total > 0 else 0
        result_list.append({
            "trigger_id": trigger_id,
            "total_insights": total,
            "dismissed": stats["dismissed"],
            "engaged": stats["engaged"],
            "pending": stats["pending"],
            "dismissal_rate": round(dismissal_rate, 3),
        })

    result_list.sort(key=lambda x: x["dismissal_rate"], reverse=True)
    return result_list


async def _learn_from_dismissal(
    db,
    trigger_id: str,
    reason: str,
) -> None:
    """
    Adjust trigger based on dismissal patterns.
    - 3+ 'false_positive' → flag for review (add to review queue)
    - 5+ 'not_relevant' → reduce severity or increase cooldown
    """
    cutoff = utcnow() - timedelta(days=30)

    # Count recent dismissals for this trigger
    dismissals = await db.select(
        KgProactiveInsight,
        ("trigger_id", trigger_id),
        ("created_at__gte", cutoff),
        ("dismissed_reason", reason),
    )
    count = len(dismissals)

    if reason == "false_positive" and count >= 3:
        # Flag for review via the review queue
        try:
            from ai.engine.knowledge_graph.feedback import ReviewQueue
            trig = first(await db.select(KgProactiveTrigger, ("id", trigger_id)))
            if trig:
                rq = ReviewQueue(trig.instance_id)
                await rq.add_item(
                    db,
                    category="trigger_tuning",
                    title=f"Trigger '{trig.name}' has {count} false positive dismissals",
                    description=f"Consider adjusting condition or disabling trigger",
                    evidence={"trigger_id": trigger_id, "false_positive_count": count},
                )
        except Exception as e:
            logger.debug(f"Failed to create review item: {e}")

    elif reason == "not_relevant" and count >= 5:
        # Increase cooldown by 50%
        trig = first(await db.select(KgProactiveTrigger, ("id", trigger_id)))
        if trig:
            trig.cooldown_seconds = int(trig.cooldown_seconds * 1.5)
            await db.commit()
            logger.info(
                f"Auto-increased cooldown for trigger '{trig.name}' "
                f"to {trig.cooldown_seconds}s due to {count} 'not_relevant' dismissals"
            )
