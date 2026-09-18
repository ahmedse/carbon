from django.core.management.base import BaseCommand, CommandError

from gradevance.models import Proposal
from gradevance.services.pack_bump import PackBumpError, PackBumpService


class Command(BaseCommand):
    help = "Bump a TranslationDevice pack from an accepted GradeVance Proposal."

    def add_arguments(self, parser):
        parser.add_argument("proposal_id")
        parser.add_argument(
            "--source",
            default="engines/lct_semantics/naa_reflective_v1",
            help="Relative device pack path under domain_packs/eduos",
        )
        parser.add_argument("--no-canary", action="store_true")

    def handle(self, *args, **options):
        try:
            prop = Proposal.objects.get(pk=options["proposal_id"])
        except Proposal.DoesNotExist as exc:
            raise CommandError(str(exc)) from exc
        try:
            result = PackBumpService().bump_device_from_proposal(
                prop,
                source_pack_rel=options["source"],
                require_canary=not options["no_canary"],
            )
        except PackBumpError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Pack bump written: {result}"))
