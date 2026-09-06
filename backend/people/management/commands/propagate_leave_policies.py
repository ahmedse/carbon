# File: people/management/commands/propagate_leave_policies.py
# Propagate leave-policy default entitlements to eligible employees (LPR-2A).
#
# Idempotent: re-runs are no-ops for employees who already have an entitlement
# for a given policy's leave type and year (existing ``entitled_days`` and
# ``policy`` provenance are never overwritten).
#
# Usage:
#   ./manage.py propagate_leave_policies --year 2026
#   ./manage.py propagate_leave_policies --policy-id 3 --dry-run
#   ./manage.py propagate_leave_policies --dry-run          # preview everything
#
# Cron (year-start propagation on 1 Jan at 00:00):
#   0 0 1 1 * /path/to/venv/bin/python /path/to/backend/manage.py propagate_leave_policies

from django.core.management.base import BaseCommand
from django.utils import timezone

from people.leave_policy_service import propagate_all_active, propagate_policy
from people.models import LeavePolicy


class Command(BaseCommand):
    help = (
        "Propagate leave-policy default entitlements to eligible employees. "
        "Idempotent — existing entitlements are never overwritten."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Target leave year (default: current year).",
        )
        parser.add_argument(
            "--policy-id",
            type=int,
            default=None,
            help="Propagate a single policy by id (default: all active policies).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview counts without writing anything.",
        )

    def handle(self, *args, **options):
        year = options["year"] or timezone.now().year
        policy_id = options["policy_id"]
        dry_run = options["dry_run"]

        mode = "DRY-RUN" if dry_run else "APPLY"

        if policy_id is not None:
            policy = LeavePolicy.objects.filter(pk=policy_id).first()
            if policy is None:
                self.stderr.write(f"LeavePolicy {policy_id} not found.")
                raise SystemExit(1)
            result = propagate_policy(policy, year=year, dry_run=dry_run)
            self._write_summary(result, mode, year)
            return

        result = propagate_all_active(year=year, dry_run=dry_run)
        self.stdout.write(self.style.MIGRATE_HEADING(f"[{mode}] Leave-policy propagation — year {year}"))
        self.stdout.write(
            f"eligible={result['eligible']} will_create={result['will_create']} "
            f"will_update={result['will_update']} skipped={result['skipped']} "
            f"created={result['created']} updated={result['updated']}"
        )
        for row in result["per_policy"]:
            self.stdout.write(
                f"  policy {row['policy_id']} ({row['name'] or 'unnamed'}): "
                f"eligible={row['eligible']} created={row.get('created', 0)} "
                f"updated={row.get('updated', 0)}"
            )

    def _write_summary(self, result, mode, year):
        self.stdout.write(self.style.MIGRATE_HEADING(f"[{mode}] Leave-policy propagation — year {year}"))
        self.stdout.write(
            f"eligible={result['eligible']} will_create={result['will_create']} "
            f"will_update={result['will_update']} skipped={result['skipped']} "
            f"created={result.get('created', 0)} updated={result.get('updated', 0)}"
        )
