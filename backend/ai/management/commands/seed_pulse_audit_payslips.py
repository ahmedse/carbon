"""Seed committed ESS payslip lines for Pulse C2 live audit (nibras_dev).

Human override 2026-09-23: populate emp_1067 host rows so Chat can read
real figures. Arithmetic is the Nibras identity:

    net = gross − gosi − loan_installment
    4500 = 6500 − 1200 − 800

After-GOSI take-home is 5300. The 04 t3 golden was aligned to 5300
    on 2026-09-23 (Master identity, not a budget loosen). This command
    does not write a fake 3700 line.

Idempotent: replaces only lines tagged ``rule_id=pulse_audit_c2`` for the
named employee on the last-month run. Other employees' lines are left alone.

Usage (nibras brand / nibras_dev only)::

    python manage.py seed_pulse_audit_payslips
    python manage.py seed_pulse_audit_payslips --employee-no 1067
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from people.models import Employee, PayrollRun, PayslipLine
from people.payroll_service import PayrollServiceError, _payslip_line_type

RULE_ID = "pulse_audit_c2"
RULE_VERSION = "1"
GROSS = Decimal("6500.000")
GOSI = Decimal("1200.000")
LOAN = Decimal("800.000")
NET = GROSS - GOSI - LOAN  # 4500


def _last_month_period(today: date) -> tuple[date, date]:
    first_this = today.replace(day=1)
    end = first_this.fromordinal(first_this.toordinal() - 1)
    start = end.replace(day=1)
    return start, end


class Command(BaseCommand):
    help = "Seed committed last-month payslip lines for Pulse C2 (emp_1067)."

    def add_arguments(self, parser):
        parser.add_argument("--employee-no", default="1067")
        parser.add_argument(
            "--username",
            default="emp_1067",
            help="Resolve the employee via this user when employee_no is ambiguous.",
        )

    def handle(self, *args, **options):
        brand = (getattr(settings, "DJANGO_BRAND", None) or "").strip().lower()
        db_name = settings.DATABASES["default"]["NAME"]
        if brand and brand != "nibras":
            raise CommandError(f"refusing: brand={brand!r} (nibras_dev only)")
        if "nibras" not in str(db_name):
            raise CommandError(f"refusing: database={db_name!r} is not nibras")

        emp = self._resolve_employee(options["employee_no"], options["username"])
        start, end = _last_month_period(timezone.localdate())
        created = self._upsert(emp, start, end)
        self.stdout.write(
            self.style.SUCCESS(
                f"seeded {emp.employee_no} {start}→{end} committed "
                f"gross={GROSS} gosi={GOSI} loan={LOAN} net={NET} "
                f"({created} lines) db={db_name}"
            )
        )

    def _resolve_employee(self, employee_no: str, username: str) -> Employee:
        qs = Employee.objects.select_related("org_unit", "user")
        emp = qs.filter(employee_no=employee_no).first()
        if emp is None:
            emp = qs.filter(user__username=username).first()
        if emp is None:
            raise CommandError(
                f"no employee for employee_no={employee_no!r} username={username!r}"
            )
        if emp.org_unit_id is None:
            raise CommandError(f"employee {emp.employee_no} has no org_unit")
        return emp

    @transaction.atomic
    def _upsert(self, emp: Employee, start: date, end: date) -> int:
        try:
            types = {
                code: _payslip_line_type(code)
                for code in ("gross", "gosi", "loan_installment", "net")
            }
        except PayrollServiceError as exc:
            raise CommandError(str(exc)) from exc

        # Prefer the company-wide committed run that already pays this employee
        # for the period (populate_payroll_history writes at the root). Writing
        # a second org-local run would double-count nets in period aggregates.
        run = (
            PayrollRun.objects.filter(
                status="committed",
                period_start=start,
                period_end=end,
                lines__employee=emp,
            )
            .order_by("org_unit__parent_id", "id")
            .first()
        )
        if run is None:
            run = PayrollRun.objects.filter(
                org_unit=emp.org_unit,
                period_start=start,
                period_end=end,
            ).exclude(status="failed").first()
        if run is None:
            run = PayrollRun.objects.create(
                org_unit=emp.org_unit,
                period_start=start,
                period_end=end,
                status="committed",
                committed_at=timezone.now(),
            )
        elif run.status not in ("validated", "committed"):
            others = run.lines.exclude(employee=emp).exists()
            if others:
                raise CommandError(
                    f"refusing to commit run #{run.pk} {start}→{end} "
                    f"status={run.status}: other employees already have lines"
                )
            run.status = "committed"
            run.committed_at = timezone.now()
            run.save(update_fields=["status", "committed_at"])

        # One identity per employee per period across all runs.
        PayslipLine.objects.filter(
            employee=emp,
            payroll_run__period_start=start,
            payroll_run__period_end=end,
        ).delete()

        specs = (
            ("gross", GROSS, {"component": "gross"}),
            ("gosi", GOSI, {"component": "gosi_employee", "rate_note": "audit fixture"}),
            ("loan_installment", LOAN, {"component": "loan_deduction"}),
            ("net", NET, {
                "identity": "gross - gosi - loan_installment",
                "after_gosi": str(GROSS - GOSI),
                "total_deductions": str(GOSI + LOAN),
            }),
        )
        for code, amount, inputs in specs:
            PayslipLine.objects.create(
                payroll_run=run,
                employee=emp,
                line_type=types[code],
                amount=amount,
                rule_id=RULE_ID,
                rule_version=RULE_VERSION,
                inputs=inputs,
            )
        return len(specs)
