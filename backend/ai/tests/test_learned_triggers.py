"""Pulse 0.2 Phase A5 — dead-subsystem resolution tests.

Path 1 (performance drift): ``detect_performance_drift`` is deprecated and no
longer on the scheduled proactive path — ``run_drift_detection`` is removed.

Path 2 (learned triggers): the ``system_snapshots:<field>`` seeding branch and
its ``trigger_learning`` job wiring are removed; ``analyze_snapshots`` (the
kept analysis path) remains intact.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from django.test import override_settings

from ai.store import reset_store


@pytest.fixture
def django_store():
    """Run the engine against the Django (PostgreSQL) Store backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


# ── Path 1: performance drift ─────────────────────────────────────────────


def test_run_drift_detection_is_removed():
    """The scheduled invocation of ``detect_performance_drift`` is gone."""
    from ai.engine.proactive import loop

    assert not hasattr(loop, "run_drift_detection")


def test_detect_performance_drift_is_importable_but_deprecated():
    """The function is kept importable and marked deprecated/experimental."""
    from ai.engine.proactive.insight_generator import detect_performance_drift

    assert callable(detect_performance_drift)
    assert "DEPRECATED" in (detect_performance_drift.__doc__ or "")


# ── Path 2: learned triggers ──────────────────────────────────────────────


def test_seed_learned_triggers_is_removed():
    """The dead seeding branch is gone from the module."""
    from ai.engine.cognition import learned_triggers

    assert not hasattr(learned_triggers, "seed_learned_triggers")


@pytest.mark.django_db(transaction=True)
def test_trigger_learning_task_is_not_registered(django_store):
    """The trigger-learning job is no longer a schedulable cognition task."""
    from ai.engine.cognition.loop import trigger_task

    result = asyncio.run(trigger_task("trigger_learning"))

    assert result["error"] == "Unknown task: trigger_learning"
    assert "trigger_learning" not in result["available"]


@pytest.mark.django_db(transaction=True)
def test_analyze_snapshots_emits_trend_for_flat_history(django_store):
    """The kept analysis path reads real snapshots and emits a trend candidate.

    Eight snapshots with a constant ``heat_rate`` are order-independent (all
    values equal), so the trend detector deterministically emits exactly one
    ``increasing`` trend candidate.
    """
    from ai.engine.core.models import SystemSnapshot
    from ai.engine.cognition.learned_triggers import analyze_snapshots
    from ai.store import get_store

    async def _run():
        factory = get_store().get_session_factory()
        async with factory() as db:
            for _ in range(8):
                db.add(SystemSnapshot(
                    instance_id="phase-a5-flat",
                    snapshot_data=json.dumps({"heat_rate": 100}),
                ))
            await db.commit()
            return await analyze_snapshots(db, "phase-a5-flat")

    result = asyncio.run(_run())

    assert len(result) == 1
    assert result[0]["condition_type"] == "trend"
    assert result[0]["field"] == "heat_rate"
    assert result[0]["direction"] == "increasing"
