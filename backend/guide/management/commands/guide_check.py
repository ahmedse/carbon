from django.core.management.base import BaseCommand, CommandError

from guide.contract import check_all


class Command(BaseCommand):
    help = "Check every domain_packs/<id>/guide pack against the guide contract."

    def handle(self, *args, **options):
        problems = check_all()
        for line in problems:
            self.stderr.write(line)
        if problems:
            raise CommandError(f"{len(problems)} guide contract problem(s)")
        self.stdout.write("guide contract: ok")
