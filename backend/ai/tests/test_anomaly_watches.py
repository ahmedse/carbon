"""Phase H3-B — user-configurable anomaly watches tests.

Covers:

* ``AIAnomalyWatch`` model create + field defaults.
* GET /ai/watches/ — own-watch scoping for non-admins; full scope for superusers.
* POST /ai/watches/ — 403 without ``ai:manage_console``; 201 for superuser;
  invalid ``condition`` (bad operator) → 400.
* PATCH/DELETE /{pk}/ — owner update; non-owner denial; superuser delete.
* ``run_user_watches`` — fires and records when the threshold is crossed; never
  raises on invalid/missing ``condition``.
"""

from __future__ import annotations

import asyncio
import types

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.models import AIAnomalyWatch


def _payload(**overrides):
    data = {
        "name": "winding temp",
        "kpi_expression": "winding temperature",
        "condition": {
            "table": "readings",
            "column": "temp",
            "operator": ">",
            "aggregation": "latest",
        },
        "threshold": 105.0,
        "instance_id": "carbon",
    }
    data.update(overrides)
    return data


# ── 1. Model ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_model_create_and_defaults():
    user = User.objects.create_user(username="owner", password="secret123")
    watch = AIAnomalyWatch.objects.create(
        user=user,
        instance_id="carbon",
        name="High temp",
        kpi_expression="winding temperature",
        condition={"table": "readings", "column": "temp"},
        threshold=105.0,
    )
    assert watch.enabled is True
    assert watch.fire_count == 0
    assert watch.comparison_window_days == 30
    assert watch.last_fired_at is None
    assert watch.condition == {"table": "readings", "column": "temp"}
    assert str(watch) == "High temp (carbon)"


# ── 2. GET list scoping ───────────────────────────────────────────────


@pytest.mark.django_db
def test_list_returns_own_watch_only():
    owner = User.objects.create_user(username="owner2", password="secret123")
    other = User.objects.create_user(username="other", password="secret123")
    AIAnomalyWatch.objects.create(
        user=owner, instance_id="carbon", name="mine", kpi_expression="x", threshold=1.0
    )
    AIAnomalyWatch.objects.create(
        user=other, instance_id="carbon", name="theirs", kpi_expression="y", threshold=2.0
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    resp = client.get(reverse("ai-watches-list"))
    assert resp.status_code == 200
    names = [r["name"] for r in resp.data["results"]]
    assert "mine" in names
    assert "theirs" not in names


@pytest.mark.django_db
def test_list_superuser_sees_all():
    admin = User.objects.create_superuser(username="admin", password="secret123")
    a = User.objects.create_user(username="a", password="secret123")
    b = User.objects.create_user(username="b", password="secret123")
    AIAnomalyWatch.objects.create(
        user=a, instance_id="carbon", name="wa", kpi_expression="x", threshold=1.0
    )
    AIAnomalyWatch.objects.create(
        user=b, instance_id="carbon", name="wb", kpi_expression="y", threshold=2.0
    )

    client = APIClient()
    client.force_authenticate(user=admin)
    resp = client.get(reverse("ai-watches-list"))
    assert resp.status_code == 200
    names = {r["name"] for r in resp.data["results"]}
    assert names == {"wa", "wb"}


# ── 3. POST ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_post_permission_and_create():
    plain = User.objects.create_user(username="plain", password="secret123")
    admin = User.objects.create_superuser(username="admin2", password="secret123")

    client = APIClient()
    client.force_authenticate(user=plain)
    resp = client.post(reverse("ai-watches-list"), _payload(), format="json")
    assert resp.status_code == 403

    client2 = APIClient()
    client2.force_authenticate(user=admin)
    resp2 = client2.post(reverse("ai-watches-list"), _payload(), format="json")
    assert resp2.status_code == 201
    assert resp2.data["name"] == "winding temp"
    assert resp2.data["enabled"] is True
    watch = AIAnomalyWatch.objects.get(pk=resp2.data["id"])
    assert watch.user_id == admin.pk


@pytest.mark.django_db
def test_post_rejects_invalid_condition():
    admin = User.objects.create_superuser(username="admin3", password="secret123")
    client = APIClient()
    client.force_authenticate(user=admin)
    resp = client.post(
        reverse("ai-watches-list"),
        _payload(condition={"table": "t", "column": "c", "operator": ">>"}),
        format="json",
    )
    assert resp.status_code == 400


# ── 4. PATCH / DELETE ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_patch_owner_and_deny_non_owner():
    owner = User.objects.create_user(username="owner3", password="secret123")
    other = User.objects.create_user(username="other2", password="secret123")
    watch = AIAnomalyWatch.objects.create(
        user=owner, instance_id="carbon", name="w", kpi_expression="k", threshold=1.0
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    resp = client.patch(
        reverse("ai-watch-detail", args=[watch.pk]), {"threshold": 5.0}, format="json"
    )
    assert resp.status_code == 200
    watch.refresh_from_db()
    assert watch.threshold == 5.0

    client2 = APIClient()
    client2.force_authenticate(user=other)
    resp2 = client2.patch(
        reverse("ai-watch-detail", args=[watch.pk]), {"threshold": 9.0}, format="json"
    )
    assert resp2.status_code in (403, 404)


@pytest.mark.django_db
def test_delete_superuser():
    admin = User.objects.create_superuser(username="admin4", password="secret123")
    owner = User.objects.create_user(username="owner4", password="secret123")
    watch = AIAnomalyWatch.objects.create(
        user=owner, instance_id="carbon", name="w", kpi_expression="k", threshold=1.0
    )

    client = APIClient()
    client.force_authenticate(user=admin)
    resp = client.delete(reverse("ai-watch-detail", args=[watch.pk]))
    assert resp.status_code == 204
    assert not AIAnomalyWatch.objects.filter(pk=watch.pk).exists()


# ── 5. run_user_watches ───────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_run_user_watches_fires_and_records(monkeypatch):
    from ai.engine.proactive.user_watches import run_user_watches

    user = User.objects.create_user(username="watch-owner", password="secret123")
    watch = AIAnomalyWatch.objects.create(
        user=user,
        instance_id="carbon",
        name="temp too high",
        kpi_expression="winding temperature",
        condition={
            "table": "readings",
            "column": "temp",
            "operator": ">",
            "aggregation": "latest",
        },
        threshold=100.0,
    )

    async def fake_query(host_db_url, table, column, aggregation, where_clause=""):
        return 150.0

    async def fake_deliver(db, instance_id, insight_data, trigger_id=None, group_id=None):
        return "insight-id"

    monkeypatch.setattr(
        "ai.engine.proactive.trigger_evaluator._query_aggregation", fake_query
    )
    monkeypatch.setattr("ai.engine.proactive.delivery.deliver_insight", fake_deliver)

    instance = types.SimpleNamespace(id="carbon", host_db_url="postgresql://x")
    result = asyncio.run(run_user_watches(None, instance))

    assert result["instance_id"] == "carbon"
    assert result["watches_evaluated"] == 1
    assert result["watches_fired"] == 1
    assert result["errors"] == []

    watch.refresh_from_db()
    assert watch.fire_count == 1
    assert watch.last_fired_at is not None


@pytest.mark.django_db(transaction=True)
def test_run_user_watches_survives_invalid_condition():
    from ai.engine.proactive.user_watches import run_user_watches

    user = User.objects.create_user(username="owner5", password="secret123")
    AIAnomalyWatch.objects.create(
        user=user,
        instance_id="carbon",
        name="missing column",
        kpi_expression="k",
        condition={"table": "readings"},
        threshold=1.0,
    )
    AIAnomalyWatch.objects.create(
        user=user,
        instance_id="carbon",
        name="no condition",
        kpi_expression="k",
        condition=None,
        threshold=1.0,
    )

    instance = types.SimpleNamespace(id="carbon", host_db_url="postgresql://x")
    result = asyncio.run(run_user_watches(None, instance))

    assert result["watches_evaluated"] == 2
    assert result["watches_fired"] == 0
    assert result["errors"] == []
