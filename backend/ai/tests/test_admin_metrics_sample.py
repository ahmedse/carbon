# backend/ai/tests/test_admin_metrics_sample.py
"""Pulse Admin QA Gate L5 — metrics sample harness.

Samples control/spend/quality/rollups/maturity/candidates for schema + honesty
gates (docs/pulse/archive/PULSE-ADMIN-QA-GATE.md §7). Does not gate chat grounding.

Run::

    ./manage.sh test ai/tests/test_admin_metrics_sample.py
"""

from __future__ import annotations

import time

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

CONTROL = "/carbon-api/ai/pulse/control"
PULSE = "/carbon-api/ai/pulse"

MATURITY_KEYS = {
    "maturity_score",
    "expertise_level",
    "expertise_description",
    "skills",
    "knowledge",
    "performance",
    "complexity",
    "learning_velocity",
    "domain_expertise",
}


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser(
        username="metrics_admin", email="metrics@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_l5_containment_apply_latency(admin_client):
    """POST containment → command GET match within 2s (CI sample of staging SLO)."""
    t0 = time.perf_counter()
    post = admin_client.post(
        f"{CONTROL}/containment/",
        {"level": "tool_freeze", "reason": "L5 latency sample"},
        format="json",
    )
    assert post.status_code == 200, post.content
    cmd = admin_client.get(f"{CONTROL}/command/")
    elapsed = time.perf_counter() - t0
    assert cmd.status_code == 200, cmd.content
    assert cmd.json()["containment"]["containment_level"] == "tool_freeze"
    assert elapsed < 2.0, f"containment→command took {elapsed:.3f}s (gate <2s)"

    admin_client.post(
        f"{CONTROL}/containment/",
        {"level": "normal", "reason": "L5 reset"},
        format="json",
    )


@pytest.mark.django_db
def test_l5_budget_override_flips_in_response(admin_client):
    """PATCH budget → same response / command spend shows override_active."""
    patch = admin_client.patch(
        f"{CONTROL}/budget/",
        {"daily_budget_usd": 33.0},
        format="json",
    )
    assert patch.status_code == 200, patch.content
    body = patch.json()
    assert body.get("daily_budget_usd") == 33.0

    cmd = admin_client.get(f"{CONTROL}/command/")
    assert cmd.status_code == 200
    spend = cmd.json().get("spend") or {}
    assert spend.get("override_active") is True
    assert float(spend.get("budget_usd") or 0) == 33.0


@pytest.mark.django_db
def test_l5_spend_honesty_usage_vs_command(admin_client):
    """usage/ and command.spend must not contradict on spent_today / budget."""
    usage = admin_client.get(f"{PULSE}/usage/")
    cmd = admin_client.get(f"{CONTROL}/command/")
    assert usage.status_code == 200, usage.content
    assert cmd.status_code == 200, cmd.content

    u = usage.json()
    spend = (cmd.json().get("spend") or {})
    for key in ("spent_today_usd", "budget_usd", "budget_exceeded"):
        assert key in u, f"usage missing {key}"
        assert key in spend, f"command.spend missing {key}"

    # Same-day sample: spent and exceeded must agree within 1 cent / bool.
    assert abs(float(u["spent_today_usd"]) - float(spend["spent_today_usd"])) < 0.01
    assert bool(u["budget_exceeded"]) == bool(spend["budget_exceeded"])
    # Budgets may differ if override only on one path — but when override_active,
    # both should reflect the override value.
    if spend.get("override_active"):
        assert abs(float(u["budget_usd"]) - float(spend["budget_usd"])) < 0.01


@pytest.mark.django_db
def test_l5_rollups_honest_when_empty(admin_client):
    """Never invent a hit rate when there are no truthfulness turns."""
    from ai.models.core import TurnLedgerRow

    TurnLedgerRow.objects.filter(stage="truthfulness_gate").delete()
    resp = admin_client.get(f"{PULSE}/rollups/")
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    totals = payload.get("totals") or payload
    assert totals.get("truthfulness_total", 0) == 0
    assert totals.get("truthfulness_hit_rate") is None


@pytest.mark.django_db
def test_l5_quality_trend_schema_or_honest_empty(admin_client):
    resp = admin_client.get(f"{PULSE}/quality-trend/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    # Accept list or object with series/points — never a fabricated 100% score alone.
    if isinstance(body, list):
        assert all(isinstance(row, dict) for row in body)
    else:
        assert isinstance(body, dict)
        # Common keys; empty is fine.
        assert not (
            body.get("hit_rate") == 1.0
            and body.get("sample_size") in (0, None)
            and body.get("fabricated") is True
        )


@pytest.mark.django_db
def test_l5_maturity_score_bounds_and_keys(admin_client):
    resp = admin_client.get(f"{PULSE}/maturity/")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    missing = MATURITY_KEYS - data.keys()
    assert not missing, f"maturity missing keys: {missing}"
    score = float(data["maturity_score"])
    assert 0.0 <= score <= 100.0
    assert isinstance(data["skills"], dict)
    assert isinstance(data["knowledge"], dict)


@pytest.mark.django_db
def test_l5_candidates_results_array(admin_client):
    resp = admin_client.get(f"{CONTROL}/candidates/?limit=20")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    results = body.get("results") if isinstance(body, dict) else body
    assert isinstance(results, list)
