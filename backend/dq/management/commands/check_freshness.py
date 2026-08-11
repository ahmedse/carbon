"""
manage.py check_freshness — Phase 1.8: Check data freshness for all tables.

Usage:  python manage.py check_freshness [--table-id=N] [--notify]
Logic lives in dq.services.check_freshness — shared with the freshness DQJob.
"""
from django.core.management.base import BaseCommand

from dq.services import check_freshness


class Command(BaseCommand):
    help = 'Check data freshness for all active tables and create FreshnessCheck records'

    def add_arguments(self, parser):
        parser.add_argument('--table-id', type=int, help='Check a single table')
        parser.add_argument('--notify', action='store_true', help='Fire notifications for stale tables')

    def handle(self, *args, **options):
        summary = check_freshness(
            table_id=options.get('table_id'),
            notify=options['notify'],
        )
        self.stdout.write(f'Checking freshness for {summary["total"]} table(s)...')
        for r in summary['results']:
            if r['age_hours'] is not None:
                status = 'fresh' if r['is_fresh'] else 'STALE'
                self.stdout.write(
                    f'  {r["table_name"]}: {status} (age={r["age_hours"]:.1f}h)'
                )
            else:
                self.stdout.write(f'  {r["table_name"]}: empty')
        self.stdout.write(self.style.SUCCESS(
            f'{summary["total"]} checked, {summary["stale"]} stale'
        ))

