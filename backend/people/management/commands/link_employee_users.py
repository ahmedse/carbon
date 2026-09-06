# File: people/management/commands/link_employee_users.py
# Associate every Employee with a platform User account (self-service) and apply
# the employee/manager group structure.
#
# Group structure (ADR-0027 governed lookups + CBAC via accounts.ScopedRole):
#   employee_group  GLOBAL (org_unit=None)  → my:access + correspondence:submit
#                    = the base "my" app access for every employee.
#   employee_group  ORG-UNIT scoped          → emp → orgunit data visibility.
#   manager_group   ORG-UNIT scoped          → manager → orgunit (team view +
#                    approval actions), applied to employees who manage others.
#
# Deterministic username: emp_<employee_no> (lowercased, non-alnum → `_`).
# Default password: from EMPLOYEE_DEFAULT_PASSWORD env (or --password).
# Idempotent: reuses existing users by username, skips already-linked employees,
# and uses get_or_create for groups and ScopedRole assignments.
#
# Usage:
#   ./manage.py link_employee_users [--password <pwd>] [--dry-run]

import os
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from accounts.models import ScopedRole
from mdm.models import OrgUnit
from people.models import Employee

DEFAULT_PASSWORD = os.environ.get("EMPLOYEE_DEFAULT_PASSWORD", "")
EMPLOYEE_GROUP = "employee_group"
MANAGER_GROUP = "manager_group"


def _slug_username(employee_no: str) -> str:
    """Deterministic, URL-safe username from an employee number."""
    slug = re.sub(r"[^a-z0-9]+", "_", (employee_no or "").lower()).strip("_")
    return f"emp_{slug}" if slug else "emp"


class Command(BaseCommand):
    help = (
        "Link every Employee to a platform User (default password) and assign "
        "the employee/manager group structure via ScopedRole. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=(
                "Default password for created users "
                "(from EMPLOYEE_DEFAULT_PASSWORD env, or --password)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the DB.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        dry_run = options["dry_run"]

        if not password:
            raise CommandError(
                "No default password configured. Set EMPLOYEE_DEFAULT_PASSWORD "
                "or pass --password <pwd>."
            )

        User = get_user_model()

        employee_group, _ = Group.objects.get_or_create(name=EMPLOYEE_GROUP)
        manager_group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)

        # Manager signals: (a) has direct reports via the self FK, or (b) is the
        # OrgUnit.manager_employee_id soft-ref for their unit.
        direct_report_manager_ids = set(
            Employee.objects.filter(manager__isnull=False).values_list(
                "manager_id", flat=True
            )
        )
        manager_org_ids = set(
            OrgUnit.objects.filter(manager_employee_id__isnull=False).values_list(
                "manager_employee_id", flat=True
            )
        )

        stats = {
            "created_users": 0,
            "reused_users": 0,
            "linked": 0,
            "employee_global": 0,
            "employee_org": 0,
            "manager_org": 0,
        }

        for emp in Employee.objects.select_related("org_unit", "user").all():
            is_manager = (
                emp.id in direct_report_manager_ids or emp.id in manager_org_ids
            )

            if emp.user_id is not None:
                # Already linked — just ensure group/scoped-role coverage.
                user = emp.user
                stats["reused_users"] += 1
            else:
                username = _slug_username(emp.employee_no)
                user, was_created = User.objects.get_or_create(username=username)
                if was_created:
                    user.set_password(password)
                    user.is_active = bool(emp.is_active)
                    user.save(update_fields=["password", "is_active"])
                    stats["created_users"] += 1
                else:
                    # Reused an existing account by username (idempotent re-run).
                    stats["reused_users"] += 1
                if not dry_run:
                    emp.user = user
                    emp.save(update_fields=["user"])
                stats["linked"] += 1

            # Django auth group membership (visible in admin; legacy surface).
            if not dry_run:
                user.groups.add(employee_group)
                if is_manager:
                    user.groups.add(manager_group)

            # CBAC ScopedRole assignments (what capabilities actually resolve to).
            if dry_run:
                continue

            # 1) GLOBAL employee_group → "all employees → employeegroup" (my app).
            _, created = ScopedRole.objects.get_or_create(
                user=user,
                group=employee_group,
                org_unit=None,
                module=None,
                defaults={"is_active": True},
            )
            if created:
                stats["employee_global"] += 1

            # 2) ORG-UNIT employee_group → "emp → orgunit".
            if emp.org_unit_id is not None:
                _, created = ScopedRole.objects.get_or_create(
                    user=user,
                    group=employee_group,
                    org_unit=emp.org_unit,
                    module=None,
                    defaults={"is_active": True},
                )
                if created:
                    stats["employee_org"] += 1

            # 3) ORG-UNIT manager_group → "manager → orgunit".
            if is_manager and emp.org_unit_id is not None:
                _, created = ScopedRole.objects.get_or_create(
                    user=user,
                    group=manager_group,
                    org_unit=emp.org_unit,
                    module=None,
                    defaults={"is_active": True},
                )
                if created:
                    stats["manager_org"] += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] would process {Employee.objects.count()} employees "
                    f"({stats['linked']} to link; "
                    f"{stats['created_users']} new users)."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Employee→User link complete: "
                f"{stats['created_users']} users created, "
                f"{stats['reused_users']} reused, "
                f"{stats['linked']} employees linked."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ ScopedRoles: {stats['employee_global']} global employee_group, "
                f"{stats['employee_org']} org-unit employee_group, "
                f"{stats['manager_org']} org-unit manager_group."
            )
        )
