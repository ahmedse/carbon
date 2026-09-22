# correspondence/management/commands/reroute_orphaned_correspondence.py
"""Re-resolve submitted/in_review items stuck with empty current_approver_ids.

When leave/loan was submitted before Employee.manager was set, the FSM marks
the manager step ``unrouted`` and leaves ``current_approver_ids=[]``. After HR
assigns managers, this command calls ``fsm._reroute`` so Team inbox fills.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from correspondence.fsm import _reroute
from correspondence.models import Correspondence


class Command(BaseCommand):
    help = (
        "Reroute orphaned correspondence (empty current_approver_ids / "
        "unrouted manager step) after managers are assigned."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List orphans without writing.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        qs = Correspondence.objects.filter(
            status__in=["submitted", "in_review"],
        ).select_related("requester", "corr_type")

        orphans = []
        for corr in qs:
            ids = corr.current_approver_ids or []
            chain = corr.approver_chain or []
            step = chain[corr.current_step] if 0 <= corr.current_step < len(chain) else {}
            if not ids or step.get("unrouted"):
                orphans.append(corr)

        fixed = 0
        still = 0
        for corr in orphans:
            if dry_run:
                self.stdout.write(
                    f"  would reroute {corr.reference_no} "
                    f"req={getattr(corr.requester, 'username', None)} "
                    f"type={getattr(corr.corr_type, 'code', None)}"
                )
                continue
            # Ensure unrouted flag so _reroute runs (older rows may only have []).
            chain = list(corr.approver_chain or [])
            if 0 <= corr.current_step < len(chain):
                entry = dict(chain[corr.current_step])
                if not entry.get("unrouted") and not (corr.current_approver_ids or []):
                    entry["unrouted"] = True
                    chain[corr.current_step] = entry
                    corr.approver_chain = chain
                    corr.save(update_fields=["approver_chain"])
            ok = _reroute(corr)
            if ok:
                fixed += 1
                corr.refresh_from_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {corr.reference_no} → approvers={corr.current_approver_ids}"
                    )
                )
            else:
                still += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ✗ {corr.reference_no} still unrouted "
                        f"(requester may still lack manager.user)"
                    )
                )

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}orphans={len(orphans)} fixed={fixed} still_unrouted={still}"
            )
        )
