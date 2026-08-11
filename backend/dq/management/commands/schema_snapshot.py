"""
manage.py schema_snapshot — Phase 1.8: Snapshot table schemas and detect changes.

Usage:  python manage.py schema_snapshot [--table-id=N] [--notify]
Logic lives in dq.services.snapshot_schema — shared with the schema DQJob.
"""
from django.core.management.base import BaseCommand

from dq.services import snapshot_schema


class Command(BaseCommand):
    help = 'Snapshot current table schemas and detect changes from previous snapshot'

    def add_arguments(self, parser):
        parser.add_argument('--table-id', type=int, help='Snapshot a single table')
        parser.add_argument('--notify', action='store_true', help='Fire notifications for schema changes')

    def handle(self, *args, **options):
        summary = snapshot_schema(
            table_id=options.get('table_id'),
            notify=options['notify'],
        )
        self.stdout.write(f'Snapshotting schema for {summary["total"]} table(s)...')
        for r in summary['results']:
            if r['initial']:
                self.stdout.write(
                    f'  {r["table_name"]}: initial snapshot ({r["columns"]} columns)'
                )
            elif r['changes']:
                self.stdout.write(
                    self.style.WARNING(
                        f'  {r["table_name"]}: {r["added"]} added, {r["dropped"]} dropped, '
                        f'{r["modified"]} modified'
                    )
                )
            else:
                self.stdout.write(f'  {r["table_name"]}: no changes')

        self.stdout.write(self.style.SUCCESS(
            f'{summary["total"]} snapshot(s) taken, {summary["changes_detected"]} change(s) detected'
        ))

