"""Dev/Nibras: clean rubbish payroll runs and populate committed months for all employees.

How payslips work (ADR-0029 / NIR-3C):
  1. Verified compensation ledger holds monthly ``basic`` (not Employee.basic_salary).
  2. PayrollRun for an org + period: draft → compute → validate → commit (SoD).
  3. Compute walks org + descendants, writes PayslipLine (gross / gosi / loan / net).
  4. My Payslips reads only validated|committed lines for the logged-in employee.

Usage (nibras / nibras_dev only)::

    python manage.py populate_payroll_history --months 12 --purge
    python manage.py populate_payroll_history --months 6 --dry-run
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from mdm.models import OrgUnit
from people.compensation_service import CompensationService
from people.models import CompensationComponent, Employee, EmployeeCompensation, PayrollRun, PayslipLine
from people.payroll_service import PayrollRunService, PayrollServiceError


class Command(BaseCommand):
    help = "Purge rubbish payroll runs and commit N months of payslips for all active employees."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=12, help="How many past calendar months to commit (default 12).")
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Delete ALL PayrollRun + PayslipLine before seeding (failed/draft/fragmented child runs).",
        )
        parser.add_argument(
            "--clean-only",
            action="store_true",
            help="Only delete failed + empty draft runs; do not seed.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        brand = (getattr(settings, "DJANGO_BRAND", None) or "").strip().lower()
        db_name = settings.DATABASES["default"]["NAME"]
        if brand and brand != "nibras":
            raise CommandError(f"refusing: brand={brand!r} (nibras_dev only)")
        if "nibras" not in str(db_name):
            raise CommandError(f"refusing: database={db_name!r} is not nibras")

        months = max(1, min(int(options["months"]), 36))
        dry = bool(options["dry_run"])
        root = OrgUnit.objects.filter(parent__isnull=True).order_by("id").first()
        if root is None:
            raise CommandError("no root OrgUnit")

        User = get_user_model()
        preparer = User.objects.filter(username="ahmed").first()
        committer = User.objects.filter(username="admin").first()
        if preparer is None or committer is None:
            raise CommandError("need users ahmed (preparer) and admin (committer) for SoD")
        if preparer.pk == committer.pk:
            raise CommandError("preparer and committer must be distinct")

        self.stdout.write(
            f"db={db_name} root={root.id}:{root.name} months={months} "
            f"purge={options['purge']} dry_run={dry}"
        )

        cleaned = self._clean(purge=options["purge"], dry=dry)
        self.stdout.write(self.style.WARNING(f"cleaned runs={cleaned}"))

        if options["clean_only"]:
            return

        ensured = self._ensure_verified_basics(dry=dry)
        self.stdout.write(f"ledger ensured={ensured}")

        if dry:
            periods = list(self._month_windows(months))
            self.stdout.write(f"dry-run would commit {len(periods)} periods at root for "
                              f"{Employee.objects.filter(is_active=True).count()} employees")
            return

        svc = PayrollRunService()
        committed = 0
        failed = 0
        for start, end in self._month_windows(months):
            try:
                self._seed_month(svc, root, start, end, preparer, committer)
                committed += 1
                self.stdout.write(self.style.SUCCESS(f"committed {start}→{end}"))
            except Exception as exc:  # noqa: BLE001 — report and continue months
                failed += 1
                self.stdout.write(self.style.ERROR(f"FAILED {start}→{end}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"DONE committed_months={committed} failed_months={failed} "
                f"runs={PayrollRun.objects.count()} lines={PayslipLine.objects.count()} "
                f"emps_with_lines="
                f"{PayslipLine.objects.filter(payroll_run__status='committed').values('employee').distinct().count()}"
            )
        )

    def _clean(self, *, purge: bool, dry: bool) -> int:
        if purge:
            qs = PayrollRun.objects.all()
        else:
            qs = PayrollRun.objects.filter(status__in=("failed", "draft"))
        n = qs.count()
        if dry:
            return n
        # Lines cascade or explicit — PayslipLine has FK to run; delete runs.
        PayslipLine.objects.filter(payroll_run__in=qs).delete()
        deleted, _ = qs.delete()
        return deleted

    def _ensure_verified_basics(self, *, dry: bool) -> int:
        component, _ = CompensationComponent.objects.get_or_create(
            code="basic",
            defaults={
                "name": "Basic Salary",
                "direction": "earning",
                "is_wps_relevant": True,
                "sort_order": 10,
                "is_active": True,
            },
        )
        admin = get_user_model().objects.filter(username="ahmed").first()
        as_of = timezone.localdate()
        n = 0
        for emp in Employee.objects.filter(is_active=True).iterator():
            if CompensationService.verified_basic_amount(emp, as_of=as_of) is not None:
                continue
            raw = getattr(emp, "basic_salary", None) or Decimal("2000.000")
            try:
                amt = Decimal(str(raw))
            except Exception:  # noqa: BLE001
                amt = Decimal("2000.000")
            if amt < Decimal("2000.000"):
                amt = Decimal("2000.000")
            if dry:
                n += 1
                continue
            line = EmployeeCompensation.objects.create(
                employee=emp,
                component=component,
                amount=amt,
                frequency="monthly",
                effective_start=date(2024, 1, 1),
                is_verified=False,
            )
            if admin is not None:
                CompensationService.verify_line(line, verified_by=admin)
            else:
                line.is_verified = True
                line.save(update_fields=["is_verified"])
            n += 1
        return n

    def _month_windows(self, months: int):
        today = timezone.localdate()
        y, m = today.year, today.month
        # Include the previous completed month and walk back; skip current partial month.
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        for _ in range(months):
            start = date(y, m, 1)
            end = date(y, m, monthrange(y, m)[1])
            yield start, end
            m -= 1
            if m == 0:
                m = 12
                y -= 1

    def _seed_month(self, svc, root, start, end, preparer, committer):
        existing = PayrollRun.objects.filter(
            org_unit=root,
            period_start=start,
            period_end=end,
            status__in=("draft", "computed", "validated", "committed"),
        ).first()
        if existing and existing.status == "committed":
            return existing
        if existing:
            existing.lines.all().delete()
            existing.status = "draft"
            existing.save(update_fields=["status"])
            run = existing
        else:
            run = PayrollRun.objects.create(
                org_unit=root,
                period_start=start,
                period_end=end,
                status="draft",
            )
        with transaction.atomic():
            svc.compute(run, user=preparer)
            run.refresh_from_db()
            result = svc.validate(run, user=preparer)
            run.refresh_from_db()
            if run.status != "validated":
                raise PayrollServiceError(
                    f"validate → {run.status}: {result.get('findings') or result}"
                )
            commit = svc.commit(run, user=committer)
            run.refresh_from_db()
            if run.status != "committed":
                raise PayrollServiceError(f"commit → {run.status}: {commit}")
        return run
