from django.core.management.base import BaseCommand

from gradevance.services.learning import ProposalMiner


class Command(BaseCommand):
    help = "Mine ExpertEdit events into draft GradeVance Proposals (HITL learning loop)."

    def handle(self, *args, **options):
        created = ProposalMiner().mine()
        self.stdout.write(self.style.SUCCESS(f"Mined {len(created)} draft proposal(s)."))
