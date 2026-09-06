"""Deterministic answer-quality eval gate (PAQ-1A).

Builds the KNOWN golden population from ``ai.eval.golden.GOLDEN_DATASET``,
drives the already-merged ``_people_analytics`` server-side aggregation, and
applies the pure checks in ``ai.eval.checks``.  No network, no LLM — this is
the CI gate that protects future prompt/model/renderer changes.

Each test mirrors the helper patterns of ``test_people_grounding.py``
(``_executor``, ``_analytics``, ``_make_org``, ``_make_employee``).
"""

from decimal import Decimal

import pytest
from asgiref.sync import async_to_sync

from accounts.models import User
from mdm.models import OrgUnit
from people.models import Employee, Position

from ai.eval.checks import (
    assert_caveat_fires_for_blank,
    assert_chart_type_rule,
    assert_counts_match_db,
    assert_no_raw_pk_labels,
    assert_synonym_merged,
    assert_truncation_collapsed_to_other,
)
from ai.eval.golden import GOLDEN_DATASET


# ─── helpers ────────────────────────────────────────────────────────────────

def _executor(user: User):
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:eval:{user.pk}",
        host_user_id=str(user.pk),
    )


def _anon_executor():
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(db=None, instance_config={}, user_token="", host_user_id="")


def _analytics(executor, dimension: str):
    return async_to_sync(executor._people_analytics_in_process)(
        method="GET", params={"dimension": dimension}, body={}
    )


def _make_org(name: str = "Eval HQ", slug: str = "eval-hq") -> OrgUnit:
    return OrgUnit.objects.get_or_create(slug=slug, defaults={"name": name})[0]


def _make_position(org: OrgUnit, title: str = "Engineer") -> Position:
    code = title.upper().replace(" ", "-")
    return Position.objects.get_or_create(
        org_unit=org, code=code, defaults={"title": title}
    )[0]


def _make_employee(
    org: OrgUnit,
    no: str = "E001",
    name: str = "Ali Hassan",
    position=None,
    gender: str = "",
    is_active: bool = True,
    **extra,
) -> Employee:
    return Employee.objects.create(
        org_unit=org,
        employee_no=no,
        full_name=name,
        basic_salary=Decimal("1200.000"),
        is_active=is_active,
        position=position,
        gender=gender,
        **extra,
    )


def _build_golden() -> None:
    """Materialise ``GOLDEN_DATASET`` (orgs → positions → employees)."""
    orgs = {}
    for key, name in GOLDEN_DATASET["orgs"]:
        orgs[key] = OrgUnit.objects.get_or_create(
            slug=f"eval-{key}", defaults={"name": name}
        )[0]

    positions = {}
    for key, org_key, code, title in GOLDEN_DATASET["positions"]:
        positions[key] = Position.objects.get_or_create(
            org_unit=orgs[org_key], code=code, defaults={"title": title}
        )[0]

    for emp in GOLDEN_DATASET["employees"]:
        _make_employee(
            orgs[emp["org"]],
            emp["no"],
            emp["name"],
            position=positions[emp["position"]],
            gender=emp["gender"],
            is_active=emp["is_active"],
        )


# ─── golden gender: exact counts + synonym merge + caveat threshold ─────────

@pytest.mark.django_db(transaction=True)
def test_golden_gender_exact_counts_and_synonym_merge():
    user = User.objects.create_superuser(username="eval-gender", password="secret123")
    _build_golden()

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    breakdown = data["breakdown"]

    # 6 male / 2 female / 1 blank — exact DB counts.
    assert_counts_match_db(breakdown, {"male": 6, "female": 2, "(blank)": 1})
    assert_no_raw_pk_labels(breakdown)

    # Raw "M"/"F" variants must be merged, never standalone buckets.
    assert_synonym_merged(breakdown, "male", "M")
    assert_synonym_merged(breakdown, "female", "F")
    assert data["was_normalized"] is True

    # Balanced (66.7 / 22.2 / 11.1) ⇒ pie, per the deterministic rule.
    assert data["suggested_chart_type"] == "pie"
    assert_chart_type_rule(breakdown, data["suggested_chart_type"])

    # Bucket counts sum to total == full DB population (superuser sees all).
    assert sum(r["count"] for r in breakdown) == data["total"]
    assert data["total"] == Employee.objects.count() == 9

    # blank = 1/9 = 11.1% < 50% ⇒ the missing-data caveat must NOT fire.
    text = " ".join(data["caveats"]).lower()
    assert "incomplete" not in text
    assert "recorded" not in text


@pytest.mark.django_db(transaction=True)
def test_golden_blank_caveat_fires_at_threshold():
    """blank ≥ 50% ⇒ a missing-data caveat must be disclosed (two-sided check)."""
    user = User.objects.create_superuser(username="eval-caveat", password="secret123")
    org = _make_org("Caveat HQ", "eval-caveat-hq")
    _make_employee(org, "CV001", "Gendered", gender="male")
    for i in range(9):
        _make_employee(org, f"CB{i:03d}", f"Blank {i}", gender="")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    assert_caveat_fires_for_blank(data["breakdown"], data["caveats"])


# ─── golden position: FK label resolution, no raw PKs ──────────────────────

@pytest.mark.django_db(transaction=True)
def test_golden_position_labels_are_titles_not_ids():
    user = User.objects.create_superuser(username="eval-pos", password="secret123")
    _build_golden()

    result = _analytics(_executor(user), "position")

    assert result["status_code"] == 200
    data = result["data"]
    breakdown = data["breakdown"]

    assert data["label_resolved"] is True, "FK position labels must be resolved"
    assert_counts_match_db(breakdown, {"Engineer": 5, "Supervisor": 2, "Floorman": 2})
    assert_no_raw_pk_labels(breakdown)

    labels = {r["label"] for r in breakdown}
    assert "Engineer" in labels
    assert "Supervisor" in labels
    assert "Floorman" in labels


# ─── golden is_active: active+inactive sum to total, dominant ⇒ bar ─────────

@pytest.mark.django_db(transaction=True)
def test_golden_is_active_sums_and_dominant_bar():
    user = User.objects.create_superuser(username="eval-active", password="secret123")
    _build_golden()

    result = _analytics(_executor(user), "is_active")

    assert result["status_code"] == 200
    data = result["data"]
    breakdown = data["breakdown"]

    # 7 active / 2 inactive — the labels are the stringified booleans.
    assert_counts_match_db(breakdown, {"True": 7, "False": 2})
    assert sum(r["count"] for r in breakdown) == data["total"] == 9

    # 7/9 = 77.8% dominant ⇒ bar, never pie.
    assert data["suggested_chart_type"] == "bar"
    assert_chart_type_rule(breakdown, data["suggested_chart_type"])


# ─── truncation: > max_buckets distinct values collapse to "Other" ─────────

@pytest.mark.django_db(transaction=True)
def test_golden_truncation_collapses_to_other():
    from ai.host_executor import _ANALYTICS_MAX_BUCKETS

    user = User.objects.create_superuser(username="eval-trunc", password="secret123")
    org = _make_org("Trunc HQ", "eval-trunc-hq")
    for i in range(_ANALYTICS_MAX_BUCKETS + 5):
        _make_employee(org, f"NT{i:04d}", f"Emp {i}", nationality=f"Country{i:02d}")

    result = _analytics(_executor(user), "nationality")

    assert result["status_code"] == 200
    data = result["data"]
    assert_truncation_collapsed_to_other(
        data["breakdown"], max_buckets=_ANALYTICS_MAX_BUCKETS
    )


# ─── gates: bad dimension / auth / empty population ────────────────────────

@pytest.mark.django_db(transaction=True)
def test_golden_bad_dimension_returns_400():
    user = User.objects.create_superuser(username="eval-baddim", password="secret123")
    _build_golden()

    result = _analytics(_executor(user), "salary")  # not an allowed dimension

    assert result["status_code"] == 400


@pytest.mark.django_db(transaction=True)
def test_golden_unauthenticated_returns_401():
    result = _analytics(_anon_executor(), "gender")
    assert result["status_code"] == 401


@pytest.mark.django_db(transaction=True)
def test_golden_no_capability_returns_403():
    user = User.objects.create_user(username="eval-403", password="secret123")
    result = _analytics(_executor(user), "gender")
    assert result["status_code"] == 403


@pytest.mark.django_db(transaction=True)
def test_golden_empty_population_returns_zero_total_with_caveat():
    """No employees ⇒ total 0, empty breakdown, a caveat explains why."""
    user = User.objects.create_superuser(username="eval-empty", password="secret123")
    # No employees created for this test — visibility returns nothing.
    result = _analytics(_executor(user), "gender")
    assert result["status_code"] == 200
    data = result["data"]
    assert data["total"] == 0
    assert data["breakdown"] == []
    assert len(data["caveats"]) > 0
