"""Delete generated payroll artifacts on nibras_dev and commit named months.

Does not delete employees, users, org units, compensation lines, or rules.
"""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mdm.models import OrgUnit
from people.governance.sod import SUBJECT_PAYROLL_RUN, SUBJECT_WPS_FILING
from people.models import (
    ComplianceRule,
    LieuDay,
    PayrollRun,
    PayrollRunValidation,
    PayslipLine,
    SoDPreparation,
    WpsFiling,
)
from people.payroll_service import PayrollRunService, PayrollServiceError


def _snapshot_version(version):
    rows = {}
    for rule in ComplianceRule.objects.filter(version=version).order_by("rule_id", "pk"):
        rows[(rule.rule_id, rule.pk)] = json.dumps(rule.inputs_schema, sort_keys=True, default=str)
    return rows


class Command(BaseCommand):
    help = "Purge generated payroll rows on nibras_dev and commit the given months."

    def add_arguments(self, parser):
        parser.add_argument("--months", default="2026-10,2026-11,2026-12")
        parser.add_argument("--preparer", default="ahmed")
        parser.add_argument("--committer", default="admin")

    def handle(self, *args, **options):
        brand = (getattr(settings, "DJANGO_BRAND", None) or "").strip().lower()
        db_name = settings.DATABASES["default"]["NAME"]
        if brand != "nibras" or db_name != "nibras_dev":
            raise CommandError(f"refusing: brand={brand!r} database={db_name!r} (nibras_dev only)")

        root = OrgUnit.objects.filter(parent__isnull=True).order_by("id").first()
        if root is None or "GOFSCO" not in (root.name or ""):
            raise CommandError(f"refusing: root org is {getattr(root, 'name', None)!r}")

        User = get_user_model()
        preparer = User.objects.filter(username=options["preparer"]).first()
        committer = User.objects.filter(username=options["committer"]).first()
        if preparer is None or committer is None or preparer.pk == committer.pk:
            raise CommandError("need two distinct users")

        before_2026_1 = _snapshot_version("2026.1")
        before_2026_2 = _snapshot_version("2026.2")
        deleted = self._purge()
        self.stdout.write(f"deleted {deleted}")

        months = []
        for token in str(options["months"]).split(","):
            year_s, month_s = token.strip().split("-")
            year, month = int(year_s), int(month_s)
            start = date(year, month, 1)
            end = date(year, month, monthrange(year, month)[1])
            months.append((start, end))

        if (
            PayrollRun.objects.exists()
            or PayslipLine.objects.exists()
            or PayrollRunValidation.objects.exists()
            or WpsFiling.objects.exists()
            or LieuDay.objects.exists()
            or SoDPreparation.objects.filter(
                subject_type__in=(SUBJECT_PAYROLL_RUN, SUBJECT_WPS_FILING),
            ).exists()
        ):
            raise CommandError("payroll tables were not empty after purge")

        svc = PayrollRunService()
        for start, end in months:
            try:
                run = self._commit_month(svc, root, start, end, preparer, committer)
            except Exception as exc:  # noqa: BLE001 — report the month and continue
                self.stdout.write(self.style.ERROR(f"FAILED {start}→{end}: {exc}"))
                continue
            versions = list(
                run.lines.order_by("id").values_list(
                    "employee__employee_no", "line_type__code", "amount", "rule_id", "rule_version",
                )[:8]
            )
            self.stdout.write(self.style.SUCCESS(
                f"committed {start}→{end} run={run.pk} lines={run.lines.count()} "
                f"exceptions={len(run.exceptions or [])} sample={versions}"
            ))

        if _snapshot_version("2026.1") != before_2026_1:
            raise CommandError("version 2026.1 formula bytes changed")
        if _snapshot_version("2026.2") != before_2026_2:
            raise CommandError("version 2026.2 formula bytes changed")
        self.stdout.write(self.style.SUCCESS("2026.1 and 2026.2 formula bytes unchanged"))

    def _purge(self) -> dict:
        run_ids = list(PayrollRun.objects.values_list("pk", flat=True))
        wps_ids = list(WpsFiling.objects.filter(payroll_run_id__in=run_ids).values_list("pk", flat=True))
        # Also drop SoD left behind after an earlier run delete. Every remaining
        # payroll_run / wps_filing subject is a payroll artifact.
        counts = {
            "runs": len(run_ids),
            "lines": PayslipLine.objects.filter(payroll_run_id__in=run_ids).count(),
            "validations": PayrollRunValidation.objects.filter(payroll_run_id__in=run_ids).count(),
            "wps": len(wps_ids),
            "lieu": LieuDay.objects.filter(payroll_run_id__in=run_ids).count(),
            "sod_runs": SoDPreparation.objects.filter(subject_type=SUBJECT_PAYROLL_RUN).count(),
            "sod_wps": SoDPreparation.objects.filter(subject_type=SUBJECT_WPS_FILING).count(),
        }
        with transaction.atomic():
            SoDPreparation.objects.filter(subject_type=SUBJECT_PAYROLL_RUN).delete()
            SoDPreparation.objects.filter(subject_type=SUBJECT_WPS_FILING).delete()
            PayrollRun.objects.filter(pk__in=run_ids).update(source_run=None)
            PayrollRun.objects.filter(pk__in=run_ids).delete()
        return counts

    def _commit_month(self, svc, root, start, end, preparer, committer):
        run = PayrollRun.objects.create(
            org_unit=root, period_start=start, period_end=end, status="draft",
        )
        try:
            with transaction.atomic():
                svc.compute(run, user=preparer)
                run.refresh_from_db()
                result = svc.validate(run, user=preparer)
                run.refresh_from_db()
                if run.status != "validated":
                    findings = [
                        (row.get("rule_key"), row.get("sample_failures"))
                        for row in result.get("findings") or []
                        if not row.get("passed", True)
                    ]
                    raise PayrollServiceError(f"validate → {run.status}: {findings}")
                commit = svc.commit(run, user=committer)
                run.refresh_from_db()
                if run.status != "committed":
                    raise PayrollServiceError(f"commit → {run.status}: {commit}")
        except Exception:
            PayrollRun.objects.filter(pk=run.pk).delete()
            raise
        return run
