"""``run_due_schedules`` — materialize due plan schedules (W6-E F-29).

Idempotent by design: only schedules whose ``next_run_at`` has passed are
considered, and each is claimed with an atomic compare-and-set so concurrent
invocations fire exactly once. Materialized runs are ``pending_approval``
(RULE_21) — nothing executes without approval. ``--dry-run`` lists what would
fire without creating anything.

Intended to run from cron (see ``manage.sh``) — no docker required::

    cd backend && ../.venv/bin/python manage.py run_due_schedules
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from ai.plans_service import PlansService


class Command(BaseCommand):
    help = (
        "Materialize due plan schedules into reviewable Runs (idempotent). "
        "Use --dry-run to preview without creating anything."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List due schedules without materializing any runs.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        result = PlansService().materialize_due_schedules(dry_run=dry_run)

        verb = "would materialize" if dry_run else "materialized"
        self.stdout.write(
            self.style.WARNING(
                f"[dry-run] {result['materialized']} due schedule(s) "
                f"{verb} — nothing was created."
            )
            if dry_run
            else self.style.SUCCESS(
                f"{result['materialized']} due schedule(s) materialized."
            )
        )
        for entry in result["runs"]:
            self.stdout.write(
                f"  schedule={entry['schedule_id'][:8]} "
                f"name={entry['name']!r} "
                + (f"run={entry['run_id']}" if entry.get("run_id") else "(preview)")
            )
