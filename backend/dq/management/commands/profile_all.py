"""
manage.py profile_all — Phase 1.7: Profile all active DataTables.

Usage:  python manage.py profile_all [--table-id=<id>]
"""
from django.core.management.base import BaseCommand
from dataschema.models import DataTable
from dq.services import profile_table

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Profile all active DataTables (or a single table with --table-id)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--table-id', type=int, default=None,
            help='Profile a single table by its ID'
        )
        parser.add_argument(
            '--module-id', type=int, default=None,
            help='Profile all tables within a given module'
        )

    def handle(self, *args, **options):
        table_id = options['table_id']
        module_id = options['module_id']

        if table_id:
            self.stdout.write(f'Profiling table id={table_id} ...')
            profile_table(table_id)
            self.stdout.write(self.style.SUCCESS(f'Done — table id={table_id}'))
            return

        qs = DataTable.objects.filter(is_archived=False)
        if module_id:
            qs = qs.filter(module_id=module_id)

        total = qs.count()
        self.stdout.write(f'Profiling {total} table(s)...')

        for idx, table in enumerate(qs.iterator(), start=1):
            self.stdout.write(f'  [{idx}/{total}] {table.name} (id={table.id}) ... ', ending='')
            try:
                profile_table(table.id)
                self.stdout.write(self.style.SUCCESS('OK'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'FAILED: {exc}'))
                logger.exception('profile_all failed for table %s', table.id)

        self.stdout.write(self.style.SUCCESS(f'All done — {total} table(s) processed.'))
