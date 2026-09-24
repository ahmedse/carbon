"""Regression + correctness tests for Nibras grounded reads and server-side analytics.

Covers:
  * CarbonHostExecutor._people_in_process  — employees list/detail, CBAC, 401
  * Page cap enforcement: list returns ≤ PAGE_CAP rows; total reflects full population
  * _people_analytics_in_process  — GROUP BY, FK label resolution, caveats
  * Wrong-answer regression: "top position = 4 (real 52)" can no longer happen
  * Gender missing-data caveat (>50% blank → caveat emitted)
  * Bad dimension → 400
  * Analytics 401/403 gates
"""
from decimal import Decimal

import pytest
from asgiref.sync import async_to_sync

from accounts.models import User
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, Position


# ─── helpers ────────────────────────────────────────────────────────────────

def _executor(user: User):
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:nibras:{user.pk}",
        host_user_id=str(user.pk),
    )


def _anon_executor():
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(db=None, instance_config={}, user_token="", host_user_id="")


def _people(executor, endpoint: str, method: str = "GET", params=None, body=None):
    return async_to_sync(executor._people_in_process)(
        method=method, params=params or {}, body=body or {}, endpoint=endpoint
    )


def _analytics(executor, dimension: str, **params):
    return async_to_sync(executor._people_analytics_in_process)(
        method="GET", params={"dimension": dimension, **params}, body={}
    )


def _make_org(
    name: str = "Nibras HQ",
    slug: str = "nibras-hq",
    parent: OrgUnit | None = None,
) -> OrgUnit:
    return OrgUnit.objects.get_or_create(
        slug=slug, defaults={"name": name, "parent": parent}
    )[0]


def _ref(set_name: str, code: str, label: str | None = None) -> ReferenceValue:
    """Create/fetch a governed ReferenceValue (Employee.gender / nationality FKs)."""
    rs, _ = ReferenceSet.objects.get_or_create(
        name=set_name,
        defaults={"slug": set_name.replace("_", "-")},
    )
    rv, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs,
        code=code,
        defaults={"label": label or code, "is_active": True},
    )
    return rv


def _as_ref(set_name: str, value, *, label: str | None = None):
    """Accept ReferenceValue, code string, or blank/None → FK instance or None."""
    if value is None:
        return None
    if isinstance(value, ReferenceValue):
        return value
    code = str(value).strip()
    if not code:
        return None
    return _ref(set_name, code, label=label)


def _make_position(org: OrgUnit, title: str = "Engineer") -> Position:
    # Omit grade: model FK is nullable; avoid writing grade when DB/model diverge.
    code = title.upper().replace(" ", "-")
    return Position.objects.get_or_create(
        org_unit=org, code=code, defaults={"title": title}
    )[0]


def _make_employee(
    org: OrgUnit,
    no: str = "E001",
    name: str = "Ali Hassan",
    position=None,
    gender="",
    nationality=None,
    **extra,
) -> Employee:
    return Employee.objects.create(
        org_unit=org,
        employee_no=no,
        full_name=name,
        basic_salary=Decimal("1200.000"),
        is_active=True,
        position=position,
        gender=_as_ref("gender", gender),
        nationality=_as_ref("nationality", nationality),
        **extra,
    )


# ─── list employees ──────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_employees_in_process_returns_seeded_employee():
    user = User.objects.create_superuser(username="tg-list", password="secret123")
    org = _make_org("HQ", "tg-hq")
    _make_employee(org, "TG001", "Ali Hassan")

    result = _people(_executor(user), "carbon-api/people/employees")

    assert result["status_code"] == 200
    data = result["data"]
    assert data["count"] >= 1
    assert data["total"] >= 1
    names = [r["full_name"] for r in data["results"]]
    assert "Ali Hassan" in names


@pytest.mark.django_db(transaction=True)
def test_employee_list_exposes_total_and_count():
    """total always reflects full population; count is rows returned."""
    user = User.objects.create_superuser(username="tg-totals", password="secret123")
    org = _make_org("HQ2", "tg-hq2")
    for i in range(3):
        _make_employee(org, f"TT{i:03d}", f"Employee {i}")

    result = _people(_executor(user), "carbon-api/people/employees")

    assert result["status_code"] == 200
    data = result["data"]
    assert "total" in data, "total is required for honest population reporting"
    assert "count" in data
    assert data["total"] >= 3
    assert data["count"] == len(data["results"])


@pytest.mark.django_db(transaction=True)
def test_employees_page_cap_enforced(monkeypatch):
    """Never return more than PAGE_CAP rows; truncated + caveat set when over cap."""
    from ai import host_executor

    cap = 5
    monkeypatch.setattr(host_executor, "_PEOPLE_LIST_PAGE_CAP", cap)

    user = User.objects.create_superuser(username="tg-cap", password="secret123")
    org = _make_org("HQ3", "tg-hq3")
    for i in range(cap + 3):
        _make_employee(org, f"CAP{i:03d}", f"Cap Employee {i}")

    result = _people(_executor(user), "carbon-api/people/employees")

    assert result["status_code"] == 200
    data = result["data"]
    assert data["count"] <= cap, "must not exceed PAGE_CAP"
    assert data["total"] > cap, "total must reflect full set"
    assert data.get("truncated") is True, "truncated flag required when capped"
    assert "caveat" in data, "caveat required when truncated"
    assert str(data["total"]) in data["caveat"], "caveat must name the full total"


@pytest.mark.django_db(transaction=True)
def test_employee_detail_in_process_resolves_path_id():
    user = User.objects.create_superuser(username="tg-detail", password="secret123")
    org = _make_org("HQ4", "tg-hq4")
    employee = _make_employee(org, "TG002", "Sara Nabil")

    result = _people(_executor(user), f"carbon-api/people/employees/{employee.pk}")

    assert result["status_code"] == 200
    assert result["data"]["full_name"] == "Sara Nabil"
    assert result["data"]["employee_no"] == "TG002"


@pytest.mark.django_db(transaction=True)
def test_people_reads_require_capability():
    user = User.objects.create_user(username="tg-anon", password="secret123")
    org = _make_org("HQ5", "tg-hq5")
    _make_employee(org, "TG003", "Noor Ahmed")

    result = _people(_executor(user), "carbon-api/people/employees")

    assert result["status_code"] == 403


@pytest.mark.django_db(transaction=True)
def test_people_unauthenticated_returns_401():
    result = _people(_anon_executor(), "carbon-api/people/employees")
    assert result["status_code"] == 401


# ─── analytics: basic correctness ───────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_analytics_gender_breakdown_correct():
    """Counts match DB — the 'top = 4 instead of 52' bug cannot recur."""
    user = User.objects.create_superuser(username="tg-gender", password="secret123")
    org = _make_org("Ana-HQ", "ana-hq")
    # Create 5 male, 2 female, 3 blank
    for i in range(5):
        _make_employee(org, f"GM{i:03d}", f"Male {i}", gender="male")
    for i in range(2):
        _make_employee(org, f"GF{i:03d}", f"Female {i}", gender="female")
    for i in range(3):
        _make_employee(org, f"GB{i:03d}", f"Blank {i}", gender="")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    assert data["dimension"] == "gender"
    assert data["total"] >= 10

    breakdown = {row["label"]: row["count"] for row in data["breakdown"]}
    assert breakdown.get("male", 0) >= 5
    assert breakdown.get("female", 0) >= 2
    assert breakdown.get("(blank)", 0) >= 3

    total_pct = sum(r["pct"] for r in data["breakdown"])
    assert abs(total_pct - 100.0) < 1.0


@pytest.mark.django_db(transaction=True)
def test_analytics_synonym_normalization_merges_M_into_male():
    """Dirty ReferenceValue codes 'M'/'Male' merge into 'male' after FK resolve."""
    user = User.objects.create_superuser(username="tg-syn", password="secret123")
    org = _make_org("Syn-HQ", "syn-hq")
    # Distinct codes on ReferenceSet 'gender' (governed FK); analytics synonym-merges.
    _make_employee(org, "SN001", "John",  gender="male")
    _make_employee(org, "SN002", "James", gender="Male")   # capitalisation variant code
    _make_employee(org, "SN003", "Ali",   gender="M")       # abbreviation variant code
    _make_employee(org, "SN004", "Sara",  gender="female")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    labels = {r["label"] for r in data["breakdown"]}
    # "M" and "Male" must NOT appear as separate buckets
    assert "M" not in labels
    assert "Male" not in labels
    # All three must be merged under "male"
    male_row = next((r for r in data["breakdown"] if r["label"] == "male"), None)
    assert male_row is not None
    assert male_row["count"] >= 3, "male + Male + M should all be in one bucket"

    assert data["was_normalized"] is True
    assert len(data["normalization_notes"]) > 0
    # The note must identify what was merged and recommend cleanup
    note_text = " ".join(data["normalization_notes"])
    assert "male" in note_text.lower()
    assert "standardis" in note_text.lower() or "standard" in note_text.lower()


@pytest.mark.django_db(transaction=True)
def test_analytics_no_normalization_when_data_clean():
    """When all values are already canonical, was_normalized=False."""
    user = User.objects.create_superuser(username="tg-clean", password="secret123")
    org = _make_org("Clean-HQ", "clean-hq")
    for i in range(3):
        _make_employee(org, f"CL{i:03d}", f"Emp {i}", gender="male")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    assert data["was_normalized"] is False
    assert data["normalization_notes"] == []


@pytest.mark.django_db(transaction=True)
def test_analytics_suggested_chart_type_bar_for_dominant_bucket():
    """When one bucket holds >70% — 'bar' is returned, not 'pie'."""
    user = User.objects.create_superuser(username="tg-chartbar", password="secret123")
    org = _make_org("Bar-HQ", "bar-hq")
    # 9 active, 1 inactive → 90% dominant → must suggest bar
    for i in range(9):
        _make_employee(org, f"BA{i:03d}", f"Active {i}")  # is_active=True default
    e = _make_employee(org, "BA999", "Inactive")
    e.is_active = False
    e.save()

    result = _analytics(_executor(user), "is_active")

    assert result["status_code"] == 200
    assert result["data"]["suggested_chart_type"] == "bar", (
        "A 90%/10% split must suggest bar, not pie"
    )


@pytest.mark.django_db(transaction=True)
def test_analytics_suggested_chart_type_pie_for_balanced():
    """When distribution is balanced across ≤8 buckets — 'pie' is returned."""
    user = User.objects.create_superuser(username="tg-chartpie", password="secret123")
    org = _make_org("Pie-HQ", "pie-hq")
    # 4 male, 3 female, 3 unknown — reasonably balanced
    for i in range(4):
        _make_employee(org, f"PM{i:03d}", f"Male {i}", gender="male")
    for i in range(3):
        _make_employee(org, f"PF{i:03d}", f"Female {i}", gender="female")
    for i in range(3):
        _make_employee(org, f"PU{i:03d}", f"Unknown {i}", gender="nonbinary")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    assert result["data"]["suggested_chart_type"] == "pie"


@pytest.mark.django_db(transaction=True)
def test_analytics_top_n_collapse_for_high_cardinality():
    """More than _ANALYTICS_MAX_BUCKETS distinct values → tail collapsed to 'Other'."""
    from ai.host_executor import _ANALYTICS_MAX_BUCKETS

    user = User.objects.create_superuser(username="tg-topn", password="secret123")
    org = _make_org("TopN-HQ", "topn-hq")
    # Create MAX+5 distinct nationalities so the tail overflows
    for i in range(_ANALYTICS_MAX_BUCKETS + 5):
        _make_employee(org, f"NT{i:04d}", f"Emp {i}", nationality=f"Country{i:02d}")

    result = _analytics(_executor(user), "nationality")

    assert result["status_code"] == 200
    data = result["data"]
    labels = {r["label"] for r in data["breakdown"]}
    assert "Other" in labels, "tail must be collapsed into 'Other'"
    assert len(data["breakdown"]) <= _ANALYTICS_MAX_BUCKETS + 1  # top-N + Other
    other_row = next(r for r in data["breakdown"] if r["label"] == "Other")
    assert other_row["count"] >= 5
    assert len(data["caveats"]) > 0  # caveat about truncation


@pytest.mark.django_db(transaction=True)
def test_analytics_position_resolves_fk_labels():
    """Position breakdown uses the Position.title label, never the raw PK integer."""
    user = User.objects.create_superuser(username="tg-pos", password="secret123")
    org = _make_org("Pos-HQ", "pos-hq")
    driver_pos = _make_position(org, "Heavy Duty Driver")
    supervisor_pos = _make_position(org, "Supervisor")

    for i in range(3):
        _make_employee(org, f"PD{i:03d}", f"Driver {i}", position=driver_pos)
    for i in range(2):
        _make_employee(org, f"PS{i:03d}", f"Supervisor {i}", position=supervisor_pos)

    result = _analytics(_executor(user), "position")

    assert result["status_code"] == 200
    data = result["data"]
    assert data["label_resolved"] is True, "FK labels must be resolved"

    labels = {row["label"] for row in data["breakdown"]}
    assert "Heavy Duty Driver" in labels, "position title must appear, not PK"
    assert "Supervisor" in labels
    # PK integers must NOT appear as labels
    pk_labels = {row["label"] for row in data["breakdown"] if str(row["label"]).isdigit()}
    assert len(pk_labels) == 0, f"raw PK labels leaked: {pk_labels}"


@pytest.mark.django_db(transaction=True)
def test_analytics_position_counts_match_db():
    """Aggregation is server-side: counts are exact, never from a capped list."""
    user = User.objects.create_superuser(username="tg-poscount", password="secret123")
    org = _make_org("Count-HQ", "count-hq")
    top_pos = _make_position(org, "Top Driver")

    # Create MORE than PAGE_CAP employees in the top position.
    from ai.host_executor import _PEOPLE_LIST_PAGE_CAP
    n = _PEOPLE_LIST_PAGE_CAP + 10
    for i in range(n):
        _make_employee(org, f"PC{i:04d}", f"Driver {i}", position=top_pos)

    result = _analytics(_executor(user), "position")

    assert result["status_code"] == 200
    data = result["data"]
    assert data["total"] >= n, "total must count beyond PAGE_CAP"

    top_label_row = next(
        (r for r in data["breakdown"] if r["label"] == "Top Driver"), None
    )
    assert top_label_row is not None
    # The count must equal the full DB count, not a capped 100.
    assert top_label_row["count"] >= n, (
        f"Expected ≥{n}, got {top_label_row['count']} — "
        "LLM would have seen wrong numbers without server-side aggregation"
    )


@pytest.mark.django_db(transaction=True)
def test_analytics_missing_data_caveat_fired():
    """When >50% of employees have a blank dimension, caveats must include the rate."""
    user = User.objects.create_superuser(username="tg-caveat", password="secret123")
    org = _make_org("Cav-HQ", "cav-hq")
    # 1 gendered, 9 blank → 90% blank → caveat required
    _make_employee(org, "CV001", "Gendered", gender="male")
    for i in range(9):
        _make_employee(org, f"CB{i:03d}", f"Blank {i}", gender="")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    assert len(data["caveats"]) > 0, "caveat must fire when dimension is mostly blank"
    caveat_text = " ".join(data["caveats"])
    assert "%" in caveat_text, "caveat must name the blank percentage"
    assert "gender" in caveat_text.lower(), "caveat must name the dimension"


@pytest.mark.django_db(transaction=True)
def test_analytics_no_caveat_when_data_complete():
    """No caveat emitted when the dimension is fully populated."""
    user = User.objects.create_superuser(username="tg-nocav", password="secret123")
    org = _make_org("Full-HQ", "full-hq")
    for i in range(4):
        _make_employee(org, f"NC{i:03d}", f"Emp {i}", gender="male")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 200
    data = result["data"]
    # No blank caveat (all rows have gender="male", 0% blank)
    blank_caveats = [c for c in data["caveats"] if "incomplete" in c.lower()]
    assert len(blank_caveats) == 0


@pytest.mark.django_db(transaction=True)
def test_analytics_bad_dimension_returns_400():
    user = User.objects.create_superuser(username="tg-baddim", password="secret123")
    _make_org("Bad-HQ", "bad-hq")

    result = _analytics(_executor(user), "salary")  # not an allowed dimension

    assert result["status_code"] == 400
    assert "dimension" in result["data"]["detail"].lower() or "allowed" in result["data"]["detail"].lower()


@pytest.mark.django_db(transaction=True)
def test_analytics_department_filter_and_multi_group_are_applied():
    user = User.objects.create_superuser(username="tg-filtered", password="secret123")
    field_ops = _make_org("Field Operations", "tg-field-operations")
    coiled = _make_org("Coiled Tubing", "tg-coiled-tubing", parent=field_ops)
    other = _make_org("Drilling", "tg-drilling", parent=field_ops)
    operator = _make_position(coiled, "Coiled Operator")
    driller = _make_position(other, "Driller")
    for index in range(3):
        _make_employee(
            coiled, f"CT{index:03d}", f"Coiled {index}", position=operator
        )
    for index in range(2):
        _make_employee(
            other, f"DR{index:03d}", f"Driller {index}", position=driller
        )

    result = _analytics(
        _executor(user),
        "position",
        filters={"department": ["Coiled Tubing"]},
        group_by=["department", "position"],
    )

    assert result["status_code"] == 200, result
    data = result["data"]
    assert data["total"] == 3
    assert data["group_by"] == ["org_unit", "position"]
    assert data["applied_filters"] == {"org_unit": ["Coiled Tubing"]}
    assert data["breakdown"] == [{
        "org_unit": "Coiled Tubing",
        "position": "Coiled Operator",
        "count": 3,
        "pct": 100.0,
    }]


@pytest.mark.django_db(transaction=True)
def test_analytics_unknown_exact_department_fails_instead_of_widening():
    user = User.objects.create_superuser(username="tg-no-widen", password="secret123")
    org = _make_org("Coiled Tubing", "tg-no-widen-coiled")
    _make_employee(org, "NW001", "Scoped Employee")

    result = _analytics(
        _executor(user),
        "position",
        filters={"department": ["Field Ops"]},
        group_by=["department", "position"],
    )

    assert result["status_code"] == 400
    assert "field ops" in result["data"]["detail"].lower()


@pytest.mark.django_db(transaction=True)
def test_analytics_unauthenticated_returns_401():
    result = _analytics(_anon_executor(), "gender")
    assert result["status_code"] == 401


@pytest.mark.django_db(transaction=True)
def test_analytics_no_capability_returns_403():
    user = User.objects.create_user(username="tg-403", password="secret123")

    result = _analytics(_executor(user), "gender")

    assert result["status_code"] == 403


@pytest.mark.django_db(transaction=True)
def test_analytics_empty_population_returns_zero_total_with_caveat():
    """Zero employees → total=0, empty breakdown, caveat explaining why."""
    user = User.objects.create_superuser(username="tg-empty", password="secret123")
    # No employees created — the visibility filter returns nothing.
    result = _analytics(_executor(user), "gender")
    assert result["status_code"] == 200
    data = result["data"]
    assert data["total"] == 0
    assert data["breakdown"] == []
    assert len(data["caveats"]) > 0


# ─── create / activate (onboarding host mutations) ───────────────────────────

@pytest.mark.django_db(transaction=True)
def test_create_employee_post_returns_201():
    """Agent confirm create_employee must not 404 — in-process POST exists."""
    from datetime import date

    user = User.objects.create_superuser(username="tg-hire", password="secret123")
    org = _make_org("Hire Org", "tg-hire-org")
    no = "HIRE001"
    result = _people(
        _executor(user),
        "carbon-api/people/employees",
        method="POST",
        body={
            "employee_no": no,
            "full_name": "New Hire",
            "org_unit": org.pk,
            "join_date": date.today().isoformat(),
            "basic_salary": "500.000",
            "is_active": False,
        },
    )
    assert result["status_code"] == 201, result
    assert result["data"]["employee_no"] == no
    assert Employee.objects.filter(employee_no=no).exists()


@pytest.mark.django_db(transaction=True)
def test_update_employee_patch_activates():
    """Onboarding activate uses PATCH is_active=true via in-process host."""
    user = User.objects.create_superuser(username="tg-act", password="secret123")
    org = _make_org("Act Org", "tg-act-org")
    emp = _make_employee(org, "ACT001", "Inactive Hire")
    emp.is_active = False
    emp.save(update_fields=["is_active"])
    result = _people(
        _executor(user),
        f"carbon-api/people/employees/{emp.pk}",
        method="PATCH",
        body={"is_active": True},
    )
    assert result["status_code"] == 200, result
    emp.refresh_from_db()
    assert emp.is_active is True
