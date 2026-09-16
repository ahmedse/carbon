# File: people/management/commands/normalize_employee_genders.py
# Legacy PAQ-4A command — Employee.gender is now a governed FK (NSR-7B /
# ADR-0027 ReferenceSet ``gender``). Free-text M/F normalization no longer
# applies; this command is retained as a no-op reporter for operators.

from django.core.management.base import BaseCommand

from people.models import Employee


class Command(BaseCommand):
    help = (
        "No-op since NSR-7B: Employee.gender is a governed ReferenceValue FK. "
        "Reports current gender FK coverage."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Accepted for compatibility; always a report-only command.",
        )

    def handle(self, *args, **options):
        total = Employee.objects.count()
        with_gender = Employee.objects.exclude(gender__isnull=True).count()
        blank = total - with_gender
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Employee.gender is governed (ReferenceSet 'gender'). "
                f"{total} employees: {with_gender} set, {blank} unset. "
                f"No free-text normalization performed."
            )
        )
