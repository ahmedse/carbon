# File: people/access_sync.py
# Structural facts for one employee → accounts.birthright.
# Position title and org-unit name are not inputs.

from accounts.birthright import recalculate_birthright
from mdm.models import OrgUnit
from people.models import Employee


def managed_org_ids(employee) -> set:
    """Org units this person runs: units that name them, and their home unit when they have reports."""
    if not employee.is_active:
        return set()
    ids = set(
        OrgUnit.objects.filter(
            manager_employee_id=employee.pk, is_active=True,
        ).values_list("id", flat=True)
    )
    has_reports = Employee.objects.filter(manager=employee, is_active=True).exists()
    if has_reports and employee.org_unit_id:
        ids.add(employee.org_unit_id)
    return ids


def sync_employee_access(employee, *, trigger="employee", actor=None):
    """Recalculate birthright for ``employee`` from org, reports, and position code."""
    if employee is None or employee.user_id is None:
        return None
    position = getattr(employee, "position", None)
    if position is None and employee.position_id:
        position = employee.position
    code = position.code if position is not None else ""
    return recalculate_birthright(
        user=employee.user,
        is_active=bool(employee.is_active),
        home_org_id=employee.org_unit_id,
        managed_org_ids=managed_org_ids(employee),
        position_code=code,
        trigger=trigger,
        actor=actor,
    )


def sync_org_managers(employee_ids, *, trigger="org_unit", actor=None):
    """Recalculate birthright for the employees named as org-unit managers."""
    seen = set()
    for employee_id in employee_ids or ():
        if not employee_id or employee_id in seen:
            continue
        seen.add(employee_id)
        employee = Employee.objects.filter(pk=employee_id).select_related("user", "position").first()
        if employee is not None:
            sync_employee_access(employee, trigger=trigger, actor=actor)


def sync_employee_and_managers(employee, *, previous_manager_id=None, actor=None, trigger="employee"):
    """Sync this person, the manager they left, and the manager they report to now."""
    sync_employee_access(employee, trigger=trigger, actor=actor)
    seen = {employee.pk}
    for manager_id in (previous_manager_id, employee.manager_id):
        if not manager_id or manager_id in seen:
            continue
        seen.add(manager_id)
        manager = Employee.objects.filter(pk=manager_id).select_related("user", "position").first()
        if manager is not None:
            sync_employee_access(manager, trigger=trigger, actor=actor)
