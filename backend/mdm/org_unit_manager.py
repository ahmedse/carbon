# mdm/org_unit_manager.py
"""Resolve OrgUnit.manager_employee_id → linked User id (soft people ref).

Shared by correspondence routing and people ESS guards so the parent-walk
logic lives in one place (mdm owns OrgUnit; Employee is reached via
``apps.get_model`` — RULE_3 / no cross-app FK from mdm).
"""

from __future__ import annotations

from django.apps import apps


def resolve_org_unit_manager_user_id(org_unit) -> int | None:
    """Walk ``org_unit`` → parent until ``manager_employee_id`` has a linked user.

    Returns that employee's ``user_id``, or None if none found.
    """
    if org_unit is None:
        return None
    Employee = apps.get_model('people', 'Employee')
    OrgUnit = apps.get_model('mdm', 'OrgUnit')
    seen: set[int] = set()
    ou = org_unit
    while ou is not None:
        ou_id = getattr(ou, 'id', None)
        if ou_id is None or ou_id in seen:
            break
        seen.add(ou_id)
        mid = getattr(ou, 'manager_employee_id', None)
        if mid:
            try:
                mgr = (
                    Employee.objects.filter(pk=mid, is_active=True)
                    .only('id', 'user_id')
                    .first()
                )
            except (LookupError, AttributeError):
                mgr = None
            if mgr and mgr.user_id:
                return mgr.user_id
        parent_id = getattr(ou, 'parent_id', None)
        if not parent_id:
            break
        try:
            ou = OrgUnit.objects.filter(pk=parent_id).only(
                'id', 'parent_id', 'manager_employee_id',
            ).first()
        except (LookupError, AttributeError):
            break
    return None
