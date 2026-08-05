"""
Management command to unlock all DataTables.
Usage: python manage.py unlock_tables
"""
from django.core.management.base import BaseCommand
from dataschema.models import DataTable


class Command(BaseCommand):
    help = 'Unlock all DataTables (is_locked=False)'

    def handle(self, *args, **options):
        count = DataTable.objects.filter(is_locked=True).count()
        DataTable.objects.update(is_locked=False)
        self.stdout.write(
            self.style.SUCCESS(f'Unlocked {count} DataTable(s).')
        )
