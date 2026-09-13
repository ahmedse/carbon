"""DjangoWatchAdapter — host implementation of the UserWatchStore port.

Lists enabled :class:`ai.models.core.AIAnomalyWatch` rows for an instance and
records fires.  Watches are instance-scoped configuration evaluated by the
proactive pass with no user context, so ``list_enabled_watches`` returns every
enabled watch for the instance (no visibility predicate) — exactly the
pre-migration ``AIAnomalyWatch.objects.filter(enabled=True, instance_id=…)``
behavior.  ``record_fire`` is a pk-addressed update (the watch id is globally
unique, so no instance predicate is available or needed).

The adapter reads/writes through the Django ORM directly (``objects``) rather
than a Store session: the proactive pass may invoke ``run_user_watches`` with
``db=None``, so a session must not be required here.

RULE_20: imports only ``ai.*``, Django, and the stdlib.
"""
from __future__ import annotations

from typing import Any

from django.utils import timezone

from ai.engine.ports.watches import WatchRecord
from ai.models.core import AIAnomalyWatch


def _watch_to_record(watch: AIAnomalyWatch) -> WatchRecord:
    return {
        "id": watch.id,
        "instance_id": watch.instance_id,
        "name": watch.name,
        "kpi_expression": watch.kpi_expression,
        "condition": watch.condition or {},
        "threshold": watch.threshold,
        "enabled": watch.enabled,
        "last_fired_at": watch.last_fired_at,
        "fire_count": watch.fire_count or 0,
    }


class DjangoWatchAdapter:
    """User-watch adapter implementing ``ai.engine.ports.watches.UserWatchStore``."""

    def __init__(self, db: Any = None) -> None:
        # ``db`` is retained for interface symmetry with the other host
        # adapters, but watch I/O goes through the Django ORM directly so the
        # adapter still works when the proactive pass supplies ``db=None``.
        self.db = db

    async def list_enabled_watches(self, instance_id: str) -> list[WatchRecord]:
        from asgiref.sync import sync_to_async

        def _run() -> list[AIAnomalyWatch]:
            return list(
                AIAnomalyWatch.objects.filter(enabled=True, instance_id=instance_id)
            )

        rows = await sync_to_async(_run, thread_sensitive=True)()
        return [_watch_to_record(w) for w in rows]

    async def record_fire(self, watch_id: str) -> WatchRecord | None:
        from asgiref.sync import sync_to_async

        def _run() -> WatchRecord | None:
            try:
                watch = AIAnomalyWatch.objects.get(pk=watch_id)
            except AIAnomalyWatch.DoesNotExist:
                return None
            watch.fire_count = (watch.fire_count or 0) + 1
            watch.last_fired_at = timezone.now()
            watch.save(update_fields=["last_fired_at", "fire_count"])
            return _watch_to_record(watch)

        return await sync_to_async(_run, thread_sensitive=True)()
