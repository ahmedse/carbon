"""Phase D — cognition scheduler activation tests (TASKS-PULSE-VENDOR-PHASE-D).

Tests:
  * ``_for_each_instance`` iterates active instances via the Django Store
    (inactive instances excluded).
  * ``trigger_task("health_check")`` returns ``status: ok`` and writes a
    durable ``CognitionSweepRun`` row (no live LLM).
  * ``trigger_task("bogus")`` returns the ``{error, available}`` envelope
    (fail-visible — never a 500/exception).
  * ``CognitionSweepRun`` upsert: running ``_tracked`` twice for one task
    increments ``run_count`` and updates ``last_run`` (one row, not two).
  * ``sweeps/`` endpoint: 200 with ``tasks`` list for auth users; 401
    anonymous; 405 for POST (structural read-only).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store

BASE = "/carbon-api/ai/pulse"


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    """Run the engine against the Django (PostgreSQL) Store backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    """Clear the settings cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def user(db):
    from accounts.models import User

    user = User.objects.create_user(username="ai-sweeps", password="secret123")
    user.is_superuser = True
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def auth_client(api_client, get_token_for_user, user):
    """DRF client authenticated with a real JWT (mirrors conftest pattern)."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


# ── _for_each_instance ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_for_each_instance_iterates_active_instances(django_store, cfg):
    """Active instances are visited; inactive ones are not."""
    from ai.engine.cognition.loop import _for_each_instance
    from ai.models.core import Instance
    from ai.store import get_store

    active_a = f"sweep-active-{uuid4().hex[:8]}"
    active_b = f"sweep-active-{uuid4().hex[:8]}"
    paused = f"sweep-paused-{uuid4().hex[:8]}"

    # Seed via the Store so the rows commit on the same (sync) connection the
    # engine reads from — test-thread ORM writes are in an uncommitted
    # transaction the worker thread cannot see.
    async def _seed():
        factory = get_store().get_session_factory()
        async with factory() as db:
            for name, status in (
                (active_a, "active"),
                (active_b, "active"),
                (paused, "paused"),
            ):
                db.add(
                    Instance(
                        name=name,
                        display_name=name,
                        host_db_url="postgres://db",
                        host_api_url="https://host",
                        status=status,
                    )
                )
            await db.commit()

    asyncio.run(_seed())

    seen: list[str] = []

    async def _cb(db, instance):
        seen.append(instance.name)

    asyncio.run(_for_each_instance(_cb))

    assert active_a in seen
    assert active_b in seen
    assert paused not in seen


# ── run-once ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_run_once_health_check_writes_sweep_run(django_store, cfg):
    """health_check returns ok and writes a durable CognitionSweepRun row."""
    from ai.engine.cognition.loop import trigger_task
    from ai.models.core import CognitionSweepRun
    from ai.store import get_store

    # Clean any leaked row from a prior --reuse-db run (fixed task name).
    async def _cleanup():
        factory = get_store().get_session_factory()
        async with factory() as db:
            for row in await db.select(CognitionSweepRun, ("task_name", "health_check")):
                await db.delete(row)
            await db.commit()

    asyncio.run(_cleanup())

    result = asyncio.run(trigger_task("health_check"))

    assert result["status"] == "ok"
    assert result["task"] == "health_check"

    rows = list(CognitionSweepRun.objects.filter(task_name="health_check"))
    assert len(rows) == 1
    assert rows[0].run_count == 1
    assert rows[0].last_status == "ok"
    assert rows[0].last_run is not None
    assert rows[0].last_error is None


@pytest.mark.django_db
def test_run_once_unknown_task_is_fail_visible(django_store, cfg):
    """Unknown task returns the {error, available} envelope — not an exception."""
    from ai.engine.cognition.loop import trigger_task

    result = asyncio.run(trigger_task("bogus"))

    assert result["error"] == "Unknown task: bogus"
    assert "available" in result
    assert "health_check" in result["available"]


# ── CognitionSweepRun upsert ─────────────────────────────────────────────


@pytest.mark.django_db
def test_tracked_upserts_single_row(django_store, cfg):
    """Running _tracked twice for one task yields one row with run_count=2."""
    from ai.engine.cognition.loop import _tracked
    from ai.models.core import CognitionSweepRun

    task = f"upsert-probe-{uuid4().hex[:8]}"

    async def _noop():
        return None

    asyncio.run(_tracked(task, _noop))
    asyncio.run(_tracked(task, _noop))

    rows = list(CognitionSweepRun.objects.filter(task_name=task))
    assert len(rows) == 1
    assert rows[0].run_count == 2
    assert rows[0].last_run is not None
    assert rows[0].last_status == "ok"


# ── sweeps/ endpoint ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sweeps_endpoint_returns_tasks(auth_client):
    resp = auth_client.get(f"{BASE}/sweeps/")
    assert resp.status_code == 200
    body = resp.json()
    assert "scheduler_running" in body
    assert isinstance(body["tasks"], list)
    assert "live" in body


@pytest.mark.django_db
def test_sweeps_endpoint_lists_seeded_runs(auth_client):
    from ai.models.core import CognitionSweepRun
    from django.utils import timezone

    task = f"seeded-{uuid4().hex[:8]}"
    CognitionSweepRun.objects.create(
        task_name=task,
        last_run=timezone.now(),
        last_status="ok",
        last_duration_ms=12,
        run_count=3,
    )
    resp = auth_client.get(f"{BASE}/sweeps/")
    assert resp.status_code == 200
    tasks = {t["task_name"]: t for t in resp.json()["tasks"]}
    assert task in tasks
    assert tasks[task]["run_count"] == 3
    assert tasks[task]["last_status"] == "ok"
    assert tasks[task]["last_duration_ms"] == 12


@pytest.mark.django_db
def test_sweeps_endpoint_requires_auth(api_client):
    assert api_client.get(f"{BASE}/sweeps/").status_code == 401


@pytest.mark.django_db
def test_sweeps_endpoint_rejects_post(auth_client):
    assert auth_client.post(f"{BASE}/sweeps/", {}).status_code == 405
