"""Shared fixtures for Pulse AI engine tests (Phase A).

Patterns:
  * ``carbon_executor(user)`` — build the in-process host executor used by the
    chat path (CarbonHostExecutor with inproc token).
  * ``scoped_user`` — user + ScopedRole with an org/module/group; use
    ``group_name="viewers_group"`` for read-only visibility, ``"dataowners_group"``
    for read-write.
  * Org-scoping helpers mirror the emissions grounding tests so every CBAC
    scenario can assert "user in org A cannot see org B's data".

All fixtures are function-scoped and DB-backed (django_db) so tests stay
isolated. Tests that invoke executor coroutines must use
``@pytest.mark.django_db(transaction=True)`` (the executor calls services
that read the DB inside sync_to_async threads).
"""
from decimal import Decimal

import pytest
from asgiref.sync import async_to_sync

from accounts.models import ScopedRole, User
from core.models import Module
from emissions.models import Calculation, EmissionFactor, ReportingPeriod
from mdm.models import OrgUnit


# ── Helpers ────────────────────────────────────────────────────────────────


def make_user(username: str, *, superuser: bool = False, staff: bool = False) -> User:
    """Create a plain user (or superuser)."""
    if superuser:
        return User.objects.create_superuser(username=username, password="secret123")
    user = User.objects.create_user(username=username, password="secret123")
    if staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    return user


def make_org(name: str) -> OrgUnit:
    """Create an org unit (slug auto-derived from name)."""
    return OrgUnit.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def make_module(name: str, org: OrgUnit, scope: int = 2) -> Module:
    """Create a Module bound to an org (scope 2 = indirect energy default)."""
    return Module.objects.create(name=name, scope=scope, org_unit=org)


def grant_role(user: User, *, group_name: str, org: OrgUnit | None = None,
               module: Module | None = None) -> ScopedRole:
    """Grant a ScopedRole; group must be in accounts.constants sets to matter."""
    from django.contrib.auth.models import Group
    group, _ = Group.objects.get_or_create(name=group_name)
    return ScopedRole.objects.create(
        user=user, group=group, org_unit=org, module=module, is_active=True,
    )


def make_factor(*, code: str, value: Decimal | float = Decimal("0.4584"),
                name: str | None = None, category: str = "electricity",
                scope: int = 2, unit: str = "kg CO2e", activity: str = "kWh",
                country: str = "Egypt", source: str = "EEHC 2024",
                is_active: bool = True) -> EmissionFactor:
    """Create an active emission factor (factors are GLOBAL — RULE_12)."""
    return EmissionFactor.objects.create(
        code=code,
        name=name or code.replace("_", " ").title(),
        category=category,
        scope=scope,
        factor_value=Decimal(value),
        factor_unit=unit,
        activity_unit=activity,
        country=country,
        source=source,
        tags=[],
        valid_from="2024-01-01",
        is_active=is_active,
    )


def make_calculation(*, org: OrgUnit, module_name: str, factor: EmissionFactor,
                     kwh: str = "1000", scope: int = 2,
                     period_name: str = "FY 2026") -> Calculation:
    """Create the full chain org→module→table→row→calculation and return it.

    The module's org determines scoping: users with a role on ``org`` (or an
    ancestor) see this calculation via ``get_visible_module_ids``.
    """
    from dataschema.models import DataRow, DataTable
    module = make_module(module_name, org, scope=scope)
    table = DataTable.objects.create(
        title=module_name, name=module_name.lower().replace(" ", "_"), module=module,
    )
    row = DataRow.objects.create(data_table=table, values={"kwh": kwh})
    period = ReportingPeriod.objects.create(
        name=period_name,
        start_date="2026-01-01",
        end_date="2026-12-31",
        status="open",
    )
    return Calculation.objects.create(
        data_row=row,
        module=module,
        emission_factor=factor,
        activity_value=Decimal(kwh),
        activity_unit="kWh",
        co2e_kg=Decimal(kwh) * factor.factor_value,
        scope=scope,
        category=factor.category,
        reporting_period=period,
        reporting_year=2026,
    )


def carbon_executor(user: User | None):
    """Build the in-process CarbonHostExecutor wired exactly like the chat path.

    ``user=None`` simulates an unauthenticated call (host_user_id missing) —
    the executor's ``_resolve_user`` then returns None and endpoints answer 401.
    """
    from ai.host_executor import CarbonHostExecutor
    user_id = str(user.pk) if user is not None else ""
    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:carbon:{user_id}" if user is not None else "",
        host_user_id=user_id,
    )


def call(executor, name: str, *args, **kwargs):
    """Invoke an executor coroutine synchronously."""
    return async_to_sync(getattr(executor, name))(*args, **kwargs)


# ── Test hygiene ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _flush_pulse_memory():
    """Flush Pulse engine ephemeral-memory keys before each test.

    Working/short-term memory are Redis-backed (source of truth), so a stale
    ``pulse:*`` key left by a previous test can leak focus across tests — e.g.
    the anaphora resolver "resolving" a pronoun with no focus set at all. Flush
    the namespace up front to keep memory tests deterministic.
    """
    from ai.engine.memory._redis import get_redis_client

    client = get_redis_client()
    if client is None:
        return
    try:
        keys = client.keys("pulse:*")
        if keys:
            client.delete(*keys)
    except Exception:  # noqa: BLE001 — Redis flush is best-effort test hygiene
        pass


# ── Public fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def users():
    """Container for user factories: users.make(), users.superuser()."""
    class _Users:
        @staticmethod
        def make(username: str = "user", **kw) -> User:
            return make_user(username, **kw)
    return _Users()


@pytest.fixture
def make_scoped_user():
    """Factory: create a user with a granted role.

    Example::

        user = make_scoped_user("analyst-a", group="viewers_group", org=org_a)

    Returns the User (the ScopedRole is created for org + visibility).
    """
    def _make(username: str, *, group: str = "viewers_group",
              org: OrgUnit | None = None, module: Module | None = None,
              superuser: bool = False) -> User:
        user = make_user(username, superuser=superuser)
        if not superuser:
            grant_role(user, group_name=group, org=org, module=module)
        return user
    return _make


@pytest.fixture
def seeded_factors():
    """Two GLOBAL active emission factors + one inactive (must be excluded)."""
    return {
        "grid": make_factor(code="EG_GRID_2024", value="0.4584"),
        "diesel": make_factor(
            code="DIESEL_2024", value="2.51", category="mobile_combustion",
            activity="liter", source="IPCC 2024",
        ),
        "inactive": make_factor(
            code="OLD_FACTOR", value="0.9", is_active=False,
        ),
    }


@pytest.fixture
def org_a_and_b():
    """Two orgs, each with one module + one calculation (differing footprints)."""
    org_a = make_org("Org Alpha")
    org_b = make_org("Org Beta")
    f_a = make_factor(code="FACTOR_A", value="0.4584")
    f_b = make_factor(code="FACTOR_B", value="1.0")
    calc_a = make_calculation(org=org_a, module_name="Elec Alpha", factor=f_a, kwh="1000")
    calc_b = make_calculation(org=org_b, module_name="Elec Beta", factor=f_b, kwh="2000")
    return {
        "org_a": org_a, "org_b": org_b,
        "module_a": calc_a.module, "module_b": calc_b.module,
        "calc_a": calc_a, "calc_b": calc_b,
    }
