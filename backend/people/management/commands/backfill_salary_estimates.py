# people/management/commands/backfill_salary_estimates.py
# Re-applies the corrected salary_for() bands to all employees whose salary
# was set by the original (unrealistic 4000–8000 KWD) import bands.
# Only touches employees whose basic_salary is still one of the old flat values.
# ESTIMATED values — replace with real payroll data when available.
from decimal import Decimal
from django.core.management.base import BaseCommand

OLD_FLAT_VALUES = {
    Decimal("4000.000"), Decimal("4500.000"),
    Decimal("5000.000"), Decimal("6000.000"), Decimal("8000.000"),
}


class Command(BaseCommand):
    help = "Backfill realistic KWD salary estimates (replaces unrealistic 4000–8000 flat bands)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--all', action='store_true',
                            help='Update ALL employees, not just those with old flat values')

    def handle(self, *args, **options):
        from people.management.commands.import_gofsco_employees import salary_for
        from people.models import Employee

        qs = Employee.objects.select_related('position')
        if not options['all']:
            qs = qs.filter(basic_salary__in=OLD_FLAT_VALUES)

        updated = 0
        skipped = 0
        dist: dict[Decimal, int] = {}

        for emp in qs.iterator():
            title = emp.position.title if emp.position else emp.full_name
            new_sal = salary_for(title, is_kuwaiti=emp.kuwaitization)
            if new_sal == emp.basic_salary and not options['all']:
                skipped += 1
                continue
            dist[new_sal] = dist.get(new_sal, 0) + 1
            if not options['dry_run']:
                emp.basic_salary = new_sal
                emp.save(update_fields=['basic_salary'])
            updated += 1

        prefix = "[DRY RUN] " if options['dry_run'] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Updated {updated} employees, skipped {skipped} (already correct)"
        ))
        self.stdout.write("Salary distribution after update:")
        for sal in sorted(dist):
            self.stdout.write(f"  {sal:8.0f} KWD: {dist[sal]:4d} employees")
