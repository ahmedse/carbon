"""Phase C — Pulse activation read API tests (usage/ + settings/).

Tests:
  * usage/ returns 200 with the budget/spend/token/call aggregates
  * usage/ aggregates seeded LLMCallLog rows by model and by day
  * settings/ returns 200 with all eight sections (llm/limits/cache/...)
  * settings/ never leaks the API key (string match against full payload)
  * settings/ carries no secret-hinting key with a non-redacted string value
  * both endpoints require auth; both reject write methods with 405
"""
import json
import re

import pytest

from ai.models.core import LLMCallLog

BASE = "/carbon-api/ai/pulse"

_SECRET_KEY_RE = re.compile(r"token|secret|password|api_key", re.IGNORECASE)


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="ai-activation", password="secret123")


@pytest.fixture
def auth_client(api_client, get_token_for_user, user):
    """DRF client authenticated with a real JWT (mirrors conftest pattern)."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


def _leaf_paths(obj, path=""):
    """Yield (path, value) for every leaf of a JSON-ish structure."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _leaf_paths(value, f"{path}/{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from _leaf_paths(item, f"{path}/{index}")
    else:
        yield path, obj


# ── usage/ ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_usage_requires_auth(api_client):
    assert api_client.get(f"{BASE}/usage/").status_code == 401


@pytest.mark.django_db
def test_usage_returns_aggregates_empty_db(auth_client):
    """All aggregate keys present with correct types on a fresh DB.

    Note: the test DB is reused (--reuse-db) and live-LLM tests also write
    LLMCallLog rows, so we assert structure, not absolute totals.
    """
    resp = auth_client.get(f"{BASE}/usage/")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "budget_usd",
        "spent_today_usd",
        "tokens_today",
        "calls_today",
        "tokens_total",
        "calls_total",
        "cost_total",
        "remaining_usd",
        "budget_exceeded",
    ):
        assert key in body
    assert isinstance(body["budget_exceeded"], bool)
    assert isinstance(body["by_model"], list)
    assert isinstance(body["by_day"], list)
    assert body["budget_usd"] > 0


@pytest.mark.django_db
def test_usage_aggregates_seeded_logs(auth_client):
    """Seeded LLMCallLog rows appear in the aggregates (delta-based).

    The test DB is reused across runs and other tests may write rows, so we
    capture a baseline and assert the exact delta our seeds introduce.
    """
    before = auth_client.get(f"{BASE}/usage/").json()

    LLMCallLog.objects.create(
        instance_id="inst-1",
        conversation_id="conv-1",
        model="model-a",
        total_tokens=100,
        cost_usd=0.01,
    )
    LLMCallLog.objects.create(
        instance_id="inst-1",
        conversation_id="conv-2",
        model="model-b",
        total_tokens=50,
        cost_usd=0.005,
    )

    resp = auth_client.get(f"{BASE}/usage/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls_total"] == before["calls_total"] + 2
    assert body["tokens_total"] == before["tokens_total"] + 150
    assert abs(body["cost_total"] - (before["cost_total"] + 0.015)) < 1e-9
    assert body["calls_today"] == before["calls_today"] + 2
    assert body["tokens_today"] == before["tokens_today"] + 150
    models = {row["model"] for row in body["by_model"]}
    assert {"model-a", "model-b"} <= models
    assert body["by_day"], "seeded logs must appear in the 7-day breakdown"
    assert all(
        "date" in row and "cost_usd" in row and "calls" in row
        for row in body["by_day"]
    )


@pytest.mark.django_db
def test_usage_rejects_write_methods(auth_client):
    assert auth_client.post(f"{BASE}/usage/", {}).status_code == 405
    assert auth_client.put(f"{BASE}/usage/", {}).status_code == 405
    assert auth_client.delete(f"{BASE}/usage/").status_code == 405


# ── settings/ ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_settings_requires_auth(api_client):
    assert api_client.get(f"{BASE}/settings/").status_code == 401


@pytest.mark.django_db
def test_settings_returns_all_sections(auth_client):
    resp = auth_client.get(f"{BASE}/settings/")
    assert resp.status_code == 200
    body = resp.json()
    for section in (
        "llm",
        "limits",
        "cache",
        "rate_limit",
        "routing",
        "mcp_servers",
        "tools_catalog",
        "agents",
    ):
        assert section in body

    llm = body["llm"]
    for key in (
        "base_url",
        "model",
        "normal_model",
        "cognition_model",
        "embedding_model",
        "eval_model",
        "daily_budget_usd",
        "allow_expensive_models",
    ):
        assert key in llm
    assert "LLM_API_KEY" not in llm

    assert isinstance(body["routing"], dict)
    assert body["routing"]["chat"]
    assert isinstance(body["limits"], dict)
    assert "GUARDRAIL_MAX_TOOL_CALLS_PER_RUN" in body["limits"]
    assert isinstance(body["mcp_servers"], list)
    assert isinstance(body["tools_catalog"], list)
    assert isinstance(body["agents"], list)
    assert isinstance(body["cache"], dict)
    assert "ttl_seconds" in body["cache"]


@pytest.mark.django_db
def test_settings_never_leaks_api_key(auth_client):
    from ai.engine.core.config import get_settings

    api_key = get_settings().LLM_API_KEY
    resp = auth_client.get(f"{BASE}/settings/")
    assert resp.status_code == 200
    payload_text = json.dumps(resp.json())
    # Guard: with no key configured, "" is trivially "in" any string.
    if api_key:
        assert api_key not in payload_text


@pytest.mark.django_db
def test_settings_has_no_unredacted_secret_strings(auth_client):
    """No leaf under a secret-hinting key carries a non-redacted string.

    Numeric/bool config values under token-hinting keys (e.g.
    ``RUN_TOKEN_BUDGET_DEFAULT``) are safe — only secret-shaped strings
    (``[REDACTED]`` or absent) may appear there.
    """
    resp = auth_client.get(f"{BASE}/settings/")
    assert resp.status_code == 200
    for path, value in _leaf_paths(resp.json()):
        if _SECRET_KEY_RE.search(path):
            assert value == "[REDACTED]" or not isinstance(value, str), (
                f"secret-hinting key leaked a string value: {path!r}"
            )


@pytest.mark.django_db
def test_settings_rejects_write_methods(auth_client):
    assert auth_client.post(f"{BASE}/settings/", {}).status_code == 405
    assert auth_client.put(f"{BASE}/settings/", {}).status_code == 405
    assert auth_client.delete(f"{BASE}/settings/").status_code == 405
