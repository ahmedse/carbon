"""Governed write slots — the consent card must not re-ask what was stated.

Live Agent (2026-09-21): "اريد تقديم طلب إجازة عادية لمدة يوم واحد. 1 اكتوبر
القادم" staged ``{days: 1, start_date: 2023-10-01, end_date: 2023-10-01}`` —
no ``leave_type`` (so the card asked for it) and a year the model invented
because it has no clock. Both are resolved from the operator's own words:
governed codes via ``mdm.ReferenceValue`` aliases, dates via the platform
clock. No leave-only alias tables anywhere.
"""
from __future__ import annotations

from datetime import date

import pytest

from ai.write_slots import (
    ground_future_date,
    is_date_field,
    parse_amount,
    parse_date_expression,
    parse_days,
    parse_months,
    write_slots_for,
)

TODAY = date(2026, 9, 21)


# ── Clock grounding (no DB) ───────────────────────────────────────────────


def test_model_date_in_the_past_rolls_to_the_intended_occurrence():
    assert ground_future_date("2023-10-01", today=TODAY) == "2026-10-01"


def test_future_date_is_left_alone():
    assert ground_future_date("2026-12-31", today=TODAY) == "2026-12-31"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 اكتوبر القادم", "2026-10-01"),
        ("1 أكتوبر", "2026-10-01"),
        ("October 1", "2026-10-01"),
        ("غدًا", "2026-09-22"),
        ("tomorrow", "2026-09-22"),
        ("اليوم", "2026-09-21"),
        ("1 يناير", "2027-01-01"),  # already past this year → next occurrence
    ],
)
def test_date_expressions_are_grounded(text, expected):
    parsed = parse_date_expression(text, today=TODAY)
    assert parsed is not None and parsed.isoformat() == expected


def test_unreadable_date_is_dropped_not_guessed():
    assert ground_future_date("sometime soon", today=TODAY) is None


def test_days_from_wording():
    assert parse_days("لمدة يوم واحد") == 1
    assert parse_days("for 3 days") == 3
    assert parse_days("لمدة 5 ايام") == 5
    assert parse_days("لمدة 3 شهور") is None
    assert parse_days("no duration here") is None


def test_loan_amount_and_months_from_wording():
    assert parse_amount("أريد قرض طوارئ 5000 لمدة 12 شهر") == 5000.0
    assert parse_amount("emergency loan of 2500 SAR") == 2500.0
    assert parse_amount("hello") is None
    assert parse_months("لمدة 12 شهر") == 12
    assert parse_months("for 6 months") == 6
    assert parse_months("لمدة 3 شهور") == 3
    assert parse_months("لمدة 3 ايام") is None
    assert parse_months("no term") is None


def test_hours_from_wording():
    from ai.write_slots import parse_hours

    assert parse_hours("ساعتين") == 2.0
    assert parse_hours("for 3 hours") == 3.0
    assert parse_hours("one hour") == 1.0
    assert parse_hours("no hours") is None


def test_date_field_detection():
    assert is_date_field("start_date")
    assert is_date_field("date")
    assert not is_date_field("days")
    assert not is_date_field("leave_type")


def test_write_slots_read_from_catalog_entry():
    catalog = [
        {"name": "submit_my_leave", "write_slots": [{"field": "leave_type", "governed": True}]},
        {"name": "list_my_leave"},
    ]
    assert write_slots_for("submit_my_leave", catalog) == [
        {"field": "leave_type", "governed": True},
    ]
    assert write_slots_for("list_my_leave", catalog) == []
    assert write_slots_for("unknown", catalog) == []


# ── Governed resolution (needs the MDM reference sets) ────────────────────


@pytest.fixture
def leave_types(db):
    from mdm.models import ReferenceSet, ReferenceValue

    rs, _ = ReferenceSet.objects.get_or_create(
        name="leave_type", defaults={"description": "Leave types"},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=rs, code="annual",
        defaults={"label": "Annual Leave", "metadata": {"aliases": ["عادية", "سنوية"]}},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=rs, code="emergency",
        defaults={"label": "Emergency Leave", "metadata": {"aliases": ["عارضة"]}},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=rs, code="unpaid",
        defaults={"label": "Unpaid Leave", "metadata": {}},
    )
    return rs


LEAVE_SLOTS = [
    {"field": "leave_type", "governed": True},
    {"field": "start_date", "type": "date", "future": True},
    {"field": "end_date", "type": "date", "future": True},
    {"field": "days", "type": "days"},
]


@pytest.mark.django_db
def test_bare_aadi_fills_leave_type_like_aadiah(leave_types):
    """Live Agent (2026-09-22): عادي (not عادية) must still ground to annual.

    Consent must reach summary/Approve — not ask "Which leave type?".
    """
    from people.leave_type_resolve import ensure_leave_type_aliases
    from ai.write_slots import consent_slot_specs, fill_write_body

    ensure_leave_type_aliases()
    body = fill_write_body(
        {},
        slots=LEAVE_SLOTS,
        text="اريد اجازة، ليوم واحد غدا، عادي.",
        today=TODAY,
    )
    assert body.get("leave_type") == "annual"
    assert body.get("start_date") == "2026-09-22"  # غدا relative to TODAY fixture
    assert body.get("end_date") == "2026-09-22"
    assert body.get("days") == 1

    # All required consent slots present → UI shows Approve, not chips.
    catalog = {
        "endpoints": [{
            "name": "submit_my_leave",
            "write_slots": LEAVE_SLOTS,
        }],
    }
    specs = consent_slot_specs("submit_my_leave", catalog)
    missing = [
        s["field"] for s in specs
        if s.get("required") and not body.get(s["field"])
    ]
    assert missing == [], f"ungrounded slots would force ask UI: {missing}"


@pytest.mark.django_db
def test_empty_body_is_filled_from_the_brief(leave_types):
    from ai.write_slots import fill_write_body

    body = fill_write_body(
        {},
        slots=LEAVE_SLOTS,
        text="تقديم طلب إجازة عارضة ليوم واحد غدًا",
        today=TODAY,
    )
    assert body == {
        "leave_type": "emergency",
        "start_date": "2026-09-22",
        "end_date": "2026-09-22",
        "days": 1,
    }


@pytest.mark.django_db
def test_multi_day_duration_stretches_the_span(leave_types):
    """A stated duration must not stage a one-day span the host rejects."""
    from ai.write_slots import fill_write_body

    body = fill_write_body(
        {},
        slots=LEAVE_SLOTS,
        text="اريد إجازة عادية لمدة 3 ايام من 1 اكتوبر",
        today=TODAY,
    )
    assert body == {
        "leave_type": "annual",
        "start_date": "2026-10-01",
        "end_date": "2026-10-03",
        "days": 3,
    }


@pytest.mark.django_db
def test_explicit_end_date_is_never_overridden(leave_types):
    from ai.write_slots import fill_write_body

    body = fill_write_body(
        {"start_date": "2026-10-01", "end_date": "2026-10-02", "days": 2},
        slots=LEAVE_SLOTS,
        text="إجازة عادية",
        today=TODAY,
    )
    assert body["end_date"] == "2026-10-02"


@pytest.mark.django_db
def test_unpaid_months_are_implicit_in_the_brief(leave_types):
    """بدون مرتب is unpaid; 3 شهور is a span, not 3 days."""
    from ai.write_slots import fill_write_body

    body = fill_write_body(
        {},
        slots=LEAVE_SLOTS,
        text="اريد طلب اجازة بدون مرتب لمدة 3 شهور, نبدأ من 1 فبراير 2027",
        today=TODAY,
    )
    assert body["leave_type"] == "unpaid"
    assert body["start_date"] == "2027-02-01"
    assert body["end_date"] == "2027-04-30"
    assert body["days"] == 89


@pytest.mark.django_db
def test_governed_synonym_is_repaired_without_any_text(leave_types):
    """Staging-time repair: no brief to read — values still governed."""
    from ai.write_slots import normalize_write_body

    body = normalize_write_body(
        {"leave_type": "إجازة عادية", "start_date": "2023-10-05", "days": 1},
        slots=LEAVE_SLOTS,
        today=TODAY,
    )
    assert body == {
        "leave_type": "annual",
        "start_date": "2026-10-05",
        "end_date": "2026-10-05",
        "days": 1,
    }


@pytest.mark.django_db
def test_past_date_is_kept_when_the_field_is_not_forward_dated(db):
    """A backdated hire date is legitimate — grounding is opt-in per slot."""
    from ai.write_slots import normalize_write_body

    body = normalize_write_body(
        {"join_date": "2023-10-05"},
        slots=[{"field": "join_date", "type": "date"}],
        today=TODAY,
    )
    assert body == {"join_date": "2023-10-05"}


@pytest.mark.django_db
def test_end_date_never_precedes_start_date(db):
    from ai.write_slots import normalize_write_body

    body = normalize_write_body(
        {"start_date": "2026-10-05", "end_date": "2026-10-01"},
        slots=LEAVE_SLOTS,
        today=TODAY,
    )
    assert body == {"start_date": "2026-10-05", "end_date": "2026-10-05"}


def test_endpoint_lookup_matches_method_and_path():
    from ai.write_slots import write_slots_for_endpoint

    catalog = [{
        "name": "submit_my_leave",
        "method": "POST",
        "path": "/carbon-api/people/me/leave/",
        "write_slots": [{"field": "leave_type", "governed": True}],
    }]
    assert write_slots_for_endpoint(
        "POST", "/carbon-api/people/me/leave/", catalog,
    ) == [{"field": "leave_type", "governed": True}]
    assert write_slots_for_endpoint(
        "GET", "/carbon-api/people/me/leave/", catalog,
    ) == []


@pytest.mark.django_db
def test_unresolvable_governed_value_is_dropped_for_the_host_to_answer(leave_types):
    """Junk must not be written — the host owns the "which value?" contract."""
    from ai.write_slots import normalize_write_body

    body = normalize_write_body({"leave_type": "purple"}, today=TODAY)
    assert "leave_type" not in body


@pytest.mark.django_db
def test_other_governed_sets_use_the_same_seam(db):
    """Attendance permission gets the same treatment — no per-API code."""
    from mdm.models import ReferenceSet, ReferenceValue

    from ai.write_slots import fill_write_body

    rs, _ = ReferenceSet.objects.get_or_create(
        name="permission_type", defaults={"description": "Permission types"},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=rs, code="medical",
        defaults={"label": "Medical", "metadata": {"aliases": ["طبي", "طبية"]}},
    )
    body = fill_write_body(
        {},
        slots=[
            {"field": "permission_type", "governed": True},
            {"field": "date", "type": "date"},
        ],
        text="أحتاج إذن حضور طبي 1 اكتوبر",
        today=TODAY,
    )
    assert body["permission_type"] == "medical"
    assert body["date"] == "2026-10-01"
