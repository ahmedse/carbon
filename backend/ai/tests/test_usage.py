"""Phase 21-A — usage aggregation + quota tests.

Covers:

* ModelCatalog cost computation + model-id resolution (never ad hoc)
* usage persisted on a generation at completion (via the populate helper)
* AIUsage.summary aggregation (tokens, cost, tier/model buckets)
* AIUsage.by_conversation aggregation (CBAC: own conversations only)
* quota soft-warning (80%) + hard-exceeded ("quota" error code)
* request-time quota gate emits a "quota" error frame on the stream
* usage endpoints: auth required + admin override scoping
* AIUserProfile reset-day math (quota_reset_at / quota_window_start)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIGeneration, AIUserProfile, ModelCatalog
from ai.usage_service import AIUsage, QuotaExceededError, parse_period


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="usage-worker", password="secret123")


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(username="usage-other", password="secret123")


def _model(**overrides) -> ModelCatalog:
    base = {
        "model_id": "claude-haiku-4.5",
        "display_name": "Claude Haiku 4.5",
        "description": "Fast test model.",
        "tier": "fast",
        "version": "anthropic/claude-haiku-4.5",
        "context_window": 200000,
        "input_cost_per_1m": "1.00",
        "output_cost_per_1m": "5.00",
        "deprecated": False,
        "capabilities": [],
    }
    base.update(overrides)
    return ModelCatalog.objects.create(**base)


@pytest.fixture
def catalog(db):
    ModelCatalog.objects.all().delete()
    haiku = _model()
    brain = _model(
        model_id="gpt-4o", display_name="GPT-4o", tier="brain",
        version="openai/gpt-4o",
        input_cost_per_1m="2.50", output_cost_per_1m="10.00",
    )
    return {"haiku": haiku, "brain": brain}


def _conversation(user, **overrides) -> AIConversation:
    base = {
        "user": user,
        "title": "usage-test",
        "conversation_type": "chat",
        "scope_json": {},
        "task_payload_json": {},
    }
    base.update(overrides)
    return AIConversation.objects.create(**base)


def _generation(conversation, *, model_id="claude-haiku-4.5", prompt=0,
                completion=0, cost=None, status="completed",
                completed_at=None) -> AIGeneration:
    total = prompt + completion
    if cost is None:
        cost = ModelCatalog.compute_cost(model_id, prompt, completion)
    return AIGeneration.objects.create(
        conversation=conversation,
        status=status,
        completed_at=completed_at or timezone.now(),
        model_id=model_id,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cost=Decimal(cost),
    )


# ── ModelCatalog cost + resolution ──────────────────────────────────────


@pytest.mark.django_db
def test_model_catalog_resolve_model_id(catalog):
    assert ModelCatalog.resolve_model_id("claude-haiku-4.5") == "claude-haiku-4.5"
    assert ModelCatalog.resolve_model_id("anthropic/claude-haiku-4.5") == "claude-haiku-4.5"
    assert ModelCatalog.resolve_model_id("openai/gpt-4o") == "gpt-4o"
    assert ModelCatalog.resolve_model_id(None) == ""
    assert ModelCatalog.resolve_model_id("") == ""


@pytest.mark.django_db
def test_model_catalog_compute_cost(catalog):
    # 1M input * 1.00 + 1M output * 5.00 = 6.00
    cost = ModelCatalog.compute_cost("claude-haiku-4.5", 1_000_000, 1_000_000)
    assert cost == Decimal("6.000000")
    # zero tokens → zero cost
    assert ModelCatalog.compute_cost("claude-haiku-4.5", 0, 0) == Decimal("0.000000")
    # unknown model → zero cost (never fabricates)
    assert ModelCatalog.compute_cost("unknown-model", 1000, 1000) == Decimal("0.000000")


# ── usage persistence helper ────────────────────────────────────────────


@pytest.mark.django_db
def test_populate_generation_usage_writes_fields_and_catalog_cost(user, catalog):
    conv = _conversation(user)
    gen = _generation(conv, status="running", completed_at=None)
    gen.completed_at = None

    fields = CarbonIntelligence._populate_generation_usage(
        gen,
        {
            "prompt_tokens": 1000,
            "completion_tokens": 2000,
            "total_tokens": 3000,
            "model": "anthropic/claude-haiku-4.5",
        },
    )
    assert set(fields) == {
        "model_id", "prompt_tokens", "completion_tokens", "total_tokens", "cost",
    }
    assert gen.model_id == "claude-haiku-4.5"
    assert gen.prompt_tokens == 1000
    assert gen.completion_tokens == 2000
    assert gen.total_tokens == 3000
    # 1000/1e6 * 1.00 + 2000/1e6 * 5.00 = 0.001 + 0.010 = 0.011000
    assert gen.cost == Decimal("0.011000")


# ── summary aggregation ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_summary_aggregates_tokens_cost_tier_model(user, catalog):
    conv = _conversation(user)
    _generation(conv, model_id="claude-haiku-4.5", prompt=1_000, completion=2_000)
    _generation(conv, model_id="gpt-4o", prompt=10_000, completion=5_000)

    summary = AIUsage(user).summary(period_days=30)

    assert summary["total_tokens"] == 18_000
    assert summary["prompt_tokens"] == 11_000
    assert summary["completion_tokens"] == 7_000
    assert summary["total_generations"] == 2
    # haiku cost = 0.001 + 0.010 = 0.011 ; gpt-4o = 0.025 + 0.050 = 0.075
    assert Decimal(summary["total_cost"]) == Decimal("0.086000")
    assert set(summary["by_tier"].keys()) == {"fast", "brain"}
    assert summary["by_tier"]["fast"]["tokens"] == 3_000
    assert summary["by_tier"]["brain"]["tokens"] == 15_000
    assert set(summary["by_model"].keys()) == {"claude-haiku-4.5", "gpt-4o"}


@pytest.mark.django_db
def test_summary_scopes_to_own_user(user, other_user, catalog):
    mine = _conversation(user)
    theirs = _conversation(other_user)
    _generation(mine, prompt=100, completion=200)
    _generation(theirs, prompt=10_000, completion=10_000)

    summary = AIUsage(user).summary(period_days=30)
    assert summary["total_tokens"] == 300  # only mine, never theirs


# ── by-conversation aggregation ─────────────────────────────────────────


@pytest.mark.django_db
def test_by_conversation_groups_by_conversation(user, catalog):
    c1 = _conversation(user, title="first")
    c2 = _conversation(user, title="second")
    _generation(c1, prompt=100, completion=200)
    _generation(c1, prompt=50, completion=50)
    _generation(c2, prompt=1000, completion=1000)

    result = AIUsage(user).by_conversation(period_days=30)
    rows = {c["conversation_id"]: c for c in result["conversations"]}
    assert rows[str(c1.id)]["total_tokens"] == 400
    assert rows[str(c1.id)]["title"] == "first"
    assert rows[str(c1.id)]["generation_count"] == 2
    assert rows[str(c2.id)]["total_tokens"] == 2000


# ── quota enforcement ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_quota_soft_warning_at_80pct(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.monthly_token_limit = 1000
    profile.save()
    conv = _conversation(user)
    _generation(conv, prompt=810, completion=0)

    snapshot = AIUsage(user).quota_snapshot()
    assert snapshot["used"] == 810
    assert snapshot["soft_warning"] is True
    assert snapshot["hard_exceeded"] is False
    # still allowed
    AIUsage(user).check_quota()


@pytest.mark.django_db
def test_quota_hard_exceeded_raises(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.monthly_token_limit = 1000
    profile.save()
    conv = _conversation(user)
    _generation(conv, prompt=1001, completion=0)

    with pytest.raises(QuotaExceededError) as exc_info:
        AIUsage(user).check_quota()
    assert exc_info.value.code == "quota"
    assert exc_info.value.quota["hard_exceeded"] is True
    assert exc_info.value.quota["remaining"] == 0


@pytest.mark.django_db
def test_request_time_quota_gate_emits_quota_frame(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.monthly_token_limit = 100
    profile.save()
    conv = _conversation(user)
    _generation(conv, prompt=150, completion=0)

    frames = list(CarbonIntelligence().send_message_stream(user, str(conv.id), "hello"))
    assert frames
    assert frames[0]["type"] == "error"
    assert frames[0]["error_code"] == "quota"
    assert "quota" in frames[0]


# ── quota reset-day math ────────────────────────────────────────────────


@pytest.mark.django_db
def test_quota_reset_at_and_window_start(user):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.quota_reset_day = 15
    profile.save()

    now = timezone.make_aware(datetime(2026, 8, 18, 12, 0, 0))  # after the 15th
    reset_at = profile.quota_reset_at(now=now)
    assert (reset_at.year, reset_at.month, reset_at.day) == (2026, 9, 15)
    window_start = profile.quota_window_start(now=now)
    assert (window_start.year, window_start.month, window_start.day) == (2026, 8, 15)

    early = timezone.make_aware(datetime(2026, 8, 10, 12, 0, 0))  # before the 15th
    reset_at = profile.quota_reset_at(now=early)
    assert (reset_at.year, reset_at.month, reset_at.day) == (2026, 8, 15)
    window_start = profile.quota_window_start(now=early)
    assert (window_start.year, window_start.month, window_start.day) == (2026, 7, 15)


# ── endpoints ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_usage_endpoints_require_auth(catalog):
    client = APIClient()
    assert client.get(reverse("ai-usage-summary")).status_code == 401
    assert client.get(reverse("ai-usage-by-conversation")).status_code == 401


@pytest.mark.django_db
def test_usage_summary_endpoint_returns_own_data(user, other_user, catalog):
    conv = _conversation(user)
    _generation(conv, prompt=100, completion=200)
    _generation(_conversation(other_user), prompt=10_000, completion=10_000)

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(reverse("ai-usage-summary"))
    assert resp.status_code == 200
    assert resp.data["total_tokens"] == 300


@pytest.mark.django_db
def test_usage_summary_admin_override_scoped(user, other_user, catalog):
    from accounts.rbac_utils import user_is_global_admin

    admin = User.objects.create_user(username="usage-admin", password="secret123", is_superuser=True)
    _generation(_conversation(other_user), prompt=42, completion=0)

    client = APIClient()
    client.force_authenticate(user=admin)
    resp = client.get(
        reverse("ai-usage-summary"),
        {"user_id": other_user.id},
    )
    assert resp.status_code == 200
    assert resp.data["total_tokens"] == 42


@pytest.mark.django_db
def test_non_admin_cannot_override_user_id(user, other_user, catalog):
    _generation(_conversation(user), prompt=7, completion=0)
    _generation(_conversation(other_user), prompt=999, completion=0)

    client = APIClient()
    client.force_authenticate(user=user)
    # Non-admin passing user_id must be ignored (CBAC) — still own data.
    resp = client.get(reverse("ai-usage-summary"), {"user_id": other_user.id})
    assert resp.status_code == 200
    assert resp.data["total_tokens"] == 7


# ── period parsing ──────────────────────────────────────────────────────


def test_parse_period():
    assert parse_period("30d") == 30
    assert parse_period("7d") == 7
    assert parse_period("2w") == 14
    assert parse_period(45) == 45
    assert parse_period("garbage") == 30
    assert parse_period("0d") == 30
    assert parse_period(None) == 30
