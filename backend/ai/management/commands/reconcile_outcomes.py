"""``reconcile_outcomes`` — run the reconciliation loop for awaiting steps.

Scans steps in ``awaiting_reconciliation`` and runs the authoritative
read-back loop from ``ai.reconciliation`` (P3-08). Idempotent and fail-closed:
an inconclusive read-back creates a durable escalation, never a re-run.

No Celery — run from cron (documented in ``ai/reconciliation.py``)::

    */5 * * * * cd /home/ahmed/ws/carbon/backend && /home/ahmed/ws/carbon/.venv/bin/python manage.py reconcile_outcomes

Use ``--limit N`` to bound the number of steps reconciled per invocation.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ai.reconciliation import (
    ACTION_ESCALATED,
    ACTION_RESOLVED_FAILED,
    ACTION_RESOLVED_SUCCEEDED,
    reconcile_pending,
)


class Command(BaseCommand):
    help = (
        "Reconcile outcome_unknown/awaiting_reconciliation run steps via "
        "authoritative read-back (never blind-retries)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of steps to reconcile (0 = all).",
        )

    def handle(self, *args, **options):
        limit = int(options.get("limit") or 0)
        results = reconcile_pending(limit=limit)

        succeeded = sum(1 for r in results if r.action == ACTION_RESOLVED_SUCCEEDED)
        failed = sum(1 for r in results if r.action == ACTION_RESOLVED_FAILED)
        escalated = sum(1 for r in results if r.action == ACTION_ESCALATED)
        other = len(results) - succeeded - failed - escalated

        self.stdout.write(
            self.style.SUCCESS(
                f"reconcile_outcomes: {len(results)} step(s) scanned — "
                f"{succeeded} succeeded, {failed} failed, "
                f"{escalated} escalated, {other} other."
            )
        )
        for r in results:
            self.stdout.write(
                f"  step={r.step_id} action={r.action}"
                + (f" escalation={r.escalation_id[:8]}" if r.escalation_id else "")
            )
