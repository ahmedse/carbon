"""Phase 2c — Pulse ops read API tests (TASKS-PULSE-VENDOR-PHASE-2C-OPS-API).

Tests:
  * health/ returns 200 with healthy=True and dq.validate/chat advertised
  * modules/ returns 200 with count == 12, every type in engine_runtime.MODULES
  * tasks/{unknown}/ is fail-visible (200, pulse_unavailable / not_found)
  * all three endpoints require auth (anonymous GET -> 401)
  * health/ rejects write methods with 405 (structural read-only)
"""
import pytest

from ai import engine_runtime

BASE = "/carbon-api/ai/pulse"


@pytest.fixture
def user(db):
    from accounts.models import User

    user = User.objects.create_user(username="ai-ops", password="secret123")
    user.is_superuser = True
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def auth_client(api_client, get_token_for_user, user):
    """DRF client authenticated with a real JWT (mirrors conftest pattern)."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


@pytest.mark.django_db
def test_health_returns_healthy_modules(auth_client):
    resp = auth_client.get(f"{BASE}/health/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert "dq.validate" in body["modules_available"]
    assert "chat" in body["modules_available"]


@pytest.mark.django_db
def test_modules_returns_twelve_types(auth_client):
    resp = auth_client.get(f"{BASE}/modules/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 12
    assert "investigate" in engine_runtime.MODULES
    assert all(m["type"] in engine_runtime.MODULES for m in body["modules"])


@pytest.mark.django_db
def test_task_status_unknown_is_fail_visible(auth_client):
    resp = auth_client.get(f"{BASE}/tasks/nope/")
    assert resp.status_code == 200  # NOT 404
    body = resp.json()
    assert body["status"] == "pulse_unavailable"
    assert body["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_endpoints_require_auth(api_client):
    assert api_client.get(f"{BASE}/health/").status_code == 401
    assert api_client.get(f"{BASE}/modules/").status_code == 401
    assert api_client.get(f"{BASE}/tasks/nope/").status_code == 401


@pytest.mark.django_db
def test_read_only_no_write_methods(auth_client):
    assert auth_client.post(f"{BASE}/health/", {}).status_code == 405
    assert auth_client.put(f"{BASE}/health/", {}).status_code == 405
    assert auth_client.delete(f"{BASE}/health/").status_code == 405
