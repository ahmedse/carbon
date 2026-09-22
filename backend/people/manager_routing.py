# people/manager_routing.py
"""Guard ESS submissions that need a linked manager for workflow routing.

Leave / loan / attendance policies start with ``role=manager``. Resolution
order (see ``correspondence.routing.resolve_step_approvers``):

1. ``Employee.manager.user_id``
2. ``OrgUnit.manager_employee_id`` (walk parent chain) → that employee's user
   via ``mdm.org_unit_manager.resolve_org_unit_manager_user_id``

Without either, the FSM leaves ``current_approver_ids`` empty (unrouted).
Prefer a clear 400 at submit over a silent orphan in Team inbox.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from mdm.org_unit_manager import resolve_org_unit_manager_user_id


def _has_routable_manager(employee) -> bool:
    """True when line manager or org-unit manager can receive approvals."""
    if employee is None:
        return False
    manager = getattr(employee, 'manager', None)
    if getattr(employee, 'manager_id', None) and manager and getattr(manager, 'user_id', None):
        return True

    ou = getattr(employee, 'org_unit', None)
    if ou is None and getattr(employee, 'org_unit_id', None):
        from django.apps import apps
        OrgUnit = apps.get_model('mdm', 'OrgUnit')
        ou = OrgUnit.objects.filter(pk=employee.org_unit_id).only(
            'id', 'parent_id', 'manager_employee_id',
        ).first()
    return resolve_org_unit_manager_user_id(ou) is not None


def manager_routing_block_response(employee) -> Response | None:
    """Return a 400 Response when the employee cannot route to a manager, else None."""
    if employee is None:
        return Response(
            {
                'detail': 'No employee profile is linked to this account.',
                'error_kind': 'no_employee_profile',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    manager_id = getattr(employee, 'manager_id', None)
    manager = getattr(employee, 'manager', None)
    if manager_id and manager is not None and not getattr(manager, 'user_id', None):
        # Line manager set but unlinked — org-unit fallback may still work.
        if _has_routable_manager(employee):
            return None
        return Response(
            {
                'detail': (
                    'Your reporting manager has no linked login account. '
                    'Ask HR to link their user before submitting.'
                ),
                'error_kind': 'manager_no_user',
                'hints': {
                    'suggestion': 'Contact HR to link the manager user account.',
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if _has_routable_manager(employee):
        return None

    return Response(
        {
            'detail': (
                'No reporting manager is assigned. Ask HR to set your '
                'manager (or the org-unit manager) before submitting this request.'
            ),
            'error_kind': 'no_manager',
            'hints': {
                'suggestion': 'Contact HR to assign a reporting manager.',
            },
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
