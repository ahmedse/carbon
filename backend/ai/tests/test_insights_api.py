"""Pulse 0.2 Phase A3 — proactive insights SSE/read-layer API tests.

Covers:
  * list endpoint returns only CBAC-visible insights
  * disposition POST updates disposition, stores reason, 404s out-of-scope
  * the pure scope filter (``_frame_visible``) admits/rejects frames
  * delivery ``_push_websocket`` publishes an OUTCOME-shaped bus frame
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.insights_api import _frame_visible
from ai.models import KgProactiveInsight


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="insights-worker", password="secret123")


@pytest.fixture
def api_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── 1. list endpoint (CBAC scoping) ──────────────────────────────────────


@pytest.mark.django_db
def test_list_returns_only_visible_insights(user, api_client):
    KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Shared insight",
        narrative="visible",
        severity="warning",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="shared",
    )
    KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Private other",
        narrative="hidden",
        severity="critical",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="private",
        host_user_id="99999",
    )

    resp = api_client.get(reverse("ai-insights-list"))

    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"count", "next", "previous", "results"}
    assert data["count"] == 1
    titles = [r["title"] for r in data["results"]]
    assert "Shared insight" in titles
    assert "Private other" not in titles

    result = data["results"][0]
    assert set(result.keys()) == {
        "id", "title", "narrative", "severity", "insight_type",
        "recommended_actions", "context", "disposition", "created_at",
    }


# ── 2. disposition POST ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_disposition_updates_and_404s_out_of_scope(user, api_client):
    insight = KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Act on me",
        narrative="n",
        severity="info",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="shared",
    )
    private = KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Hidden",
        narrative="n",
        severity="info",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="private",
        host_user_id="99999",
    )

    url = reverse("ai-insight-disposition", kwargs={"pk": str(insight.id)})
    resp = api_client.post(url, {"disposition": "acted_on"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["disposition"] == "acted_on"
    insight.refresh_from_db()
    assert insight.disposition == "acted_on"

    # Out-of-scope id → 404.
    hidden_url = reverse("ai-insight-disposition", kwargs={"pk": str(private.id)})
    resp = api_client.post(hidden_url, {"disposition": "read"}, format="json")
    assert resp.status_code == 404
    assert "detail" in resp.json()

    # Invalid disposition → 400.
    resp = api_client.post(url, {"disposition": "banana"}, format="json")
    assert resp.status_code == 400
    assert "detail" in resp.json()


@pytest.mark.django_db
def test_disposition_dismissed_stores_reason(user, api_client):
    insight = KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Dismiss me",
        narrative="n",
        severity="info",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="shared",
    )

    url = reverse("ai-insight-disposition", kwargs={"pk": str(insight.id)})
    resp = api_client.post(
        url, {"disposition": "dismissed", "reason": "not relevant"}, format="json"
    )

    assert resp.status_code == 200
    assert resp.json()["disposition"] == "dismissed"
    insight.refresh_from_db()
    assert insight.disposition == "dismissed"
    assert insight.dismissed_reason == "not relevant"


# ── 3. pure scope filter ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_frame_visible_scope_filter(user):
    uid = str(user.id)
    base = {"org_unit_id": None, "app_identifier": "carbon"}

    assert _frame_visible(user, {**base, "visibility": "shared", "host_user_id": None})
    assert _frame_visible(user, {**base, "visibility": "global", "host_user_id": None})
    assert _frame_visible(user, {**base, "visibility": "private", "host_user_id": uid})
    assert not _frame_visible(user, {**base, "visibility": "private", "host_user_id": "99999"})
    assert not _frame_visible(user, {**base, "visibility": "shared", "app_identifier": "other"})


# ── 3b. SSE stream content negotiation (regression: 406 Not Acceptable) ──


@pytest.mark.django_db
def test_stream_accepts_event_stream_media_type(user, api_client):
    """The SSE stream must serve on ``Accept: text/event-stream`` (not 406).

    DRF's default content negotiation raises NotAcceptable when no renderer
    matches the browser's SSE Accept header. The view returns a raw
    StreamingHttpResponse and must ignore client Accept negotiation.
    """
    resp = api_client.get(
        reverse("ai-insights-stream"),
        HTTP_ACCEPT="text/event-stream",
    )
    # Never read ``resp.content`` — the body is an infinite event stream.
    assert resp.status_code == 200
    assert resp.get("Content-Type", "").startswith("text/event-stream")
    assert resp.streaming


# ── 4. delivery publishes an OUTCOME-shaped bus frame ────────────────────


def test_push_websocket_publishes_bus_frame(monkeypatch):
    from ai.engine.knowledge_graph.models import KgProactiveInsight as EngineInsight
    from ai.engine.proactive import delivery

    insight = EngineInsight(
        id="insight-1",
        instance_id="carbon",
        insight_type="threshold_alert",
        severity="warning",
        title="Disk near capacity",
        narrative="Disk usage exceeded 90%",
        context_json=json.dumps({"table": "x"}),
        recommended_actions_json=json.dumps(["add capacity"]),
        disposition="pending",
        visibility="shared",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    captured = {}

    async def _fake_publish(channel, frame):
        captured["channel"] = channel
        captured["frame"] = frame

    monkeypatch.setattr(delivery, "publish", _fake_publish)

    asyncio.run(delivery._push_websocket(None, "carbon", insight))

    assert captured["frame"]["event_type"] == "insight.new"
    assert captured["frame"]["instance_id"] == "carbon"

    payload = captured["frame"]["payload"]
    assert payload["id"] == "insight-1"
    assert payload["title"] == "Disk near capacity"
    assert payload["narrative"] == "Disk usage exceeded 90%"
    assert payload["severity"] == "warning"
    assert payload["insight_type"] == "threshold_alert"
    assert payload["recommended_actions"] == ["add capacity"]
    assert payload["context"] == {"table": "x"}
    assert payload["disposition"] == "pending"
    assert payload["visibility"] == "shared"
    assert payload["org_unit_id"] is None
    assert payload["host_user_id"] is None
    assert payload["app_identifier"] == "carbon"

    # RULE_23: no engine jargon leaks through the bus frame.
    assert "trigger_id" not in payload
    assert "delivery_channel" not in payload
    assert "instance_id" not in payload
