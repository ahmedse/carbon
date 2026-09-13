"""P1-14 — capability health tests (``ai.health.capability_health`` + endpoint).

Tests:
  * capability_health() returns all five capabilities with valid statuses
  * store is "healthy" under the durable ``django`` backend (test DB)
  * mcp is "disabled" when ``MCP_SERVERS`` is empty (default)
  * verify is "configured" when ``PULSE_VERIFY_ENABLED`` is on (default)
  * reason_lane is "configured" (dedicated or fallback)
  * mcp reports "degraded" on malformed JSON (monkeypatched engine settings)
  * GET /carbon-api/ai/pulse/health/ carries a ``capabilities`` object
"""
import pytest

from ai.health import _STATUSES, capability_health

BASE = "/carbon-api/ai/pulse"


@pytest.fixture
def user(db):
    from accounts.models import User

    user = User.objects.create_user(username="ai-health", password="secret123")
    user.is_superuser = True
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def auth_client(api_client, get_token_for_user, user):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


# ── capability_health() ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_capability_health_returns_all_five():
    caps = capability_health()
    assert set(caps) == {"store", "reason_lane", "verify", "mcp", "sandbox"}
    for key, entry in caps.items():
        assert entry["status"] in _STATUSES, f"{key} has invalid status {entry['status']!r}"
        assert "detail" in entry


@pytest.mark.django_db
def test_store_is_healthy_under_django_backend():
    from django.conf import settings

    assert settings.AI_STORE_BACKEND == "django"
    assert capability_health()["store"]["status"] == "healthy"


def test_mcp_disabled_when_no_servers():
    assert capability_health()["mcp"]["status"] == "disabled"


def test_verify_configured_when_enabled():
    caps = capability_health()
    assert caps["verify"]["status"] == "configured"
    assert caps["verify"]["enabled"] is True


def test_reason_lane_configured():
    assert capability_health()["reason_lane"]["status"] == "configured"


def test_mcp_degraded_on_malformed_json(monkeypatch):
    from ai.engine.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MCP_SERVERS", "{not valid json")
    assert capability_health()["mcp"]["status"] == "degraded"


# ── Endpoint ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_health_endpoint_carries_capabilities(auth_client):
    resp = auth_client.get(f"{BASE}/health/")
    assert resp.status_code == 200
    caps = resp.json().get("capabilities")
    assert isinstance(caps, dict)
    assert set(caps) == {"store", "reason_lane", "verify", "mcp", "sandbox"}
    for entry in caps.values():
        assert entry["status"] in _STATUSES
