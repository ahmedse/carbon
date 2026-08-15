"""Sprint 10 (Phase 9-C) — batch learning command.

Consumes unprocessed ``AIMessage`` feedback into the engine (KG feedback +
long-term memory) for all learnable outcomes.

    manage.py learn_from_feedback                 # process everything pending
    manage.py learn_from_feedback --limit 10      # process at most 10
    manage.py learn_from_feedback --dry-run       # count candidates, write nothing
"""

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Consume unprocessed AIMessage feedback into the engine (KG + long-term memory)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from ai.learning import learn_all_pending, LEARNABLE_OUTCOMES
        from ai.models import AIMessage

        if options["dry_run"]:
            qs = AIMessage.objects.filter(
                outcome__in=LEARNABLE_OUTCOMES, learned_at__isnull=True
            )
            self.stdout.write(f"pending: {qs.count()}")
            return

        stats = learn_all_pending(limit=options["limit"])
        self.stdout.write(json.dumps(stats))
