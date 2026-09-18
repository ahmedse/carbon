# backend/catalog/tests/test_trust_index.py
import pytest
from datetime import timedelta

from django.utils import timezone

from catalog.trust_index import (
    compute_trust_index,
    freshness_snapshot_for_table,
)


class _FakeTags:
    def __init__(self, n):
        self._n = n

    def count(self):
        return self._n


class _FakeAsset:
    def __init__(self, **kwargs):
        self.quality_score = kwargs.get("quality_score")
        self.owner_id = kwargs.get("owner_id")
        self.steward_id = kwargs.get("steward_id")
        self.description = kwargs.get("description", "")
        self.glossary_term_id = kwargs.get("glossary_term_id")
        self.domain_id = kwargs.get("domain_id")
        self.tags = _FakeTags(kwargs.get("tag_count", 0))
        self.data_table_id = kwargs.get("data_table_id")
        self.data_table = kwargs.get("data_table")
        self.data_field_id = kwargs.get("data_field_id")
        self.data_field = kwargs.get("data_field")


class _FakeTable:
    def __init__(self, *, age_hours=1.0, created_at=None):
        self.id = 1
        now = timezone.now()
        self.last_data_updated_at = now - timedelta(hours=age_hours)
        self.created_at = created_at or self.last_data_updated_at


class _FakePolicy:
    def __init__(self, max_age_hours=24, enabled=True):
        self.max_age_hours = max_age_hours
        self.enabled = enabled


def test_trust_index_empty_is_untrustworthy():
    # No Q/O/C; freshness unknown → 5 pts (DTR-5)
    result = compute_trust_index(_FakeAsset(), freshness={"status": "unknown"})
    assert result["score"] == 5
    assert result["tier"] == "untrustworthy"
    assert result["breakdown"]["quality"]["points"] == 0
    assert result["breakdown"]["ownership"]["points"] == 0
    assert result["breakdown"]["context"]["points"] == 0
    assert result["breakdown"]["freshness"]["points"] == 5
    assert result["breakdown"]["freshness"]["max"] == 10


def test_trust_index_full_fresh_is_trusted():
    asset = _FakeAsset(
        quality_score=100,
        owner_id=1,
        steward_id=2,
        description="Payroll facts for GOFSCO",
        glossary_term_id=9,
        domain_id=3,
        tag_count=2,
    )
    result = compute_trust_index(asset, freshness={"status": "fresh", "age_hours": 1, "max_age_hours": 24})
    # 35 + 20 + 8+12+10+5 + 10 = 100
    assert result["score"] == 100
    assert result["tier"] == "trusted"
    assert result["breakdown"]["quality"]["points"] == 35
    assert result["breakdown"]["ownership"]["points"] == 20
    assert result["breakdown"]["context"]["points"] == 35
    assert result["breakdown"]["freshness"]["points"] == 10


def test_trust_index_stale_drops_freshness_only():
    asset = _FakeAsset(
        quality_score=100,
        owner_id=1,
        description="x",
        glossary_term_id=1,
        domain_id=1,
        tag_count=1,
    )
    result = compute_trust_index(asset, freshness={"status": "stale", "age_hours": 48, "max_age_hours": 24})
    # 35 + 20 + 35 + 0 = 90
    assert result["score"] == 90
    assert result["breakdown"]["freshness"]["points"] == 0
    assert result["breakdown"]["freshness"]["status"] == "stale"


def test_trust_index_steward_only_half_ownership():
    result = compute_trust_index(
        _FakeAsset(steward_id=5, quality_score=50),
        freshness={"status": "unknown"},
    )
    assert result["breakdown"]["ownership"]["points"] == 10
    assert result["breakdown"]["quality"]["points"] == 17.5
    assert result["breakdown"]["freshness"]["points"] == 5
    # 17.5 + 10 + 0 + 5 = 32.5 → 32 or 33
    assert result["score"] in (32, 33)
    assert result["tier"] == "limited"


def test_quality_none_contributes_zero():
    result = compute_trust_index(
        _FakeAsset(owner_id=1, description="x"),
        freshness={"status": "unknown"},
    )
    assert result["breakdown"]["quality"]["points"] == 0
    assert result["breakdown"]["ownership"]["points"] == 20
    assert result["breakdown"]["context"]["points"] == 8
    assert result["breakdown"]["freshness"]["points"] == 5
    assert result["score"] == 33


def test_freshness_snapshot_fresh_vs_stale():
    table = _FakeTable(age_hours=2)
    policy = _FakePolicy(max_age_hours=24)
    snap = freshness_snapshot_for_table(table, policy=policy)
    assert snap["status"] == "fresh"

    stale_table = _FakeTable(age_hours=48)
    snap2 = freshness_snapshot_for_table(stale_table, policy=policy)
    assert snap2["status"] == "stale"


def test_freshness_snapshot_no_policy_is_unknown():
    table = _FakeTable(age_hours=2)
    snap = freshness_snapshot_for_table(table, policy=None)
    assert snap["status"] == "unknown"
