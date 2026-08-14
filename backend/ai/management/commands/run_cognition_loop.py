"""Phase D — run the conscious cognition loop scheduler (blocking command).

Modes:

  * ``--run-once <task>``  trigger a single cognition task synchronously and
    print its result envelope, then exit (used by smoke tests / ops).
  * ``--status``           print the in-process loop status JSON and exit.
  * (default)             start the APScheduler ``AsyncIOScheduler`` (which
    manages its own event loop) and block until SIGINT/SIGTERM.  Signal
    handlers call ``stop_scheduler()`` before returning.

The scheduler's async event loop lives inside APScheduler's own background
thread, so the command only keeps the main thread alive with ``signal.pause()``.
"""

import asyncio
import json
import logging
import signal

from django.core.management.base import BaseCommand

from ai.engine.cognition.loop import (
    get_loop_status,
    start_scheduler,
    stop_scheduler,
    trigger_task,
)

logger = logging.getLogger("carbon.ai.run_cognition_loop")


class Command(BaseCommand):
    help = (
        "Run the conscious cognition loop scheduler (default), trigger one "
        "task (--run-once), or print loop status (--status)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-once",
            metavar="TASK",
            help="Trigger a single cognition task and exit (e.g. health_check).",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Print the loop status JSON and exit.",
        )

    def handle(self, *args, **options):
        if options["status"]:
            self.stdout.write(json.dumps(get_loop_status(), indent=2))
            return

        task = options["run_once"]
        if task:
            result = asyncio.run(trigger_task(task))
            self.stdout.write(json.dumps(result, indent=2))
            return

        # Default: start the scheduler and block until a termination signal.
        start_scheduler()

        def _stop(signum, frame):
            logger.info("Received signal %s — stopping cognition loop", signum)
            stop_scheduler()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        try:
            signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            stop_scheduler()
