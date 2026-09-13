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

from accounts.capabilities import ALL_CAPABILITIES, GROUP_CAPABILITIES, _expand_capabilities

from .models import Delegation

User = get_user_model()


def _users_with_capability(cap_key: str) -> list[int]:
    """Ordered list of active user ids that hold cap_key (superuser '*' counts).

    Resolved with a constant number of SQL queries (no per-user loop) by
    translating the rules in ``accounts.capabilities.get_user_capabilities``
    into set-based ScopedRole lookups:
      * active superusers always qualify (their capabilities are ``{"*"}``);
      * a GLOBAL wildcard group grants every known capability;
      * a GLOBAL non-wildcard group grants cap_key if its (expanded) caps contain it;
      * a SCOPED non-wildcard group grants cap_key if its (expanded) caps contain it
        (the flat check does not scope non-wildcard groups);
      * a SCOPED wildcard group grants ONLY view capabilities
        (action == "view" or action.startswith("view_")).

    ``derive_employee_capabilities`` is intentionally ignored: it never yields
    the capabilities resolved here (correspondence:admin / people:manage /
    correspondence:finance), so only superuser + ScopedRole membership matters.
    """
    ScopedRole = apps.get_model('accounts', 'ScopedRole')

    cap = ALL_CAPABILITIES.get(cap_key)
    is_view = bool(cap and (cap.action == 'view' or cap.action.startswith('view_')))

    full_groups: list[str] = []      # wildcard groups (grant every *known* capability)
    grantor_groups: list[str] = []   # non-wildcard groups whose caps include cap_key
    for name, gcaps in GROUP_CAPABILITIES.items():
        if '*' in gcaps:
            if cap is not None:
                full_groups.append(name)
        elif cap_key in _expand_capabilities(gcaps):
            grantor_groups.append(name)

    ids: set[int] = set(
        User.objects.filter(is_active=True, is_superuser=True).values_list('id', flat=True)
    )

    scoped = ScopedRole.objects.filter(is_active=True, user__is_active=True)

    # Global roles (org_unit IS NULL AND module IS NULL).
    global_q = Q(org_unit__isnull=True, module__isnull=True) & (
        Q(group__name__in=full_groups) | Q(group__name__in=grantor_groups)
    )
    ids.update(scoped.filter(global_q).values_list('user_id', flat=True))

    # Scoped roles (anything not global). Non-wildcard groups grant their full
    # set; wildcard groups grant only view capabilities.
    scoped_grant = Q(group__name__in=grantor_groups)
    if is_view:
        scoped_grant |= Q(group__name__in=full_groups)
    scoped_q = ~Q(org_unit__isnull=True, module__isnull=True) & scoped_grant
    ids.update(scoped.filter(scoped_q).values_list('user_id', flat=True))

    return sorted(ids)


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
