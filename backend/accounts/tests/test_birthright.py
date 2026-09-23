# ADR-0048 — birthright duty × org scope. Exception grants survive a move.

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from accounts.birthright import recalculate_birthright
from accounts.capabilities import get_user_capabilities
from accounts.models import DutyProfile, RoleAssignmentAuditLog, ScopedRole
from accounts.rbac_utils import visible_org_ids
from mdm.models import OrgUnit
from people.access_sync import sync_employee_access, sync_org_managers
from people.models import Employee, Position

User = get_user_model()


def _employee(org, no, **kwargs):
    user = User.objects.create_user(username=f"emp_{no}", password="TestPa_132")
    return Employee.objects.create(
        org_unit=org,
        employee_no=no,
        full_name=no,
        basic_salary="1000.000",
        join_date=date(2026, 1, 1),
        user=user,
        **kwargs,
    )


@pytest.mark.django_db
def test_manager_birthright_follows_reports_and_revokes():
    org = OrgUnit.objects.create(name="HR", slug="hr-br")
    manager = _employee(org, "M1")
    report = _employee(org, "R1", manager=manager)

    sync_employee_access(manager, trigger="test")
    role = ScopedRole.objects.get(user=manager.user, group__name="manager_group", org_unit=org)
    assert role.provenance == ScopedRole.PROVENANCE_BIRTHRIGHT
    assert role.is_active is True

    report.manager = None
    report.save(update_fields=["manager"])
    sync_employee_access(manager, trigger="test")
    role.refresh_from_db()
    assert role.is_active is False


@pytest.mark.django_db
def test_exception_grant_survives_recalculation():
    org = OrgUnit.objects.create(name="Ops", slug="ops-br")
    person = _employee(org, "E1")
    group, _ = Group.objects.get_or_create(name="manager_group")
    ScopedRole.objects.create(
        user=person.user,
        group=group,
        org_unit=org,
        provenance=ScopedRole.PROVENANCE_EXCEPTION,
        is_active=True,
    )
    sync_employee_access(person, trigger="test")
    row = ScopedRole.objects.get(user=person.user, group=group, org_unit=org)
    assert row.provenance == ScopedRole.PROVENANCE_EXCEPTION
    assert row.is_active is True


@pytest.mark.django_db
def test_position_profile_grants_and_drops_people_lead():
    org = OrgUnit.objects.create(name="People", slug="people-br")
    position = Position.objects.create(org_unit=org, code="HR-DIR", title="HR Director")
    DutyProfile.objects.create(
        position_code="HR-DIR", duty="people:lead", scope=DutyProfile.SCOPE_HOME,
    )
    person = _employee(org, "HR1", position=position)
    sync_employee_access(person, trigger="test")
    assert ScopedRole.objects.filter(
        user=person.user, group__name="people_lead", org_unit=org, is_active=True,
    ).exists()
    assert "people:view" in get_user_capabilities(person.user)

    other = Position.objects.create(org_unit=org, code="CLERK", title="Clerk")
    person.position = other
    person.save(update_fields=["position"])
    sync_employee_access(person, trigger="test")
    assert ScopedRole.objects.filter(
        user=person.user, group__name="people_lead", is_active=True,
    ).exists() is False
    user = person.user
    del user._cached_capabilities
    assert "people:view" not in get_user_capabilities(user)


@pytest.mark.django_db
def test_expired_assignment_is_not_a_live_capability():
    org = OrgUnit.objects.create(name="Fin", slug="fin-br")
    person = _employee(org, "F1")
    group, _ = Group.objects.get_or_create(name="people_lead")
    ScopedRole.objects.create(
        user=person.user,
        group=group,
        org_unit=None,
        provenance=ScopedRole.PROVENANCE_EXCEPTION,
        is_active=True,
        valid_to=timezone.localdate() - timedelta(days=1),
    )
    assert "people:view" not in get_user_capabilities(person.user)


@pytest.mark.django_db
def test_visible_org_ids_include_descendants():
    root = OrgUnit.objects.create(name="Co", slug="co-br")
    child = OrgUnit.objects.create(name="Dept", slug="dept-br", parent=root)
    person = _employee(root, "S1")
    recalculate_birthright(
        user=person.user,
        is_active=True,
        home_org_id=root.id,
        managed_org_ids=[root.id],
        trigger="test",
    )
    ids = visible_org_ids(person.user, "platform:manager")
    assert root.id in ids
    assert child.id in ids


@pytest.mark.django_db
def test_sod_refuses_marker_and_student_together():
    org = OrgUnit.objects.create(name="Exam", slug="exam-br")
    position = Position.objects.create(org_unit=org, code="GV-DUAL", title="Dual")
    DutyProfile.objects.create(
        position_code="GV-DUAL", duty="gradevance:student", scope=DutyProfile.SCOPE_GLOBAL,
    )
    DutyProfile.objects.create(
        position_code="GV-DUAL", duty="gradevance:marker", scope=DutyProfile.SCOPE_GLOBAL,
    )
    person = _employee(org, "GV1", position=position)
    sync_employee_access(person, trigger="test")
    live = set(
        ScopedRole.objects.filter(user=person.user, is_active=True).values_list("group__name", flat=True)
    )
    assert len(live & {"gradevance_students", "gradevance_markers"}) == 1
    assert RoleAssignmentAuditLog.objects.filter(user=person.user, action="refused").exists()


@pytest.mark.django_db
def test_org_unit_manager_grants_and_drops_team():
    org = OrgUnit.objects.create(name="Shared", slug="shared-br")
    person = _employee(org, "OM1")
    org.manager_employee_id = person.id
    org.save(update_fields=["manager_employee_id"])
    sync_org_managers([person.id], trigger="org_unit")
    assert ScopedRole.objects.filter(
        user=person.user, group__name="manager_group", org_unit=org, is_active=True,
    ).exists()
    org.manager_employee_id = None
    org.save(update_fields=["manager_employee_id"])
    sync_org_managers([person.id], trigger="org_unit")
    assert ScopedRole.objects.filter(
        user=person.user, group__name="manager_group", is_active=True,
    ).exists() is False
