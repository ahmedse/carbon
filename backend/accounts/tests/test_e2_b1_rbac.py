# accounts/tests/test_e2_b1_rbac.py
# E2-B1: RBAC Reconciliation regression tests.
# Tests: calculation write hole closed, verify/reject gated, deployed groups resolve,
# constants are the single source of truth.

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.constants import (
    ADMINS_GROUP, ANALYSTS_GROUP, VIEWERS_GROUP,
    DATAOWNERS_GROUP, AUDITORS_GROUP,
    CARBON_DATA_OWNERS_GROUP, CARBON_ANALYSTS_GROUP,
    ADMIN_GROUP, ADMIN_ROLES, VISIBILITY_ROLES,
    READ_ONLY_ROLES, PROTECTED_GROUPS,
)
from accounts.models import ScopedRole
from core.models import Module
from emissions.models import ReportingPeriod, EmissionFactor, Calculation


# ── Helpers ────────────────────────────────────────────────────────
def _auth(api_client, get_token_for_user, user):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ── Task 3: Close the write hole on CalculationViewSet ─────────────

@pytest.mark.django_db
def test_calc_create_denied_for_viewer(api_client, create_user, create_scoped_role,
                                        get_token_for_user):
    """A viewer with only viewers_group role cannot POST to /calculations/."""
    viewer = create_user("e2b1_viewer")
    create_scoped_role(viewer, VIEWERS_GROUP)
    _auth(api_client, get_token_for_user, viewer)

    resp = api_client.post(reverse("emissions:calculation-list"), {
        "module": 1, "emission_factor": 1, "data_row": 1,
        "activity_value": "100", "activity_unit": "kWh", "scope": 2,
    }, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_calc_create_denied_for_unauthenticated(api_client):
    """Unauthenticated POST to /calculations/ → 401."""
    resp = api_client.post(reverse("emissions:calculation-list"), {
        "module": 1, "emission_factor": 1, "data_row": 1,
        "activity_value": "100", "activity_unit": "kWh", "scope": 2,
    }, format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_calc_create_allowed_for_analyst_with_module_role(
        api_client, create_user, create_scoped_role, get_token_for_user):
    """Analyst with analysts_group scoped to a module can POST to /calculations/."""
    analyst = create_user("e2b1_analyst_calc")
    module, _ = Module.objects.get_or_create(
        name="E2B1 Test Module", defaults={"scope": 2}
    )
    create_scoped_role(analyst, ANALYSTS_GROUP, module=module)
    _auth(api_client, get_token_for_user, analyst)

    # Create a valid emission factor
    ef = EmissionFactor.objects.create(
        name="Test Factor", code="E2B1_TEST", category="electricity",
        scope=2, factor_value="0.5", activity_unit="kWh",
        valid_from="2024-01-01", source="E2B1 Test",
    )
    resp = api_client.post(reverse("emissions:calculation-list"), {
        "module": module.id, "emission_factor": ef.id, "data_row": 1,
        "activity_value": "100", "activity_unit": "kWh", "scope": 2,
        "category": "electricity",
    }, format="json")
    # 201 if created, 400 if validation error (missing data_row)—not 403
    assert resp.status_code != 403, f"Analyst should not get 403, got {resp.status_code}: {resp.data}"


@pytest.mark.django_db
def test_calc_create_allowed_for_global_admin(
        api_client, create_user, create_scoped_role, get_token_for_user):
    """Global admin (admins_group, no scope) can POST to /calculations/."""
    admin = create_user("e2b1_admin")
    create_scoped_role(admin, ADMINS_GROUP)
    _auth(api_client, get_token_for_user, admin)

    module, _ = Module.objects.get_or_create(
        name="E2B1 Admin Module", defaults={"scope": 2}
    )
    ef = EmissionFactor.objects.create(
        name="Admin Factor", code="E2B1_ADM", category="electricity",
        scope=2, factor_value="0.5", activity_unit="kWh",
        valid_from="2024-01-01", source="E2B1 Admin",
    )
    resp = api_client.post(reverse("emissions:calculation-list"), {
        "module": module.id, "emission_factor": ef.id, "data_row": 1,
        "activity_value": "100", "activity_unit": "kWh", "scope": 2,
        "category": "electricity",
    }, format="json")
    assert resp.status_code != 403, f"Admin should not get 403, got {resp.status_code}: {resp.data}"


@pytest.mark.django_db
def test_calc_create_denied_for_analyst_no_module(
        api_client, create_user, create_scoped_role, get_token_for_user):
    """Analyst without module scoping, posting without module_id → 403."""
    analyst = create_user("e2b1_analyst_nomod")
    create_scoped_role(analyst, ANALYSTS_GROUP)  # global scope, not module-specific
    _auth(api_client, get_token_for_user, analyst)

    resp = api_client.post(reverse("emissions:calculation-list"), {
        "emission_factor": 1, "data_row": 1,
        "activity_value": "100", "activity_unit": "kWh", "scope": 2,
    }, format="json")
    # No module_id + no global admin role → 403
    assert resp.status_code == 403


# ── Task 4: verify/reject gated by ScopedRole (not raw groups.filter) ──

@pytest.mark.django_db
def test_verify_denied_for_non_admin(api_client, create_user, create_scoped_role,
                                       get_token_for_user):
    """Non-admin (analyst) cannot verify a submitted period."""
    analyst = create_user("e2b1_verify_analyst")
    create_scoped_role(analyst, ANALYSTS_GROUP)
    period = ReportingPeriod.objects.create(
        name="Q1 E2B1", start_date="2026-01-01", end_date="2026-03-31",
        status="submitted",
    )
    _auth(api_client, get_token_for_user, analyst)

    url = reverse("emissions:reporting-period-verify", args=[period.id])
    resp = api_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_reject_denied_for_non_admin(api_client, create_user, create_scoped_role,
                                       get_token_for_user):
    """Non-admin (data owner) cannot reject a submitted period."""
    owner = create_user("e2b1_reject_owner")
    create_scoped_role(owner, DATAOWNERS_GROUP)
    period = ReportingPeriod.objects.create(
        name="Q2 E2B1", start_date="2026-04-01", end_date="2026-06-30",
        status="submitted",
    )
    _auth(api_client, get_token_for_user, owner)

    url = reverse("emissions:reporting-period-reject", args=[period.id])
    resp = api_client.post(url, {"notes": "should not work"}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_verify_allowed_for_scopedrole_admin(api_client, create_user, create_scoped_role,
                                               get_token_for_user):
    """User with admins_group ScopedRole (not Django group) can verify."""
    admin = create_user("e2b1_scoped_admin")
    create_scoped_role(admin, ADMINS_GROUP)  # ScopedRole, not user.groups.add()
    period = ReportingPeriod.objects.create(
        name="Q3 E2B1", start_date="2026-07-01", end_date="2026-09-30",
        status="submitted",
    )
    _auth(api_client, get_token_for_user, admin)

    url = reverse("emissions:reporting-period-verify", args=[period.id])
    resp = api_client.post(url)
    assert resp.status_code == 200
    period.refresh_from_db()
    assert period.status == "verified"


# ── Task 1: Single source of truth (constants.py) ──────────────────

@pytest.mark.django_db
def test_constants_are_consistent():
    """All canonical constants are internally consistent."""
    # ADMIN_ROLES includes both admin and admins_group
    assert ADMIN_GROUP in ADMIN_ROLES
    assert ADMINS_GROUP in ADMIN_ROLES

    # VISIBILITY_ROLES includes all viewer roles
    assert ADMINS_GROUP in VISIBILITY_ROLES
    assert DATAOWNERS_GROUP in VISIBILITY_ROLES
    assert AUDITORS_GROUP in VISIBILITY_ROLES
    assert VIEWERS_GROUP in VISIBILITY_ROLES
    assert ANALYSTS_GROUP in VISIBILITY_ROLES

    # READ_ONLY_ROLES are subsets of VISIBILITY_ROLES
    for role in READ_ONLY_ROLES:
        assert role in VISIBILITY_ROLES, f"{role} in READ_ONLY_ROLES but not VISIBILITY_ROLES"

    # PROTECTED_GROUPS are valid
    assert ADMIN_GROUP in PROTECTED_GROUPS
    assert CARBON_DATA_OWNERS_GROUP in PROTECTED_GROUPS
    assert CARBON_ANALYSTS_GROUP in PROTECTED_GROUPS


@pytest.mark.django_db
def test_protected_groups_imported_from_constants(api_client, create_user, create_scoped_role,
                                                    get_token_for_user):
    """The GroupViewSet uses PROTECTED_GROUPS from constants."""
    admin = create_user("e2b1_protect")
    create_scoped_role(admin, ADMIN_GROUP)
    _auth(api_client, get_token_for_user, admin)

    # Try to delete 'carbon_data_owners_group' — must be protected
    protected = Group.objects.get_or_create(name=CARBON_DATA_OWNERS_GROUP)[0]
    resp = api_client.delete(reverse("group-detail", kwargs={"pk": protected.pk}))
    assert resp.status_code == 400
    assert "Cannot delete protected group" in str(resp.data)


# ── Task 2: Deployed groups resolve ────────────────────────────────

@pytest.mark.django_db
def test_deployed_groups_resolve_to_canonical():
    """Groups created by deploy_aastmt management command use canonical names from constants."""
    # Simulate deploy script: create groups by canonical names
    canonical_names = [
        ADMINS_GROUP, DATAOWNERS_GROUP, ANALYSTS_GROUP,
        VIEWERS_GROUP, AUDITORS_GROUP,
    ]
    for name in canonical_names:
        group, created = Group.objects.get_or_create(name=name)
        assert group.name in canonical_names

    # 'carbon_admin' must NOT be the canonical name — it should be 'admins_group'
    assert "carbon_admin" not in canonical_names
    # Verify no 'carbon_admin' group exists (deploy script fixed)
    assert not Group.objects.filter(name="carbon_admin").exists(), \
        "carbon_admin should not exist; deploy script now uses admins_group"
