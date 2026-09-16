"""Pulse 0.2 Phase A3 + PEC-3A — proactive insights SSE/read-layer API tests.

Covers:
  * list endpoint returns only CBAC-visible insights
  * disposition POST updates disposition, stores reason, 404s out-of-scope
  * the pure scope filter (``_frame_visible``) admits/rejects frames
  * delivery ``_push_websocket`` publishes an OUTCOME-shaped bus frame
  * PEC-3A: deliver → persist → list exposes honest confidence + provenance
  * PEC-3A: info/digest severity still publishes to the bus (SSE contract)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

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


_OUTCOME_KEYS = {
    "id",
    "title",
    "narrative",
    "severity",
    "insight_type",
    "recommended_actions",
    "context",
    "confidence",
    "confidence_label",
    "provenance",
    "disposition",
    "created_at",
}


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
        app_identifier="carbon",
        context_json={
            "confidence": 0.8,
            "confidence_label": "high",
            "provenance": {
                "sources": [{"label": "Live reading", "detail": "value=12"}],
                "basis": "Based on live readings and recent alerts",
            },
            "measured": {"value": 12},
        },
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
        app_identifier="carbon",
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
    assert set(result.keys()) == _OUTCOME_KEYS
    assert result["confidence"] == 0.8
    assert result["confidence_label"] == "high"
    assert result["provenance"]["sources"][0]["label"] == "Live reading"
    assert "trigger_id" not in result
    assert "delivery_channel" not in result
    assert "confidence" not in result["context"]
    assert "provenance" not in result["context"]


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
        app_identifier="carbon",
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
        app_identifier="carbon",
    )

    url = reverse("ai-insight-disposition", kwargs={"pk": str(insight.id)})
    resp = api_client.post(url, {"disposition": "acted_on"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["disposition"] == "acted_on"
    assert set(resp.json().keys()) == _OUTCOME_KEYS
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
        app_identifier="carbon",
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
        context_json=json.dumps(
            {
                "measured": {"value": 91, "unit": "%"},
                "confidence": 0.8,
                "confidence_label": "high",
                "provenance": {
                    "sources": [
                        {"label": "Live reading", "detail": "value=91, unit=%"}
                    ],
                    "basis": "Based on live readings and recent alerts",
                },
            }
        ),
        recommended_actions_json=json.dumps(["add capacity"]),
        disposition="pending",
        visibility="shared",
        app_identifier="carbon",
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
    assert payload["context"] == {"measured": {"value": 91, "unit": "%"}}
    assert payload["confidence"] == 0.8
    assert payload["confidence_label"] == "high"
    assert payload["provenance"]["sources"][0]["label"] == "Live reading"
    assert payload["disposition"] == "pending"
    assert payload["visibility"] == "shared"
    assert payload["org_unit_id"] is None
    assert payload["host_user_id"] is None
    assert payload["app_identifier"] == "carbon"

    # RULE_23: no engine jargon leaks through the bus frame.
    assert "trigger_id" not in payload
    assert "delivery_channel" not in payload
    assert "instance_id" not in payload


# ── 5. PEC-3A — deliver → list with honest confidence + provenance ───────


@pytest.mark.django_db
def test_deliver_insight_reaches_list_with_provenance(user, api_client):
    """Proactive outcome shape persists and is visible via the list API.

    Uses the same ``build_outcome_fields`` path ``deliver_insight`` writes, then
    a Django ORM row (transaction-safe — avoids DjangoStore cross-connection
    commits that pollute ``--reuse-db`` siblings).
    """
    from ai.engine.proactive.delivery import build_outcome_fields

    insight_data = {
        "insight_type": "threshold_alert",
        "severity": "warning",
        "title": "Payroll run 12 has an unresolved variance",
        "narrative": (
            "Run 12 still shows an unresolved variance against the "
            "posted ledger — review before close."
        ),
        "recommended_actions": ["Open payroll run 12", "Resolve variance"],
        "context": {
            "measured_data": {
                "value": 1250.0,
                "metric": "variance_amount",
                "unit": "KWD",
            },
            "related_alerts": [{"title": "prior variance"}],
            "trigger_summary": "INTERNAL — must not leak",
            "sql": "SELECT 1 — must not leak",
        },
        "app_identifier": "carbon",
    }
    outcome = build_outcome_fields(insight_data)
    row = KgProactiveInsight.objects.create(
        instance_id="carbon",
        title=insight_data["title"],
        narrative=insight_data["narrative"],
        severity="warning",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="shared",
        app_identifier="carbon",
        recommended_actions_json=insight_data["recommended_actions"],
        context_json=outcome["context"],
        trigger_id="trig-internal",
        delivery_channel="websocket",
    )

    resp = api_client.get(reverse("ai-insights-list"))
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) >= 1
    result = next(r for r in results if r["id"] == str(row.id))

    assert result["title"] == "Payroll run 12 has an unresolved variance"
    assert set(result.keys()) == _OUTCOME_KEYS
    assert result["confidence"] == 0.8
    assert result["confidence_label"] == "high"
    assert result["provenance"]["basis"].startswith("Based on live readings")
    labels = [s["label"] for s in result["provenance"]["sources"]]
    assert "Live reading" in labels
    assert "Recent alerts" in labels

    # RULE_23: no engine jargon on the wire.
    blob = json.dumps(result)
    for banned in (
        "trigger_id",
        "delivery_channel",
        "trig-internal",
        "trigger_summary",
        "SELECT 1",
        "KG_PROACTIVE",
        "witness",
        "salience",
    ):
        assert banned not in blob

    assert "trigger_summary" not in result["context"]
    assert "sql" not in result["context"]
    assert result["context"].get("measured", {}).get("metric") == "variance_amount"


def test_deliver_insight_persists_outcome_and_publishes(monkeypatch):
    """deliver_insight stamps confidence/provenance and always publishes."""
    from ai.engine.proactive import delivery

    added = []
    committed = {"n": 0}
    captured = {}

    class _FakeDB:
        def add(self, obj):
            added.append(obj)

        async def commit(self):
            committed["n"] += 1

    async def _fake_publish(channel, frame):
        captured["frame"] = frame

    monkeypatch.setattr(delivery, "publish", _fake_publish)

    async def _run():
        return await delivery.deliver_insight(
            _FakeDB(),
            "carbon",
            {
                "insight_type": "threshold_alert",
                "severity": "info",  # digest channel — must still bus-publish
                "title": "Quiet check",
                "narrative": "Nothing urgent",
                "context": {"measured_data": {"value": 1, "metric": "x"}},
                "app_identifier": "carbon",
            },
            trigger_id="trig-hidden",
        )

    insight_id = asyncio.run(_run())
    assert insight_id
    assert committed["n"] >= 1
    assert len(added) == 1
    insight = added[0]
    assert insight.visibility == "shared"
    assert insight.app_identifier == "carbon"
    ctx = json.loads(insight.context_json)
    # info + measured → severity prior 0.60 (medium); not amplified.
    assert ctx["confidence"] == 0.6
    assert ctx["confidence_label"] == "medium"
    assert "provenance" in ctx
    assert "trigger_summary" not in ctx
    assert captured["frame"]["event_type"] == "insight.new"
    assert captured["frame"]["payload"]["confidence"] == 0.6
    assert "trig-hidden" not in json.dumps(captured["frame"]["payload"])


def test_build_outcome_fields_degrades_without_measured_data():
    """Honest uncertainty: no live reading → confidence capped below high."""
    from ai.engine.proactive.delivery import build_outcome_fields

    outcome = build_outcome_fields(
        {
            "severity": "critical",
            "insight_type": "threshold_alert",
            "context": {},
        }
    )
    assert outcome["confidence"] <= 0.55
    assert outcome["confidence_label"] in {"medium", "low", "uncertain"}
    assert outcome["provenance"]["basis"].startswith("Best available")


def test_info_severity_still_publishes_bus_frame(monkeypatch):
    """PEC-3A gap fix: digest/info insights must reach SSE via the bus."""
    from ai.engine.knowledge_graph.models import KgProactiveInsight as EngineInsight
    from ai.engine.proactive import delivery

    insight = EngineInsight(
        id="info-1",
        instance_id="carbon",
        insight_type="daily_briefing",
        severity="info",
        title="Daily Briefing",
        narrative="Quiet day",
        context_json=json.dumps(
            delivery.build_outcome_fields(
                {
                    "severity": "info",
                    "insight_type": "daily_briefing",
                    "context": {"notification_count": 2},
                }
            )["context"]
        ),
        recommended_actions_json="[]",
        disposition="pending",
        visibility="shared",
        app_identifier="carbon",
        delivery_channel="digest",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    captured = {}

    async def _fake_publish(channel, frame):
        captured["frame"] = frame

    async def _fake_notification(*args, **kwargs):
        return None

    monkeypatch.setattr(delivery, "publish", _fake_publish)
    monkeypatch.setattr(delivery, "_create_notification", _fake_notification)

    db = SimpleNamespace()

    async def _run():
        await delivery._deliver(
            db, "carbon", insight, {"title": "Daily Briefing"}, "info", "digest"
        )

    asyncio.run(_run())
    assert captured["frame"]["event_type"] == "insight.new"
    assert captured["frame"]["payload"]["severity"] == "info"
    assert "confidence" in captured["frame"]["payload"]
    assert "provenance" in captured["frame"]["payload"]
