# File: people/employee_user_service.py
# Provision platform User accounts for Employees (self-service onboarding).
#
# Single source of truth for the employee → user + group/ScopedRole structure.
# Used by (1) the employee create API (auto-provision on hire) and (2) the
# ``link_employee_users`` management command (backfill of pre-existing rows).
#
# Group structure (ADR-0027 governed lookups + CBAC via accounts.ScopedRole):
#   employee_group  GLOBAL (org_unit=None)  → my:access + correspondence:submit
#                    = the base "my" app access for every employee.
#   employee_group  ORG-UNIT scoped          → emp → orgunit data visibility.
#   manager_group   ORG-UNIT scoped          → manager → orgunit (team view +
#                    approval actions), applied to employees who manage others.
#
# Deterministic username: emp_<employee_no> (lowercased, non-alnum → `_`).
# Default password: from EMPLOYEE_DEFAULT_PASSWORD env (or a random password
# when auto-provisioning without an env default).

import os
import re
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.crypto import get_random_string

from accounts.models import ScopedRole

EMPLOYEE_GROUP = "employee_group"
MANAGER_GROUP = "manager_group"
DEFAULT_PASSWORD_ENV = "EMPLOYEE_DEFAULT_PASSWORD"


def slug_username(employee_no: str) -> str:
    """Deterministic, URL-safe username from an employee number."""
    slug = re.sub(r"[^a-z0-9]+", "_", (employee_no or "").lower()).strip("_")
    return f"emp_{slug}" if slug else "emp"


def get_default_password() -> str:
    """Default employee password from the environment (empty when unset)."""
    return os.environ.get(DEFAULT_PASSWORD_ENV, "") or ""


@dataclass
class ProvisionResult:
    """Outcome of provisioning a single employee's platform account."""

    user: object = None
    created: bool = False       # A brand-new User was created.
    linked: bool = False        # employee.user was assigned in this call.
    employee_global: int = 0    # New global employee_group ScopedRole count.
    employee_org: int = 0       # New org-unit employee_group ScopedRole count.
    manager_org: int = 0        # New org-unit manager_group ScopedRole count.
    initial_password: str = ""  # Set only when a random password was generated.


def provision_employee_user(
    employee,
    password=None,
    *,
    is_manager=False,
    commit=True,
    reset_password=False,
):
    """Create (or reuse) a platform User for ``employee`` and link it.

    Assigns the employee/manager group structure (Django auth groups + CBAC
    ``ScopedRole``): a global ``employee_group`` (my app baseline), an
    org-unit ``employee_group`` (employee → org-unit data), and — when
    ``is_manager`` — an org-unit ``manager_group``.

    Idempotent: reuses an existing account by username and never duplicates
    group/ScopedRole assignments. When ``commit=False`` nothing is written
    (dry-run) and counters reflect what *would* change.

    ``password``: the default password for newly created accounts. When empty
    a random password is generated and returned via ``initial_password``.
    When ``reset_password=True`` and ``password`` is set, existing users also
    receive that password (QA / demo credential refresh).

    Returns a :class:`ProvisionResult`.
    """
    User = get_user_model()
    result = ProvisionResult()

    username = slug_username(employee.employee_no)

    if not commit:
        # Dry-run: resolve without any side effects.
        result.user = employee.user or User.objects.filter(username=username).first()
        result.created = result.user is None
        result.linked = employee.user_id is None
        return result

    employee_group, _ = Group.objects.get_or_create(name=EMPLOYEE_GROUP)
    manager_group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)

    user = employee.user
    if user is None:
        user, result.created = User.objects.get_or_create(username=username)
        if result.created:
            if password:
                user.set_password(password)
            else:
                result.initial_password = get_random_string(length=12)
                user.set_password(result.initial_password)
            user.is_active = bool(employee.is_active)
            user.save(update_fields=["password", "is_active"])
        result.linked = True
        employee.user = user
        employee.save(update_fields=["user"])
    elif reset_password and password:
        user.set_password(password)
        user.is_active = bool(employee.is_active)
        user.save(update_fields=["password", "is_active"])
    result.user = user

    # Django auth group membership (visible in admin; legacy surface).
    user.groups.add(employee_group)
    if is_manager:
        user.groups.add(manager_group)

    # 1) GLOBAL employee_group → "all employees" (my app baseline).
    _, created = ScopedRole.objects.get_or_create(
        user=user,
        group=employee_group,
        org_unit=None,
        module=None,
        defaults={"is_active": True},
    )
    result.employee_global = int(created)

    # 2) ORG-UNIT employee_group → "employee → org unit".
    if employee.org_unit_id is not None:
        _, created = ScopedRole.objects.get_or_create(
            user=user,
            group=employee_group,
            org_unit=employee.org_unit,
            module=None,
            defaults={"is_active": True},
        )
        result.employee_org = int(created)

        # 3) ORG-UNIT manager_group → "manager → org unit".
        if is_manager:
            _, created = ScopedRole.objects.get_or_create(
                user=user,
                group=manager_group,
                org_unit=employee.org_unit,
                module=None,
                defaults={"is_active": True},
            )
            result.manager_org = int(created)

    return result
