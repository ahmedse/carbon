"""
manage.py check_freshness — Phase 1.8: Check data freshness for all tables.

Usage:  python manage.py check_freshness
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from dataschema.models import DataTable, DataRow
from dq.models import FreshnessCheck, DQProfileConfig
from accounts.models import notify_event

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check data freshness for all active tables and create FreshnessCheck records'

    def add_arguments(self, parser):
        parser.add_argument('--table-id', type=int, help='Check a single table')
        parser.add_argument('--notify', action='store_true', help='Fire notifications for stale tables')

    def handle(self, *args, **options):
        config = DQProfileConfig.objects.first()
        default_threshold = config.freshness_threshold_hours if config else 24
        notify = options['notify']

        qs = DataTable.objects.filter(is_archived=False)
        if options.get('table_id'):
            qs = qs.filter(id=options['table_id'])

        total = qs.count()
        stale_count = 0
        self.stdout.write(f'Checking freshness for {total} table(s)...')

        for table in qs.iterator():
            # Find newest DataRow
            newest = DataRow.objects.filter(
                data_table=table, is_archived=False
            ).order_by('-created_at').first()

            last_ts = newest.created_at if newest else None
            now = timezone.now()

            if last_ts:
                age_hours = (now - last_ts).total_seconds() / 3600
                is_fresh = age_hours <= default_threshold
            else:
                age_hours = None
                is_fresh = True  # Empty table is not "stale"

            FreshnessCheck.objects.create(
                data_table=table,
                expected_max_age_hours=default_threshold,
                last_data_timestamp=last_ts,
                is_fresh=is_fresh,
            )

            status = 'fresh' if is_fresh else 'STALE'
            if not is_fresh:
                stale_count += 1
            self.stdout.write(f'  {table.name}: {status} (age={age_hours:.1f}h)' if age_hours else f'  {table.name}: empty')

            if notify and not is_fresh:
                try:
                    notify_event(
                        event_type='freshness_violation',
                        title=f'Stale data: {table.name}',
                        body=f'Table "{table.name}" has not been updated in {age_hours:.1f} hours '
                             f'(threshold: {default_threshold}h).',
                        severity='warning',
                        link=f'/dataschema/tables/{table.id}/',
                    )
                except Exception:
                    logger.exception('Failed to send freshness notification')

        summary = f'{total} checked, {stale_count} stale'
        self.stdout.write(self.style.SUCCESS(summary))
