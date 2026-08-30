"""
P4.4a — Statistical analysis of SystemSnapshot history.

Public function:
- analyze_snapshots(): Pure statistical analysis of 30d snapshot history

These are sleep-time jobs — no LLM calls, no hot-path impact.

NOTE (Pulse 0.2 Phase A5): the ``seed_learned_triggers`` seeding branch and
its ``trigger_learning`` job wiring were REMOVED — they produced
``KgProactiveTrigger`` rows whose ``condition_json`` referenced the
pseudo-table ``system_snapshots:<field>`` that the host-DB trigger evaluator
cannot query (dead triggers).  Re-wiring requires a snapshot-metrics crawler
that populates real, evaluable metrics (future phase).
"""
import json
import logging
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow
from ai.engine.core.models import SystemSnapshot

logger = logging.getLogger("pulse.cognition.learned_triggers")

# ── Constants ────────────────────────────────────────────────────────────────

_MIN_SNAPSHOTS = 8          # Minimum snapshots needed for a rolling window
_ROLLING_WINDOW_DAYS = 7    # 7-day rolling average
_SIGMA_THRESHOLD = 2.0      # 2σ deviation = anomaly
_TREND_MIN_DAYS = 5         # 5+ consecutive days = trend


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
