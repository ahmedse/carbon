# File: people/management/commands/populate_leave_balances.py
# Force-fill LeaveEntitlement for all active employees (demo/dev/prod reset).
# Unlike propagate_leave_policies, this UPSERTS entitled_days even when a
# zero-balance row already exists.
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from mdm.models import ReferenceValue
from people.models import Employee, LeaveEntitlement

DEFAULTS = {
    "annual": Decimal("30"),
    "sick": Decimal("15"),
    "emergency": Decimal("5"),
    "unpaid": Decimal("90"),
    "maternity": Decimal("70"),
    "paternity": Decimal("3"),
}


class Command(BaseCommand):
    help = "Upsert leave entitlements for all active employees (years: current, next, 2026, 2027)."

    def handle(self, *args, **options):
        years = sorted({timezone.now().year, timezone.now().year + 1, 2026, 2027})
        types = {
            rv.code: rv
            for rv in ReferenceValue.objects.filter(reference_set__name="leave_type")
        }
        self.stdout.write(f"leave_types={list(types)} years={years}")
        emps = list(Employee.objects.filter(is_active=True))
        created = updated = 0
        with transaction.atomic():
            for emp in emps:
                for code, days in DEFAULTS.items():
                    ltype = types.get(code)
                    if not ltype:
                        continue
                    entitled = (
                        Decimal("42")
                        if code == "annual" and getattr(emp, "kuwaitization", False)
                        else days
                    )
                    for year in years:
                        obj, was_created = LeaveEntitlement.objects.update_or_create(
                            employee=emp,
                            year=year,
                            leave_type=ltype,
                            defaults={"entitled_days": entitled},
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"DONE emp={len(emps)} created={created} upserted={updated} "
            f"total={LeaveEntitlement.objects.count()}"
        ))
        e = Employee.objects.filter(employee_no="1067").first()
        if e:
            for y in (2026, 2027):
                ent = LeaveEntitlement.objects.filter(
                    employee=e, year=y, leave_type__code="annual"
                ).first()
                self.stdout.write(
                    f"1067 {y} entitled={getattr(ent, 'entitled_days', None)} "
                    f"used={getattr(ent, 'used_days', None)}"
                )
        zeros = LeaveEntitlement.objects.filter(
            leave_type__code="annual", year=2027, entitled_days__lte=0
        ).count()
        self.stdout.write(f"annual_2027_zero_or_neg={zeros}")
