"""
P4.4a — Learned triggers from SystemSnapshot statistics.

Two public functions:
- analyze_snapshots(): Pure statistical analysis of 30d snapshot history
- seed_learned_triggers(): Create KgProactiveTrigger rows from candidates

These are sleep-time jobs — no LLM calls, no hot-path impact.
"""
import json
import logging
from datetime import datetime, timedelta

from ai.store import first

from ai.engine.core.clock import utcnow
from ai.engine.core.models import SystemSnapshot
from ai.engine.knowledge_graph.models import KgProactiveTrigger

logger = logging.getLogger("pulse.cognition.learned_triggers")

# ── Constants ────────────────────────────────────────────────────────────────

_MIN_SNAPSHOTS = 8          # Minimum snapshots needed for a rolling window
_ROLLING_WINDOW_DAYS = 7    # 7-day rolling average
_SIGMA_THRESHOLD = 2.0      # 2σ deviation = anomaly
_TREND_MIN_DAYS = 5         # 5+ consecutive days = trend
_CONFIDENCE_ENABLE_MIN = 0.7  # Triggers below this confidence are created disabled


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot analysis
# ═══════════════════════════════════════════════════════════════════════════════

async def analyze_snapshots(
    db,
    instance_id: str,
) -> list[dict]:
    """Analyze 30 days of SystemSnapshot rows for anomalies and trends.

    Args:
        db: Open async session.
        instance_id: The instance to analyze.

    Returns:
        List of trigger candidates, each with:
        {condition_type, field, threshold, direction, confidence}
    """
    cutoff = utcnow() - timedelta(days=30)

    snapshots = await db.select(
        SystemSnapshot,
        ("instance_id", instance_id),
        ("taken_at__gte", cutoff),
    )
    snapshots.sort(key=lambda s: s.taken_at)

    if len(snapshots) < _MIN_SNAPSHOTS:
        logger.debug(
            "analyze_snapshots: %d snapshots (< %d) for instance %s — skipping",
            len(snapshots), _MIN_SNAPSHOTS, instance_id,
        )
        return []

    # Parse numeric fields from snapshot_data JSON
    field_series: dict[str, list[float]] = {}
    timestamps: list[datetime] = []
    for snap in snapshots:
        if not snap.snapshot_data:
            continue
        try:
            data = json.loads(snap.snapshot_data)
        except (json.JSONDecodeError, TypeError):
            logger.debug("analyze_snapshots: invalid JSON in snapshot %s", snap.id)
            continue
        timestamps.append(snap.taken_at or utcnow())
        for key, value in data.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                field_series.setdefault(key, []).append(float(value))

    candidates: list[dict] = []

    for field, values in field_series.items():
        if len(values) < _MIN_SNAPSHOTS:
            continue

        # ── Anomaly detection: 2σ deviation from 7-day rolling mean ──
        for i in range(_ROLLING_WINDOW_DAYS, len(values)):
            window = values[i - _ROLLING_WINDOW_DAYS:i]
            mean = sum(window) / len(window)
            variance = sum((v - mean) ** 2 for v in window) / len(window)
            std = variance ** 0.5

            deviation = values[i] - mean

            if std == 0:
                # Window is flat. Any deviation from the mean is significant.
                if abs(deviation) > 0:
                    candidates.append({
                        "condition_type": "threshold",
                        "field": field,
                        "threshold": round(values[i], 4),
                        "direction": "above" if deviation > 0 else "below",
                        "confidence": 1.0,  # Certain: flat baseline, clear spike
                    })
                    break
                continue

            z_score = deviation / std
            if abs(z_score) >= _SIGMA_THRESHOLD:
                candidates.append({
                    "condition_type": "threshold",
                    "field": field,
                    "threshold": round(values[i], 4),
                    "direction": "above" if z_score > 0 else "below",
                    "confidence": round(min(abs(z_score) / (2 * _SIGMA_THRESHOLD), 1.0), 2),
                })
                break  # One anomaly per field is enough for a trigger

        # ── Trend detection: sustained increase/decrease for 5+ days ──
        if len(values) >= _TREND_MIN_DAYS:
            # Check last _TREND_MIN_DAYS for monotonic direction
            recent = values[-_TREND_MIN_DAYS:]
            increasing = all(recent[j] >= recent[j - 1] for j in range(1, len(recent)))
            decreasing = all(recent[j] <= recent[j - 1] for j in range(1, len(recent)))

            if increasing or decreasing:
                # Confidence: fraction of days that moved in the same direction
                moves = sum(
                    1 for j in range(1, len(recent))
                    if (increasing and recent[j] >= recent[j - 1])
                    or (decreasing and recent[j] <= recent[j - 1])
                )
                confidence = round(moves / (len(recent) - 1), 2)

                candidates.append({
                    "condition_type": "trend",
                    "field": field,
                    "threshold": round(values[-1], 4),
                    "direction": "increasing" if increasing else "decreasing",
                    "confidence": confidence,
                })

    logger.debug(
        "analyze_snapshots: %d snapshots → %d candidates for instance %s",
        len(snapshots), len(candidates), instance_id,
    )
    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# Trigger seeding
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_learned_triggers(
    db,
    instance_id: str,
    candidates: list[dict],
) -> int:
    """Create KgProactiveTrigger rows from analysis candidates.

    Deduplicates: skips if a trigger with the same (instance_id, name)
    already exists.

    Args:
        db: Open async session.
        instance_id: The instance to create triggers for.
        candidates: Output from ``analyze_snapshots()``.

    Returns:
        Number of new triggers created.
    """
    created = 0

    for candidate in candidates:
        name = f"Learned: {candidate['field']} {candidate['condition_type']}"

        # ── Deduplication check ──
        existing = await db.select(
            KgProactiveTrigger,
            ("instance_id", instance_id),
            ("name", name),
        )
        if first(existing) is not None:
            logger.debug("seed_learned_triggers: skipping duplicate '%s'", name)
            continue

        # ── Build condition_json ──
        condition = {
            "table": f"system_snapshots:{candidate['field']}",
            "column": candidate["field"],
        }
        if candidate["condition_type"] == "threshold":
            condition["value"] = candidate["threshold"]

        # ── Build description ──
        description = (
            f"Auto-generated: {candidate['field']} shows "
            f"{candidate['direction']} pattern "
            f"({candidate['condition_type']}, confidence={candidate['confidence']})"
        )

        confidence = candidate["confidence"]
        enabled = confidence >= _CONFIDENCE_ENABLE_MIN
        severity = "warning" if confidence >= 0.8 else "info"

        trigger = KgProactiveTrigger(
            instance_id=instance_id,
            name=name,
            category=candidate["condition_type"],
            description=description,
            severity=severity,
            enabled=enabled,
            condition_json=json.dumps(condition),
            data_sources_json="[]",
            context_queries_json="[]",
            recommended_actions_json="[]",
            recipients_json="[]",
            cooldown_seconds=3600,
            source="learned",
        )
        db.add(trigger)
        created += 1
        logger.info(
            "seed_learned_triggers: created '%s' (severity=%s, enabled=%s)",
            name, severity, enabled,
        )

    if created:
        await db.commit()
        logger.info(
            "seed_learned_triggers: %d new triggers for instance %s",
            created, instance_id,
        )

    return created
