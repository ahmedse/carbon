"""Approver routing + delegation resolution for the Correspondence engine.

Phase OF-4.

Layering: ``correspondence`` is a CORE app and must never ``import people``.
``people.Employee`` is reached only via ``apps.get_model('people', 'Employee')``
inside the function (guarded with ``try/except LookupError``). Importing
``accounts.capabilities`` is allowed.
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from accounts.capabilities import has_capability

from .models import Delegation

User = get_user_model()


def _users_with_capability(cap_key: str) -> list[int]:
    """Ordered list of active user ids that hold cap_key (superuser '*' counts)."""
    ids = []
    for u in User.objects.filter(is_active=True).order_by('id'):
        if has_capability(u, cap_key):
            ids.append(u.id)
    return ids


def resolve_step_approvers(*, step, requester, org_unit=None) -> list[int]:
    """Map a WorkflowPolicyStep.role to an ordered list of user ids.

    - 'manager'        -> requester's Employee.manager.user_id (via
                          apps.get_model('people','Employee')); [] if no manager
    - 'specific_user'  -> [step.specific_user_id] (skip None)
    - 'any_admin'      -> _users_with_capability('correspondence:admin')
    - 'hr'             -> _users_with_capability('people:manage')
    - 'finance'        -> _users_with_capability('correspondence:finance')
    Apply skip_if_self (drop requester.id). Dedupe preserving order. Never import people.
    """
    role = step.role
    ids: list[int] = []
    if role == 'manager':
        Employee = apps.get_model('people', 'Employee')
        try:
            emp = Employee.objects.select_related('manager').filter(user_id=requester.id).first()
        except (LookupError, AttributeError):
            emp = None
        if emp and emp.manager_id and emp.manager.user_id:
            ids = [emp.manager.user_id]
    elif role == 'specific_user':
        if step.specific_user_id:
            ids = [step.specific_user_id]
    elif role == 'any_admin':
        ids = _users_with_capability('correspondence:admin')
    elif role == 'hr':
        ids = _users_with_capability('people:manage')
    elif role == 'finance':
        ids = _users_with_capability('correspondence:finance')
    # skip_if_self + dedupe preserving order
    if step.skip_if_self and requester and requester.id in ids:
        ids = [i for i in ids if i != requester.id]
    seen = set()
    out = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def apply_delegation(user_ids, *, corr_type=None, org_unit=None, now=None) -> list[int]:
    """Replace each approver id with its active delegate, honoring corr_type
    scope (null='all'), org_unit scope (null='all'), and date window. Returns
    updated ordered list. A delegator with no active delegation stays as-is."""
    now = now or timezone.now()
    result = []
    for uid in user_ids:
        q = Delegation.objects.filter(delegator_id=uid, is_active=True)
        q = q.filter(Q(corr_type=corr_type) | Q(corr_type__isnull=True))
        q = q.filter(Q(org_unit=org_unit) | Q(org_unit__isnull=True))
        q = q.filter(Q(from_date__isnull=True) | Q(from_date__lte=now))
        q = q.filter(Q(to_date__isnull=True) | Q(to_date__gte=now))
        d = q.order_by('created_at').first()
        result.append(d.delegate_id if d else uid)
    return result
