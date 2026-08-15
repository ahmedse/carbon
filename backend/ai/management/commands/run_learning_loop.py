"""Sprint 11 — run the learning-feedback sweep scheduler (blocking command).

Retries any judged ``AIMessage`` whose outcome has not been consumed yet
(``learned_at IS NULL``) — typically transient engine failures from the
real-time trigger in ``CarbonIntelligence.record_feedback``.

Modes (mirrors ``run_cognition_loop.py``):

  * ``--run-once``    process all pending rows once and print stats JSON.
  * ``--status``      print the pending count JSON (no writes).
  * (default)         run an APScheduler ``AsyncIOScheduler`` interval job and
                      block until SIGINT/SIGTERM.

The sweep is a trivial DB retry, so unlike the cognition loop there is no
liveness heartbeat — ``restart: unless-stopped`` in ``docker-compose.yml`` is
the supervision boundary.
"""

import asyncio
import json
import logging
import signal

from django.conf import settings
from django.core.management.base import BaseCommand

from ai.learning import LEARNABLE_OUTCOMES, learn_all_pending
from ai.models import AIMessage

logger = logging.getLogger("carbon.ai.run_learning_loop")

DEFAULT_INTERVAL_SECONDS = 300


class Command(BaseCommand):
    help = (
        "Run the learning-feedback sweep scheduler (default), process pending "
        "rows once (--run-once), or print the pending count (--status)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-once",
            action="store_true",
            help="Process all pending rows once and exit.",
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
            help="Sweep interval in seconds (overrides LEARNING_SWEEP_INTERVAL).",
        )

    def handle(self, *args, **options):
        if options["status"]:
            pending = AIMessage.objects.filter(
                outcome__in=LEARNABLE_OUTCOMES, learned_at__isnull=True
            ).count()
            self.stdout.write(json.dumps({"pending": pending}))
            return

        if options["run_once"]:
            self.stdout.write(json.dumps(learn_all_pending()))
            return

        interval = options["interval"] or int(
            getattr(settings, "LEARNING_SWEEP_INTERVAL", DEFAULT_INTERVAL_SECONDS)
        )
        asyncio.run(self._run_scheduler_loop(interval))

    async def _run_scheduler_loop(self, interval: int) -> None:
        """Run an interval sweep job on a real asyncio loop until a signal."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        scheduler = AsyncIOScheduler()

        def _stop(signum):
            logger.info("Received signal %s — stopping learning loop", signum)
            scheduler.shutdown(wait=False)
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop, sig)
            except (NotImplementedError, RuntimeError, ValueError):
                logger.warning("Cannot register signal handler for %s", sig)

        scheduler.add_job(
            _sweep,
            "interval",
            seconds=interval,
            id="learning_sweep",
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        try:
            await stop_event.wait()
        finally:
            scheduler.shutdown(wait=False)


def _sweep() -> None:
    """Run one sweep; log outcome but never raise (so the job survives)."""
    try:
        stats = learn_all_pending()
        if stats["processed"] or stats["errors"]:
            logger.info("learning sweep: %s", stats)
    except Exception:  # noqa: BLE001 — keep the scheduler alive
        logger.exception("learning sweep failed")
