"""
Cognition monitors — health, data freshness, failed jobs, schema drift.
Each monitor queries the host DB (read-only) and creates notifications when issues are found.

All monitor SQL comes from instance config (cognition.monitors[] in instance.yaml).
No hardcoded queries — if an instance has no cognition config, monitors are skipped silently.
"""
import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.cognition.notifier import create_notification
from ai.engine.core.models import Instance

logger = logging.getLogger("pulse.cognition.monitors")


def _load_monitors_config(instance: Instance) -> list[dict]:
    """Load all monitor configs from instance config JSON."""
    if not instance.config:
        return []
    try:
        config = json.loads(instance.config)
        return config.get("cognition", {}).get("monitors", [])
    except (json.JSONDecodeError, AttributeError):
        return []


async def _execute_monitor_sql(instance: Instance, query_sql: str) -> list[dict]:
    """Execute a monitor's SELECT SQL against the host DB and return rows as dicts."""
    import psycopg2

    rows: list[dict] = []

    def _query():
        conn = psycopg2.connect(instance.host_db_url)
        try:
            conn.set_session(readonly=True)
            cur = conn.cursor()
            try:
                cur.execute(query_sql)
                cols = [d[0] for d in cur.description] if cur.description else []
                for row in cur.fetchall():
                    rows.append(dict(zip(cols, row)))
            finally:
                cur.close()
        finally:
            conn.close()

    await asyncio.to_thread(_query)
    return rows


async def check_model_health(db: AsyncSession, instance: Instance):
    """Check health scores against thresholds.

    Reads monitors with value_column + thresholds from instance config.
    Computes the pass_rate from passed_checks/total_checks when value_column='pass_rate'.
    """
    monitors = _load_monitors_config(instance)
    if not monitors:
        logger.debug("No cognition monitors for %s, skipping health check", instance.name)
        return

    for monitor in monitors:
        query_sql = monitor.get("query_sql")
        value_column = monitor.get("value_column")
        warning_threshold = monitor.get("warning_threshold")
        critical_threshold = monitor.get("critical_threshold")

        if not query_sql or not value_column:
            continue
        if warning_threshold is None and critical_threshold is None:
            continue

        display = monitor.get("display", monitor.get("name", "unknown"))

        try:
            rows = await _execute_monitor_sql(instance, query_sql)
        except Exception:
            logger.debug("Monitor %r SQL failed for %s", display, instance.name, exc_info=True)
            continue

        for row in rows:
            value = None

            # Compute pass_rate when value_column signals a derived column
            if value_column == "pass_rate":
                total = row.get("total_checks", 0)
                passed = row.get("passed_checks", 0)
                if total > 0:
                    value = (passed / total) * 100.0
            else:
                value = row.get(value_column)

            name = row.get("name", row.get("id", "unknown"))
            if value is None:
                continue

            if critical_threshold is not None and value < critical_threshold:
                await create_notification(
                    db,
                    instance_id=instance.id,
                    severity="critical",
                    title=f"{display} '{name}' critical: {value:.0f}%",
                    body=(
                        f"{display} '{name}' score is {value:.1f}%, "
                        f"below the critical threshold of {critical_threshold}%. "
                        f"Immediate investigation recommended."
                    ),
                )
            elif warning_threshold is not None and value < warning_threshold:
                await create_notification(
                    db,
                    instance_id=instance.id,
                    severity="warning",
                    title=f"{display} '{name}' warning: {value:.0f}%",
                    body=(
                        f"{display} '{name}' score is {value:.1f}%, "
                        f"below the warning threshold of {warning_threshold}%. "
                        f"Consider reviewing."
                    ),
                )

    logger.debug("Health check complete for %s", instance.name)


async def check_data_freshness(db: AsyncSession, instance: Instance):
    """Check that data sources have received recent data.

    Reads monitors with max_age_hours from instance config.
    Filters stale rows in Python (hours_since_last > max_age_hours).
    """
    monitors = _load_monitors_config(instance)
    if not monitors:
        logger.debug("No cognition monitors for %s, skipping freshness check", instance.name)
        return

    for monitor in monitors:
        max_age_hours = monitor.get("max_age_hours")
        if max_age_hours is None:
            continue

        query_sql = monitor.get("query_sql")
        if not query_sql:
            continue

        display = monitor.get("display", monitor.get("name", "unknown"))

        try:
            rows = await _execute_monitor_sql(instance, query_sql)
        except Exception:
            logger.debug("Monitor %r SQL failed for %s", display, instance.name, exc_info=True)
            continue

        stale = [r for r in rows if r.get("hours_since_last", 0) > max_age_hours]

        for row in stale:
            hours = row.get("hours_since_last", 0)
            name = row.get("name", row.get("id", "unknown"))
            await create_notification(
                db,
                instance_id=instance.id,
                severity="warning",
                title=f"{display} '{name}' data is stale",
                body=(
                    f"{display} '{name}' has not received new records in {hours:.0f} hours "
                    f"(threshold: {max_age_hours}h). Last record at: "
                    f"{row.get('last_record_time', 'unknown')}."
                ),
            )

        if stale:
            logger.debug("Freshness check for %s: %d stale", instance.name, len(stale))


async def check_failed_jobs(db: AsyncSession, instance: Instance):
    """Check for failed jobs/operations in the recent window.

    Reads monitors with look_back_hours from instance config.
    The SQL in config already includes the time window filter.
    """
    monitors = _load_monitors_config(instance)
    if not monitors:
        logger.debug("No cognition monitors for %s, skipping error check", instance.name)
        return

    for monitor in monitors:
        look_back_hours = monitor.get("look_back_hours")
        if look_back_hours is None:
            continue

        query_sql = monitor.get("query_sql")
        if not query_sql:
            continue

        display = monitor.get("display", monitor.get("name", "unknown"))

        try:
            rows = await _execute_monitor_sql(instance, query_sql)
        except Exception:
            logger.debug("Monitor %r SQL failed for %s", display, instance.name, exc_info=True)
            continue

        if rows:
            await create_notification(
                db,
                instance_id=instance.id,
                severity="warning",
                title=f"{len(rows)} {display.lower()} in last {look_back_hours}h",
                body=(
                    f"Found {len(rows)} {display.lower()} in the last "
                    f"{look_back_hours} hours. Check configurations and data sources."
                ),
            )

    logger.debug("Error check complete for %s", instance.name)


async def check_schema_drift(db: AsyncSession, instance: Instance):
    """Detect if the host database schema has changed since last introspection."""
    import psycopg2

    from ai.engine.knowledge.store import KnowledgeStore

    known_tables = set()
    current_tables = set()

    # Get known tables from knowledge store
    store = KnowledgeStore(db)
    from sqlalchemy import select
    from ai.engine.core.models import KnowledgeEntity

    stmt = select(KnowledgeEntity.name).where(
        KnowledgeEntity.instance_id == instance.id,
        KnowledgeEntity.entity_type == "table",
    )
    result = await db.execute(stmt)
    known_tables = {row[0] for row in result.fetchall()}

    if not known_tables:
        logger.debug(f"No known tables for {instance.name}, skipping drift check")
        return

    # Get current tables from host DB
    def _query():
        conn = psycopg2.connect(instance.host_db_url)
        try:
            conn.set_session(readonly=True)
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
            for row in cur.fetchall():
                current_tables.add(row[0])
            cur.close()
        finally:
            conn.close()

    await asyncio.to_thread(_query)

    new_tables = current_tables - known_tables
    removed_tables = known_tables - current_tables

    if new_tables:
        await create_notification(
            db,
            instance_id=instance.id,
            severity="info",
            title=f"Schema drift: {len(new_tables)} new table(s) detected",
            body=(
                f"New tables found in host database: {', '.join(sorted(new_tables))}. "
                f"Consider re-running introspection to update knowledge."
            ),
        )

    if removed_tables:
        await create_notification(
            db,
            instance_id=instance.id,
            severity="warning",
            title=f"Schema drift: {len(removed_tables)} table(s) removed",
            body=(
                f"Tables no longer found in host database: {', '.join(sorted(removed_tables))}. "
                f"Knowledge may be outdated."
            ),
        )

    if new_tables or removed_tables:
        logger.info(
            f"Schema drift for {instance.name}: "
            f"+{len(new_tables)} new, -{len(removed_tables)} removed"
        )
