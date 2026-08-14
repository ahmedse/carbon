"""Phase D — run the conscious cognition loop scheduler (blocking command).

Modes:

  * ``--run-once <task>``  trigger a single cognition task synchronously and
    print its result envelope, then exit (used by smoke tests / ops).
  * ``--status``           print the in-process loop status JSON and exit.
  * (default)             start the APScheduler ``AsyncIOScheduler`` on a real
    asyncio event loop (``asyncio.run``) and block until SIGINT/SIGTERM.
    Signal handlers call ``stop_scheduler()`` and unblock the loop before
    returning.

``AsyncIOScheduler`` does **not** manage its own event loop — it schedules
coroutine jobs onto the loop of the thread that starts it.  The command
therefore runs a dedicated asyncio event loop, registers SIGINT/SIGTERM via
``loop.add_signal_handler``, and blocks on ``asyncio.Event().wait()`` until a
signal arrives.
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

        # Default: run the scheduler on a real asyncio event loop and block
        # until a termination signal.
        asyncio.run(self._run_scheduler_loop())

    async def _run_scheduler_loop(self):
        """Run the scheduler on a real asyncio loop until SIGINT/SIGTERM.

        ``AsyncIOScheduler`` schedules coroutine jobs onto the event loop of
        the thread that starts it, so a plain ``signal.pause()`` never yields
        to the loop and the jobs never fire.  We install signal handlers via
        ``loop.add_signal_handler`` and block on an ``asyncio.Event``.
        """
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _stop(signum):
            logger.info("Received signal %s — stopping cognition loop", signum)
            stop_scheduler()
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop, sig)
            except (NotImplementedError, RuntimeError, ValueError):
                # add_signal_handler is unavailable on some platforms (e.g.
                # Windows) or when the loop is already closed/not running.
                logger.warning("Cannot register signal handler for %s", sig)

        start_scheduler()
        try:
            await stop_event.wait()
        finally:
            stop_scheduler()
