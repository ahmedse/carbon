"""P4-01 — Knowledge classes with metadata + conflict rules.

Covers the host-side :class:`ai.models.knowledge.KnowledgeItem` model and the
domain-agnostic engine-side conflict resolver in
:mod:`ai.engine.knowledge.classes`:

1. ``KnowledgeItem`` persists with all metadata fields and the correct defaults;
2. an invalid ``knowledge_class`` is rejected by Django validation;
3. the effective-period filter drops expired non-mandatory items but keeps
   expired *mandatory* items;
4. supersession drops a superseded predecessor (same class) and keeps a
   superseding item whose predecessor is missing;
5. mandatory items are returned before non-mandatory items in stable input order;
6. ``resolve_conflicts`` is pure (input list unchanged, returns a new list);
7. ``grant_capability`` always returns ``False``;
8. the engine module imports only the standard library (no host / Django imports).
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from ai.engine.knowledge.classes import (
    KNOWLEDGE_CLASSES as ENGINE_KNOWLEDGE_CLASSES,
    KnowledgeItemProjection,
    grant_capability,
    resolve_conflicts,
)
from ai.models.knowledge import (
    CLASS_BUSINESS_FACT,
    CLASS_POLICY,
    KNOWLEDGE_CLASSES,
    REVIEW_DRAFT,
    SENSITIVITY_INTERNAL,
    KnowledgeItem,
)

pytestmark = pytest.mark.django_db


# ── Helpers ────────────────────────────────────────────────────────────────

def _proj(
    item_id: str,
    *,
    knowledge_class: str = CLASS_POLICY,
    is_mandatory: bool = False,
    effective_start=None,
    effective_end=None,
    supersedes_id: str = "",
    **kwargs,
) -> KnowledgeItemProjection:
    """Build an engine-side projection with sensible test defaults."""
    return KnowledgeItemProjection(
        id=item_id,
        knowledge_class=knowledge_class,
        source="test",
        content=f"content-{item_id}",
        is_mandatory=is_mandatory,
        effective_start=effective_start,
        effective_end=effective_end,
        supersedes_id=supersedes_id,
        **kwargs,
    )


# ── 1. model persists with all fields + correct defaults ──────────────────

def test_knowledge_item_persists_with_all_fields_and_defaults():
    now = timezone.now()
    item = KnowledgeItem.objects.create(
        knowledge_class=CLASS_POLICY,
        source="policy-manual-v2",
        owner_id="alice",
        scope={"org_unit_id": 7, "module_id": 3},
        version="2",
        effective_start=now,
        effective_end=now + timedelta(days=365),
        review_status="approved",
        sensitivity="confidential",
        supersedes_id="00000000-0000-0000-0000-000000000001",
        content="Approvals require a designated authority.",
        is_mandatory=True,
    )

    reloaded = KnowledgeItem.objects.get(pk=item.pk)
    assert len(reloaded.pk) == 36  # string UUID pk, not an int
    assert reloaded.knowledge_class == CLASS_POLICY
    assert reloaded.source == "policy-manual-v2"
    assert reloaded.owner_id == "alice"
    assert reloaded.scope == {"org_unit_id": 7, "module_id": 3}
    assert reloaded.version == "2"
    assert reloaded.effective_start == now
    assert reloaded.effective_end == now + timedelta(days=365)
    assert reloaded.review_status == "approved"
    assert reloaded.sensitivity == "confidential"
    assert reloaded.supersedes_id == "00000000-0000-0000-0000-000000000001"
    assert reloaded.content == "Approvals require a designated authority."
    assert reloaded.is_mandatory is True
    assert reloaded.ingested_at is not None
    assert reloaded.created_at is not None
    assert reloaded.updated_at is not None

    # Defaults on a minimally-constructed item.
    minimal = KnowledgeItem.objects.create(
        knowledge_class=CLASS_BUSINESS_FACT, source="system", content="A fact.",
    )
    assert minimal.review_status == REVIEW_DRAFT
    assert minimal.sensitivity == SENSITIVITY_INTERNAL
    assert minimal.is_mandatory is False
    assert minimal.version == "1"
    assert minimal.owner_id == ""
    assert minimal.supersedes_id == ""
    assert minimal.scope == {}


# ── 2. invalid knowledge_class is rejected by Django validation ───────────

def test_invalid_knowledge_class_raises():
    item = KnowledgeItem(
        knowledge_class="bogus_kind", source="system", content="A fact.",
    )
    with pytest.raises(ValidationError):
        item.full_clean()


# ── 3. effective-period filter (mandatory survives expiry) ────────────────

def test_effective_period_filter_keeps_mandatory():
    now = timezone.now()
    expired = _proj("expired", effective_end=now - timedelta(days=1))
    future = _proj("future", effective_start=now + timedelta(days=1))
    current = _proj("current")
    mandatory_expired = _proj(
        "mandatory-expired", is_mandatory=True, effective_end=now - timedelta(days=1),
    )

    result = resolve_conflicts([expired, future, current, mandatory_expired], now)
    ids = [i.id for i in result]

    assert "expired" not in ids
    assert "future" not in ids
    assert "current" in ids
    assert "mandatory-expired" in ids  # mandatory constraint still holds


# ── 4. supersession ────────────────────────────────────────────────────────

def test_supersession_drops_predecessor():
    now = timezone.now()
    a = _proj("a")
    b = _proj("b", supersedes_id="a")
    dangling = _proj("dangling", supersedes_id="missing-a")

    result = resolve_conflicts([a, b, dangling], now)
    ids = [i.id for i in result]

    assert "a" not in ids      # superseded by b (same class)
    assert "b" in ids          # superseder kept
    assert "dangling" in ids   # predecessor missing → kept

    # Cross-class supersedes_id must NOT supersede.
    x = _proj("x")
    other = _proj("other", knowledge_class=CLASS_BUSINESS_FACT, supersedes_id="x")
    result2 = resolve_conflicts([x, other], now)
    assert [i.id for i in result2] == ["x", "other"]


# ── 5. mandatory items first, stable input order ──────────────────────────

def test_mandatory_ordered_first_stable():
    now = timezone.now()
    items = [
        _proj("a", is_mandatory=False),
        _proj("b", is_mandatory=True),
        _proj("c", is_mandatory=False),
        _proj("d", is_mandatory=True),
    ]

    result = resolve_conflicts(items, now)
    assert [i.id for i in result] == ["b", "d", "a", "c"]


# ── 6. resolve_conflicts is pure ──────────────────────────────────────────

def test_resolve_conflicts_is_pure():
    now = timezone.now()
    expired = _proj("expired", effective_end=now - timedelta(days=1))
    items = [expired, _proj("keep")]
    snapshot = list(items)

    result = resolve_conflicts(items, now)

    assert items == snapshot                    # input list unchanged
    assert result is not items                  # returns a new list
    assert items[0].effective_end == now - timedelta(days=1)  # projection untouched


# ── 7. grant_capability always False ──────────────────────────────────────

def test_grant_capability_always_false():
    assert grant_capability([]) is False
    assert grant_capability([_proj("a", is_mandatory=True)]) is False


# ── 8. engine boundary — stdlib only ──────────────────────────────────────

def test_engine_boundary_stdlib_only():
    import ai.engine.knowledge.classes as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("django", "accounts", "ai.models"):
        assert forbidden not in src, f"engine module leaks '{forbidden}'"


# ── Guard: host + engine class vocabularies agree ─────────────────────────

def test_knowledge_class_vocabularies_match():
    expected = {
        "policy",
        "process_definition",
        "business_fact",
        "procedural_heuristic",
        "episodic_observation",
        "user_preference",
    }
    assert set(KNOWLEDGE_CLASSES) == expected
    assert set(ENGINE_KNOWLEDGE_CLASSES) == expected
