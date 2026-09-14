"""Phase H3-B — user-configured anomaly watch evaluation.

Runs alongside ``run_proactive_evaluation`` in the same proactive pass: loads
each enabled ``AIAnomalyWatch`` for an instance, measures the configured KPI
through the existing read-only host aggregation helper, and delivers an
``anomaly_watch`` insight when the threshold is crossed.

``kpi_expression`` is a natural-language LABEL — never evaluated. The
machine-evaluable ``condition`` spec (``table`` / ``column`` / ``operator`` /
``aggregation``) is executed exclusively through the existing identifier-quoted,
read-only ``_query_aggregation`` helper (psycopg2). No raw SQL is built here.

This is engine-layer code: it imports only ``ai.*`` — never ``accounts``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ai.engine.ports.watches import UserWatchStore

logger = logging.getLogger("pulse.proactive.user_watches")

_ALLOWED_OPERATORS = {"<", "<=", ">", ">=", "==", "!="}
_ALLOWED_AGGREGATIONS = {"latest", "avg", "max", "min", "count"}

# Host-injected adapter factory (constructed once in host code). The engine
# never imports ``ai.adapters``; callers wire it during bootstrap.
_watch_store_factory: Callable[[Any], UserWatchStore] | None = None


def set_user_watch_store_factory(factory: Callable[[Any], UserWatchStore]) -> None:
    """Inject the host's ``UserWatchStore`` adapter factory at bootstrap."""
    global _watch_store_factory
    _watch_store_factory = factory


async def run_user_watches(db, instance, watch_store: UserWatchStore | None = None, executor=None) -> dict:
    """Evaluate enabled user watches for ``instance`` and fire crossed ones."""
    instance_id = instance.id
    host_db_url = instance.host_db_url

    summary = {
        "instance_id": instance_id,
        "watches_evaluated": 0,
        "watches_fired": 0,
        "errors": [],
    }

    if watch_store is None:
        if _watch_store_factory is None:
            raise RuntimeError(
                "UserWatchStore adapter not injected; call "
                "ai.engine.proactive.user_watches.set_user_watch_store_factory() during bootstrap"
            )
        watch_store = _watch_store_factory(db)

    try:
        watches = await watch_store.list_enabled_watches(instance_id)
    except Exception as e:  # pragma: no cover - load failure is fail-visible
        logger.error(f"Failed to load anomaly watches for {instance_id}: {e}")
        summary["errors"].append(str(e))
        return summary

    for watch in watches:
        summary["watches_evaluated"] += 1
        try:
            cond = watch["condition"] or {}
            table = cond.get("table")
            column = cond.get("column")
            operator = cond.get("operator", ">")
            aggregation = cond.get("aggregation", "latest")

            if not isinstance(table, str) or not table.strip():
                logger.warning(f"Watch {watch['id']}: missing/invalid 'table' — skipping")
                continue
            if not isinstance(column, str) or not column.strip():
                logger.warning(f"Watch {watch['id']}: missing/invalid 'column' — skipping")
                continue
            if operator not in _ALLOWED_OPERATORS:
                logger.warning(
                    f"Watch {watch['id']}: invalid operator {operator!r} — skipping"
                )
                continue
            if aggregation not in _ALLOWED_AGGREGATIONS:
                logger.warning(
                    f"Watch {watch['id']}: invalid aggregation {aggregation!r} — skipping"
                )
                continue

            from ai.engine.proactive.trigger_evaluator import (
                _compare,
                _query_aggregation,
            )

            measured = await _query_aggregation(host_db_url, table, column, aggregation)
            if measured is None:
                continue

            if not _compare(measured, operator, watch["threshold"]):
                continue

            from ai.engine.proactive.delivery import deliver_insight

            _deliver_kwargs = {} if executor is None else {"executor": executor}
            await deliver_insight(
                db,
                instance_id,
                {
                    "insight_type": "anomaly_watch",
                    "severity": "warning",
                    "title": f"Watch fired: {watch['name']}",
                    "narrative": (
                        f"{watch['kpi_expression']} measured "
                        f"{measured} {operator} {watch['threshold']}"
                    ),
                    "context": {
                        "watch_id": watch["id"],
                        "measured": measured,
                        "threshold": watch["threshold"],
                    },
                },
                **_deliver_kwargs,
            )

            await watch_store.record_fire(watch["id"])

            summary["watches_fired"] += 1

        except Exception as e:
            logger.warning(f"Error evaluating watch {watch['id']}: {e}")
            summary["errors"].append(str(e))

    return summary
