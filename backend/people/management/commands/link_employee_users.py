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

from django.core.management.base import BaseCommand, CommandError

from mdm.models import OrgUnit
from people.employee_user_service import get_default_password, provision_employee_user
from people.models import Employee

DEFAULT_PASSWORD = get_default_password()


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

            result = provision_employee_user(
                emp, password=password, is_manager=is_manager,
                commit=not dry_run,
            )
            if result.created:
                stats["created_users"] += 1
            else:
                stats["reused_users"] += 1
            if result.linked:
                stats["linked"] += 1
            stats["employee_global"] += result.employee_global
            stats["employee_org"] += result.employee_org
            stats["manager_org"] += result.manager_org

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
