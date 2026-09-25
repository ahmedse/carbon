"""Dev/Nibras: clean rubbish payroll runs and populate committed months for all employees.

How payslips work (ADR-0029 / NIR-3C):
  1. Verified compensation ledger holds monthly earnings (basic + allowances).
  2. PayrollRun for an org + period: draft → compute → validate → commit (SoD).
  3. Compute walks org + descendants, writes PayslipLine (gross / gosi / loan / net).
  4. My Payslips reads only validated|committed lines for the logged-in employee.

Usage (nibras / nibras_dev only)::

    python manage.py populate_payroll_history --months 12 --purge --reseed-compensation
    python manage.py populate_payroll_history --months 6 --dry-run
"""
from __future__ import annotations

import hashlib
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from mdm.models import OrgUnit
from people.compensation_service import CompensationService
from people.management.commands.import_gofsco_employees import salary_for
from people.models import CompensationComponent, Employee, EmployeeCompensation, PayrollRun, PayslipLine
from people.payroll_service import PayrollRunService, PayrollServiceError

ANNUAL_INCREASE = Decimal("0.04")  # ~4% typical Kuwait private-sector increment
HOUSING_PCT = Decimal("0.20")
TRANSPORT_FLOOR = Decimal("40")
TRANSPORT_CAP = Decimal("150")
QUANT = Decimal("0.001")


def _jitter(employee_no: str, span: Decimal = Decimal("0.06")) -> Decimal:
    """Deterministic ±span factor from employee_no (stable across runs)."""
    digest = hashlib.sha1(str(employee_no).encode("utf-8")).hexdigest()
    unit = int(digest[:8], 16) / 0xFFFFFFFF
    return (Decimal("1") - span) + (Decimal(str(unit)) * (span * 2))


def _money(value: Decimal) -> Decimal:
    return value.quantize(QUANT, rounding=ROUND_HALF_UP)


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
            "--reseed-compensation",
            action="store_true",
            help=(
                "Close overlapping/bogus ledger rows and rewrite verified basic + "
                "housing + transport with market rates and annual increments."
            ),
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
            f"purge={options['purge']} reseed={options['reseed_compensation']} dry_run={dry}"
        )

        cleaned = self._clean(purge=options["purge"], dry=dry)
        self.stdout.write(self.style.WARNING(f"cleaned runs={cleaned}"))

        if options["clean_only"]:
            return

        if options["reseed_compensation"]:
            n = self._reseed_compensation(dry=dry, admin=preparer)
            self.stdout.write(self.style.SUCCESS(f"compensation reseeded employees={n}"))
        else:
            ensured = self._ensure_verified_basics(dry=dry)
            self.stdout.write(f"ledger ensured={ensured}")

        if dry:
            periods = list(self._month_windows(months))
            self.stdout.write(
                f"dry-run would commit {len(periods)} periods at root for "
                f"{Employee.objects.filter(is_active=True).count()} employees"
            )
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
        PayslipLine.objects.filter(payroll_run__in=qs).delete()
        deleted, _ = qs.delete()
        return deleted

    def _component(self, code: str, *, name: str, sort_order: int) -> CompensationComponent:
        obj, _ = CompensationComponent.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "direction": "earning",
                "is_wps_relevant": True,
                "sort_order": sort_order,
                "is_active": True,
            },
        )
        return obj

    def _write_line(self, *, employee, component, amount, start, end, admin, note: str):
        line = EmployeeCompensation.objects.create(
            employee=employee,
            component=component,
            amount=_money(amount),
            frequency="monthly",
            effective_start=start,
            effective_end=end,
            is_verified=False,
            reason_note=note,
        )
        if admin is not None:
            CompensationService.verify_line(line, verified_by=admin)
        else:
            line.is_verified = True
            line.save(update_fields=["is_verified"])
        return line

    def _reseed_compensation(self, *, dry: bool, admin) -> int:
        """Rewrite basic/housing/transport from market title bands + annual steps."""
        basic_c = self._component("basic", name="Basic Salary", sort_order=10)
        housing_c = self._component("housing", name="Housing Allowance", sort_order=20)
        transport_c = self._component("transport", name="Transport Allowance", sort_order=30)
        today = timezone.localdate()
        codes = {"basic", "housing", "transport"}
        n = 0
        qs = (
            Employee.objects.filter(is_active=True)
            .select_related("position")
            .iterator()
        )
        for emp in qs:
            title = getattr(emp.position, "title", None) or ""
            band = salary_for(title, is_kuwaiti=bool(emp.kuwaitization))
            current_basic = _money(band * _jitter(emp.employee_no))
            # Cover the full history window even when join_date is recent/null
            # (ERP imports often leave join blank or stamp the load day).
            origin = date(today.year - 3, 1, 1)
            steps = 3
            start_basic = current_basic
            for _ in range(steps):
                start_basic = _money(start_basic / (Decimal("1") + ANNUAL_INCREASE))
            start_basic = max(start_basic, Decimal("80.000"))

            housing_ratio = HOUSING_PCT
            if emp.kuwaitization:
                housing_ratio = Decimal("0.25")
            elif current_basic < Decimal("300"):
                housing_ratio = Decimal("0.12")

            if dry:
                n += 1
                continue

            with transaction.atomic():
                # Dev-only rewrite: drop managed earning rows so history is clean.
                EmployeeCompensation.objects.filter(
                    employee=emp,
                    component__code__in=codes,
                ).delete()

                amount = start_basic
                year = origin.year
                while True:
                    step_start = date(year, 1, 1) if year > origin.year else origin
                    if step_start > today:
                        break
                    next_start = date(year + 1, 1, 1)
                    step_end = next_start - timedelta(days=1) if next_start <= today else None
                    housing = _money(amount * housing_ratio)
                    note = (
                        f"market reseed {title or 'untitled'} "
                        f"{'Kuwaiti' if emp.kuwaitization else 'expat'} "
                        f"y={year}"
                    )
                    self._write_line(
                        employee=emp, component=basic_c, amount=amount,
                        start=step_start, end=step_end, admin=admin, note=note,
                    )
                    self._write_line(
                        employee=emp, component=housing_c, amount=housing,
                        start=step_start, end=step_end, admin=admin,
                        note=f"housing {housing_ratio:.0%} of basic",
                    )
                    # Transport steps with basic so annual increases show on package.
                    step_transport = min(
                        TRANSPORT_CAP,
                        max(TRANSPORT_FLOOR, _money(amount * Decimal("0.08"))),
                    )
                    self._write_line(
                        employee=emp, component=transport_c, amount=step_transport,
                        start=step_start, end=step_end, admin=admin,
                        note="transport allowance",
                    )
                    if step_end is None:
                        break
                    amount = _money(amount * (Decimal("1") + ANNUAL_INCREASE))
                    year += 1

                emp.basic_salary = current_basic
                emp.save(update_fields=["basic_salary"])
            n += 1
        return n

    def _ensure_verified_basics(self, *, dry: bool) -> int:
        """Fill missing verified basic only — never invent a floor over a real band."""
        component = self._component("basic", name="Basic Salary", sort_order=10)
        admin = get_user_model().objects.filter(username="ahmed").first()
        as_of = timezone.localdate()
        n = 0
        for emp in Employee.objects.filter(is_active=True).select_related("position").iterator():
            if CompensationService.verified_basic_amount(emp, as_of=as_of) is not None:
                continue
            title = getattr(emp.position, "title", None) or ""
            raw = getattr(emp, "basic_salary", None)
            try:
                amt = Decimal(str(raw)) if raw not in (None, "") else Decimal("0")
            except Exception:  # noqa: BLE001
                amt = Decimal("0")
            if amt <= 0:
                amt = salary_for(title, is_kuwaiti=bool(emp.kuwaitization))
            if dry:
                n += 1
                continue
            line = EmployeeCompensation.objects.create(
                employee=emp,
                component=component,
                amount=_money(amt),
                frequency="monthly",
                effective_start=date(2024, 1, 1),
                is_verified=False,
                reason_note="ensure verified basic from title/basic_salary",
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
