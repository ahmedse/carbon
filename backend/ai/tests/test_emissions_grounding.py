"""Regression tests for Tier 1 read-only AI emissions data grounding.

The AI used to recite generic emission factors from memory because the host
executor had no emissions routes. These tests prove the in-process executor
can read live ``EmissionFactor``, ``Calculation`` summary, and chairman
``footprint_tonnes`` data (RULE_11 — never fix the same bug twice).
"""
from decimal import Decimal
from numbers import Number

import pytest
from asgiref.sync import async_to_sync

from accounts.models import User
from core.models import Module
from dataschema.models import DataRow, DataTable
from emissions.models import Calculation, EmissionFactor, ReportingPeriod
from mdm.models import OrgUnit


def _executor(user: User):
    from ai.host_executor import CarbonHostExecutor

    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:carbon:{user.pk}",
        host_user_id=str(user.pk),
    )


def _call(executor, name, *args, **kwargs):
    return async_to_sync(getattr(executor, name))(*args, **kwargs)


@pytest.mark.django_db(transaction=True)
def test_factors_in_process_returns_seeded_factor():
    user = User.objects.create_user(username="grounding-factors", password="secret123")
    EmissionFactor.objects.create(
        code="EG_GRID_2024",
        name="Egypt Grid 2024",
        category="electricity",
        scope=2,
        factor_value=Decimal("0.4584"),
        factor_unit="kg CO2e",
        activity_unit="kWh",
        country="Egypt",
        source="EEHC 2024",
        tags=["grid", "electricity"],
        valid_from="2024-01-01",
        is_active=True,
    )

    result = _call(_executor(user), "_emission_factors_in_process", "GET", {}, {})

    assert result["status_code"] == 200
    assert isinstance(result["data"]["results"], list)
    factor = next(
        r for r in result["data"]["results"] if r["code"] == "EG_GRID_2024"
    )
    assert factor["factor_value"] == 0.4584
    assert factor["activity_unit"] == "kWh"
    assert factor["factor_unit"] == "kg CO2e"


@pytest.mark.django_db(transaction=True)
def test_chairman_overview_returns_footprint():
    user = User.objects.create_superuser(
        username="grounding-chairman", password="secret123"
    )
    org = OrgUnit.objects.create(name="Grounding Org", slug="grounding-org")
    module = Module.objects.create(
        name="Grounding Electricity Chairman", scope=2, org_unit=org
    )
    table = DataTable.objects.create(
        title="Grounding Elec Chairman", name="grounding_elec_chairman", module=module
    )
    row = DataRow.objects.create(data_table=table, values={"kwh": "1000"})
    period = ReportingPeriod.objects.create(
        name="FY 2026 Chairman",
        start_date="2026-01-01",
        end_date="2026-12-31",
        status="open",
    )
    factor = EmissionFactor.objects.create(
        code="EG_CHAIR_2024",
        name="Egypt Grid 2024",
        category="electricity",
        scope=2,
        factor_value=Decimal("0.4584"),
        factor_unit="kg CO2e",
        activity_unit="kWh",
        source="EEHC 2024",
        valid_from="2024-01-01",
        is_active=True,
    )
    Calculation.objects.create(
        data_row=row,
        module=module,
        emission_factor=factor,
        activity_value=Decimal("1000"),
        activity_unit="kWh",
        co2e_kg=Decimal("458.4"),
        scope=2,
        category="electricity",
        reporting_period=period,
        reporting_year=2026,
    )

    result = _call(
        _executor(user),
        "_chairman_overview_in_process",
        "GET",
        {"reporting_period_id": period.pk},
        {},
    )

    assert result["status_code"] == 200
    headline = result["data"]["headline"]
    assert "footprint_tonnes" in headline
    assert isinstance(headline["footprint_tonnes"], Number)
    assert float(headline["footprint_tonnes"]) == pytest.approx(0.46, rel=0.01)


@pytest.mark.django_db(transaction=True)
def test_summary_is_org_scoped():
    admin = User.objects.create_superuser(
        username="grounding-admin", password="secret123"
    )
    restricted = User.objects.create_user(
        username="grounding-restricted", password="secret123"
    )
    org = OrgUnit.objects.create(name="Grounding Summary Org", slug="grounding-summary-org")
    module = Module.objects.create(
        name="Grounding Electricity Summary", scope=2, org_unit=org
    )
    table = DataTable.objects.create(
        title="Grounding Elec Summary", name="grounding_elec_summary", module=module
    )
    row = DataRow.objects.create(data_table=table, values={"kwh": "1000"})
    period = ReportingPeriod.objects.create(
        name="FY 2026 Summary",
        start_date="2026-01-01",
        end_date="2026-12-31",
        status="open",
    )
    factor = EmissionFactor.objects.create(
        code="EG_SUM_2024",
        name="Egypt Grid 2024",
        category="electricity",
        scope=2,
        factor_value=Decimal("0.4584"),
        factor_unit="kg CO2e",
        activity_unit="kWh",
        source="EEHC 2024",
        valid_from="2024-01-01",
        is_active=True,
    )
    Calculation.objects.create(
        data_row=row,
        module=module,
        emission_factor=factor,
        activity_value=Decimal("1000"),
        activity_unit="kWh",
        co2e_kg=Decimal("458.4"),
        scope=2,
        category="electricity",
        reporting_period=period,
        reporting_year=2026,
    )

    admin_summary = _call(
        _executor(admin), "_calculation_summary_in_process", "GET", {}, {}
    )
    restricted_summary = _call(
        _executor(restricted), "_calculation_summary_in_process", "GET", {}, {}
    )

    assert admin_summary["status_code"] == 200
    assert admin_summary["data"]["total_calculations"] >= 1
    assert restricted_summary["status_code"] == 200
    assert restricted_summary["data"]["total_calculations"] == 0
