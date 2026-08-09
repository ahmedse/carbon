"""
manage.py schema_snapshot — Phase 1.8: Snapshot table schemas and detect changes.

Usage:  python manage.py schema_snapshot [--table-id=N] [--notify]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from dataschema.models import DataTable, DataField
from dq.models import SchemaSnapshot, SchemaChange

import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Snapshot current table schemas and detect changes from previous snapshot'

    def add_arguments(self, parser):
        parser.add_argument('--table-id', type=int, help='Snapshot a single table')
        parser.add_argument('--notify', action='store_true', help='Fire notifications for schema changes')

    def handle(self, *args, **options):
        qs = DataTable.objects.filter(is_archived=False)
        if options.get('table_id'):
            qs = qs.filter(id=options['table_id'])

        total = qs.count()
        changes_detected = 0
        self.stdout.write(f'Snapshotting schema for {total} table(s)...')

        for table in qs.iterator():
            fields = DataField.objects.filter(data_table=table, is_active=True, is_archived=False)
            current_schema = {}
            for f in fields:
                current_schema[f.name] = {
                    'type': f.type,
                    'is_nullable': True,  # DataField has no is_nullable; default to True
                    'position': f.id,  # proxy for order
                }

            row_count = table.rows.filter(is_archived=False).count()

            new_snapshot = SchemaSnapshot.objects.create(
                data_table=table,
                column_schema=current_schema,
                row_count=row_count,
            )

            # Compare with previous snapshot
            prev = SchemaSnapshot.objects.filter(
                data_table=table
            ).exclude(id=new_snapshot.id).order_by('-snapshot_at').first()

            if prev and prev.column_schema:
                prev_cols = set(prev.column_schema.keys()) if isinstance(prev.column_schema, dict) else set()
                curr_cols = set(current_schema.keys())

                added = curr_cols - prev_cols
                dropped = prev_cols - curr_cols
                common = curr_cols & prev_cols

                for col in added:
                    SchemaChange.objects.create(
                        data_table=table,
                        snapshot_from=prev,
                        snapshot_to=new_snapshot,
                        change_type='added',
                        field_name=col,
                        old_definition=None,
                        new_definition=current_schema.get(col),
                    )
                    changes_detected += 1

                for col in dropped:
                    SchemaChange.objects.create(
                        data_table=table,
                        snapshot_from=prev,
                        snapshot_to=new_snapshot,
                        change_type='dropped',
                        field_name=col,
                        old_definition=prev.column_schema.get(col),
                        new_definition=None,
                    )
                    changes_detected += 1

                for col in common:
                    if prev.column_schema.get(col) != current_schema.get(col):
                        SchemaChange.objects.create(
                            data_table=table,
                            snapshot_from=prev,
                            snapshot_to=new_snapshot,
                            change_type='modified',
                            field_name=col,
                            old_definition=prev.column_schema.get(col),
                            new_definition=current_schema.get(col),
                        )
                        changes_detected += 1

                if added or dropped or any(
                    prev.column_schema.get(c) != current_schema.get(c) for c in common
                ):
                    self.stdout.write(
                        self.style.WARNING(
                            f'  {table.name}: {len(added)} added, {len(dropped)} dropped, '
                            f'{len([c for c in common if prev.column_schema.get(c) != current_schema.get(c)])} modified'
                        )
                    )

                    if options['notify']:
                        try:
                            from accounts.models import notify_event
                            notify_event(
                                event_type='schema_change',
                                title=f'Schema change: {table.name}',
                                body=f'Table "{table.name}" schema changed: '
                                     f'{len(added)} added, {len(dropped)} dropped columns.',
                                severity='info',
                                link=f'/dataschema/tables/{table.id}/',
                            )
                        except Exception:
                            logger.exception('Failed to send schema change notification')
                else:
                    self.stdout.write(f'  {table.name}: no changes')
            else:
                self.stdout.write(f'  {table.name}: initial snapshot ({len(current_schema)} columns)')

        self.stdout.write(self.style.SUCCESS(
            f'{total} snapshot(s) taken, {changes_detected} change(s) detected'
        ))
