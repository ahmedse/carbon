"""
System state snapshots — capture key metrics, diff against previous, LLM-summarize changes.

All metric SQL comes from instance config (cognition.snapshots.metrics[] in instance.yaml).
If an instance has no snapshot config, the snapshot is skipped (empty, no error).
"""
import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import Instance, SystemSnapshot, generate_uuid

logger = logging.getLogger("pulse.cognition.state")


def _load_snapshot_config(instance: Instance) -> list[dict]:
    """Load snapshot metrics config from instance config JSON."""
    if not instance.config:
        return []
    try:
        config = json.loads(instance.config)
        return config.get("cognition", {}).get("snapshots", {}).get("metrics", [])
    except (json.JSONDecodeError, AttributeError):
        return []


async def _query_host_metrics(instance: Instance) -> dict:
    """Query key metrics from the host database for a snapshot.

    Reads metrics from instance config (cognition.snapshots.metrics[]).
    Each metric defines a name and query_sql.  Returns dict of metric_name → rows.
    """
    import psycopg2

    metrics_config = _load_snapshot_config(instance)
    if not metrics_config:
        logger.debug("No snapshot metrics configured for %s, returning empty", instance.name)
        return {}

    metrics: dict = {}

    def _collect():
        conn = psycopg2.connect(instance.host_db_url)
        try:
            conn.set_session(readonly=True)
            cur = conn.cursor()

            for mc in metrics_config:
                name = mc.get("name")
                query_sql = mc.get("query_sql")
                if not name or not query_sql:
                    continue
                try:
                    cur.execute(query_sql)
                    cols = [d[0] for d in cur.description] if cur.description else []
                    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                    metrics[name] = rows
                except Exception:
                    metrics[name] = []

            cur.close()
        finally:
            conn.close()

    await asyncio.to_thread(_collect)
    return metrics


def _find_identity_key(rows: list[dict]) -> str | None:
    """Heuristic: find a column that looks like an identity key in a list of dicts."""
    if not rows or not isinstance(rows[0], dict):
        return None
    keys = list(rows[0].keys())
    for candidate in ("name", "id", "table_name", "module_name", "rule_type", "scope", "status"):
        if candidate in keys:
            return candidate
    return keys[0] if keys else None


def _diff_snapshots(old_data: dict, new_data: dict) -> dict:
    """Compare two snapshot data dicts and return differences (generic).

    For list-type metrics, compares by an identity key (name, id, etc.).
    For dict-type or scalar metrics, compares directly.
    """
    diff: dict = {}
    all_keys = set(old_data.keys()) | set(new_data.keys())

    for key in sorted(all_keys):
        old_val = old_data.get(key, [])
        new_val = new_data.get(key, [])

        if isinstance(old_val, list) and isinstance(new_val, list):
            id_key = _find_identity_key(old_val or new_val)
            if id_key:
                # Name-based comparison
                old_by_id = {item.get(id_key): item for item in old_val if item.get(id_key) is not None}
                new_by_id = {item.get(id_key): item for item in new_val if item.get(id_key) is not None}

                changes: list[dict] = []
                for nid, new_item in new_by_id.items():
                    old_item = old_by_id.get(nid)
                    if old_item is None:
                        changes.append({"item": nid, "change": "added"})
                    elif old_item != new_item:
                        # Detail which fields changed
                        field_deltas = {}
                        for fk in set(list(old_item.keys()) + list(new_item.keys())):
                            ov = old_item.get(fk)
                            nv = new_item.get(fk)
                            if ov != nv and fk != id_key:
                                if isinstance(ov, (int, float)) and isinstance(nv, (int, float)):
                                    field_deltas[fk] = {"old": ov, "new": nv, "delta": nv - ov}
                                else:
                                    field_deltas[fk] = {"old": ov, "new": nv}
                        if field_deltas:
                            changes.append({"item": nid, "change": "modified", "fields": field_deltas})

                for nid in old_by_id:
                    if nid not in new_by_id:
                        changes.append({"item": nid, "change": "removed"})

                if changes:
                    diff[key] = changes
            elif old_val != new_val:
                diff[key] = {"old_count": len(old_val), "new_count": len(new_val)}
        elif old_val != new_val:
            diff[key] = {"old": old_val, "new": new_val}

    return diff


async def _summarize_diff(diff: dict, instance_id: str = "system") -> str:
    """Use LLM to generate a narrative summary of changes."""
    if not diff:
        return "No significant changes detected."

    from ai.engine.llm.router import route_chat

    prompt = (
        "Summarize these system changes in 2-3 sentences for a system operator:\n\n"
        + json.dumps(diff, indent=2, default=str)
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"snapshot-diff-{instance_id}",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return result.get("content", "")
    except Exception as e:
        logger.warning(f"Failed to summarize diff: {e}")
        # Fallback: simple text summary from generic diff keys
        parts = []
        for key, changes in diff.items():
            if isinstance(changes, list):
                parts.append(f"{len(changes)} change(s) in {key}")
            else:
                parts.append(f"change in {key}")
        return "; ".join(parts) if parts else "Changes detected (summary unavailable)."


async def take_snapshot(db: AsyncSession, instance: Instance):
    """Take a system state snapshot, diff against previous, and store."""
    logger.info(f"Taking snapshot for {instance.name}")

    # Collect current metrics
    snapshot_data = await _query_host_metrics(instance)

    # Get previous snapshot for diffing
    stmt = (
        select(SystemSnapshot)
        .where(SystemSnapshot.instance_id == instance.id)
        .order_by(SystemSnapshot.taken_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    prev_snapshot = result.scalar_one_or_none()

    diff = {}
    summary = "Initial snapshot."

    if prev_snapshot and prev_snapshot.snapshot_data:
        try:
            prev_data = json.loads(prev_snapshot.snapshot_data)
            diff = _diff_snapshots(prev_data, snapshot_data)
            if diff:
                summary = await _summarize_diff(diff, instance_id=instance.id)
            else:
                summary = "No significant changes since last snapshot."
        except json.JSONDecodeError:
            pass

    # Store new snapshot
    new_snapshot = SystemSnapshot(
        id=generate_uuid(),
        instance_id=instance.id,
        snapshot_data=json.dumps(snapshot_data, default=str),
        diff_from_previous=json.dumps(diff, default=str) if diff else None,
        summary=summary,
    )
    db.add(new_snapshot)
    await db.commit()

    logger.info(f"Snapshot saved for {instance.name}: {summary[:80]}")
    return new_snapshot
