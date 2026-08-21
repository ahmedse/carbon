"""Phase 24-D — DQ feedback loop sweep (idempotent pipeline runner).

Applies pipeline effects to every captured ``DqFeedbackEvent`` that has not
been applied yet (``applied_at IS NULL``):

  * suggest_accepted/rejected → KgFeedbackRecord ledger (canonical promotion /
    explicit negative)
  * rule_corrected           → correction + KgGoldenPair candidate
  * result_always_pass / result_false_positive → needs_review flag (RULE_21:
    human confirmation, never auto-mutation)
  * drift_detected           → record only

Idempotent by construction: each event is applied exactly once (``applied_at``
guard + unique ``idempotency_key`` + deterministic ledger ``message_id``), so
re-running the sweep is always safe.

Modes (mirrors ``run_learning_loop.py``):

  * ``--run-once``    apply all pending events once, print stats JSON.
  * ``--status``      print the pending count JSON (no writes).
  * (default)         run an APScheduler interval job and block until
                      SIGINT/SIGTERM.
"""

import json
import logging
import signal

from django.conf import settings
from django.core.management.base import BaseCommand

from ai.feedback import apply_pending, pending_count

logger = logging.getLogger("carbon.ai.run_dq_feedback_loop")

DEFAULT_INTERVAL_SECONDS = 600


class Command(BaseCommand):
    help = (
        "Run the DQ feedback-loop sweep scheduler (default), apply pending "
        "events once (--run-once), or print the pending count (--status)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-once",
            action="store_true",
            help="Apply all pending events once and exit.",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Print the pending count JSON and exit.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=None,
            help="Sweep interval in seconds (overrides DQ_FEEDBACK_SWEEP_INTERVAL).",
        )

    def handle(self, *args, **options):
        if options["status"]:
            self.stdout.write(
                json.dumps({"pending": pending_count()})
            )
            return

        if options["run_once"]:
            self._run_once()
            return

        interval = (
            options["interval"]
            or getattr(settings, "DQ_FEEDBACK_SWEEP_INTERVAL", None)
            or DEFAULT_INTERVAL_SECONDS
        )
        self._run_scheduler(interval)

    def _run_once(self):
        applied = apply_pending()
        remaining = pending_count()
        self.stdout.write(
            json.dumps({"applied": applied, "remaining": remaining})
        )

    def _run_scheduler(self, interval: int):
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self._sweep,
            "interval",
            seconds=interval,
            id="dq_feedback_sweep",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        self.stdout.write(
            f"DQ feedback loop running — sweep every {interval}s "
            "(Ctrl-C to stop)."
        )

        stop = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, stop)
        try:
            import time

            while True:
                time.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown(wait=False)
            self.stdout.write("DQ feedback loop stopped.")

    def _sweep(self):
        try:
            self._run_once()
        except Exception:  # noqa: BLE001 — the scheduler must survive
            logger.exception("DQ feedback sweep failed")
