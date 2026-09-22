# File: people/payroll_service.py
# Payroll-run orchestration service (NIR-3C).
#
# Drives a PayrollRun through draft → computed → validated → committed (or
# failed), composing the NIR-3B calculation_engine functions and gating commit
# on an independent DQ validation seam (docs/NIBRAS-MASTER-STRATEGY.md §8.2).
#
# RULE_3: this module imports only the people app's own engine/models plus
# django — never a sibling hosted app (emissions, healthy, dq, catalog,
# accounts). The validation seam delegates to ``people.validation.validate_run``
# (that is where ``dq`` enters); this module MUST NOT import ``dq`` directly.
#
# RULE_12: employees are selected by org scope — a run only ever includes
# employees whose ``org_unit`` is the run's org_unit or one of its descendants.
#
# ADR 0029: gross basic is resolved from the verified compensation ledger
# (``CompensationService.verified_basic_amount``), not ``Employee.basic_salary``.
# Fail closed when no verified monthly ``basic`` line exists for the period.
#
# ADR 0025 lineage seam: any payslip line derived from a governed measurement
# (an AttendanceRecord backed by a dataschema.DataRow) carries ``data_row_id`` /
# ``row_hash`` inside its ``inputs``.

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import calculation_engine
from .compensation_service import CompensationService
from .models import AttendanceRecord, ComplianceRule, Employee, PayslipLine

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


class PayrollServiceError(Exception):
    """Raised when a payroll run is asked to perform an illegal transition."""


_line_type_cache: dict[str, int] = {}


def _payslip_line_type(code: str):
    """Resolve a payslip_line_type ReferenceValue by code (cached by pk)."""
    cached_pk = _line_type_cache.get(code)
    if cached_pk is not None:
        from mdm.models import ReferenceValue
        try:
            return ReferenceValue.objects.get(pk=cached_pk)
        except ReferenceValue.DoesNotExist:
            _line_type_cache.pop(code, None)
    from mdm.governed import resolve_reference_value
    rv = resolve_reference_value('payslip_line_type', code, require_current=False)
    if rv is None:
        raise PayrollServiceError(
            f"payslip_line_type {code!r} is not seeded (NSR-7A / NSR-7B)"
        )
    _line_type_cache[code] = rv.pk
    return rv


def make_finding(rule_key, *, severity=SEVERITY_ERROR, passed=False, checked=0,
                 failed=0, sample_failures=None):
    """Build a single validation finding in the shape NIR-3D will persist.

    Mirrors ``PayrollRunValidation`` fields (rule_key / passed / checked /
    failed / sample_failures) plus a ``severity`` used by the commit gate.
    """
    return {
        "rule_key": rule_key,
        "severity": severity,
        "passed": bool(passed),
        "checked": int(checked),
        "failed": int(failed),
        "sample_failures": list(sample_failures or []),
    }


def has_error_findings(findings):
    """True if any finding is error-severity and failed (blocks commit)."""
    return any(
        f.get("severity") == SEVERITY_ERROR and not f.get("passed", True)
        for f in (findings or [])
    )


def _json_safe(value):
    """Recursively convert values to JSON-serializable types.

    Mirrors the ``emissions`` ``ef_snapshot`` convention: ``Decimal`` → ``str``
    and ``date``/``datetime``/``time`` → ISO-8601, so a ``PayslipLine.inputs``
    JSONField can store engine lineage breadcrumbs without raising
    ``TypeError: Object of type Decimal is not JSON serializable``.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_json_safe(v) for v in sorted(value, key=str)]
    return value


def summarize(findings):
    """Normalize a findings list into the structure NIR-3D's runner can fill."""
    findings = list(findings or [])
    error_count = sum(
        1 for f in findings
        if f.get("severity") == SEVERITY_ERROR and not f.get("passed", True)
    )
    return {
        "findings": findings,
        "has_errors": error_count > 0,
        "error_count": error_count,
    }


class ValidationSeam:
    """DQ validation seam (ADR 0025 / NIR-3D).

    Delegates to ``people.validation.validate_run``, which returns the findings
    list the service's commit gate consumes. This module MUST NOT import ``dq``
    directly (RULE_3) — ``dq`` enters in ``people.validation``.
    """

    def validate_run(self, run):
        """Return a list of finding dicts for the given run."""
        from .validation import validate_run as _validate_run

        return _validate_run(run)


class PayrollRunService:
    """Orchestrates a PayrollRun through its governed lifecycle.

    Status transitions (strict):

        draft ──compute──▶ computed ──validate──▶ validated ──commit──▶ committed
          ▲                    │                     │
          └──── (re-run) ──────┘                     └─── error findings ──▶ failed

    ``compute`` and ``commit`` both re-run the validation seam; ``commit`` only
    succeeds from ``validated`` and only when there are zero error-severity
    findings.
    """

    # operation → allowed starting statuses
    ALLOWED_TRANSITIONS = {
        "compute": ("draft", "failed"),
        "validate": ("computed",),
        "commit": ("validated",),
    }

    def __init__(self, validation_seam=None):
        self.validation_seam = validation_seam if validation_seam is not None else ValidationSeam()

    # --- status guard -----------------------------------------------------

    def _require_status(self, run, allowed):
        if run.status not in allowed:
            raise PayrollServiceError(
                f"PayrollRun #{run.pk} is '{run.status}'; "
                f"expected one of {sorted(allowed)}."
            )

    # --- org scope (RULE_12) ----------------------------------------------

    def _scoped_employees(self, run):
        """Employees whose org_unit is the run's org_unit or a descendant."""
        ids = run.org_unit.get_descendant_ids(include_self=True)
        return Employee.objects.filter(org_unit_id__in=ids)

    # --- compute -----------------------------------------------------------

    def compute(self, run, *, user=None):
        self._require_status(run, self.ALLOWED_TRANSITIONS["compute"])

        rules = ComplianceRule.objects
        gosi_rule = self._resolve_rule(rules, "gosi")
        loan_rule = self._resolve_rule(rules, "other", formula_type="loan_schedule")
        net_rule = self._resolve_rule(rules, "other", formula_type="net_pay")

        employees = list(self._scoped_employees(run))
        with transaction.atomic():
            run.lines.all().delete()
            lines_created = 0
            for employee in employees:
                lines_created += self._compute_employee(
                    run, employee, gosi_rule, loan_rule, net_rule
                )
            run.status = "computed"
            run.save(update_fields=["status"])
            from people.governance.sod import (
                SUBJECT_PAYROLL_RUN,
                record_preparer,
            )

            record_preparer(
                subject_type=SUBJECT_PAYROLL_RUN,
                subject_id=run.pk,
                user=user,
                process_key="payroll.run.lifecycle",
            )

        return {
            "run": run.pk,
            "status": run.status,
            "employees": len(employees),
            "lines_created": lines_created,
        }

    def _compute_employee(self, run, employee, gosi_rule, loan_rule, net_rule):
        rules = ComplianceRule.objects
        created = 0

        # 1. gross — basic from verified ledger (ADR-0029); fail closed if missing.
        basic = CompensationService.verified_basic_amount(
            employee, as_of=run.period_end,
        )
        if basic is None:
            raise PayrollServiceError(
                f"Employee {employee.employee_no} has no verified monthly "
                f"'basic' compensation ledger line for period ending "
                f"{run.period_end}; refusing to compute payroll from "
                f"Employee.basic_salary."
            )
        measurements = self._attendance_measurements(employee, run)
        gross_inputs = {"basic": basic, "basic_source": "ledger"}
        if measurements:
            gross_inputs["measurements"] = measurements
            if len(measurements) == 1:
                gross_inputs["data_row_id"] = measurements[0]["data_row_id"]
                gross_inputs["row_hash"] = measurements[0]["row_hash"]
        gross = calculation_engine.calculate_gross_pay(employee, gross_inputs, rules)
        self._line_from_result(run, employee, "gross", gross)
        created += 1

        # 2. GOSI contribution (employee share becomes a net deduction).
        gosi = calculation_engine.calculate_gosi(gosi_rule, gross["value"])
        self._line_from_result(run, employee, "gosi", gosi)
        created += 1
        employee_share = gosi["lineage"].get("employee_share", Decimal("0"))

        # 3. loan installments due this period.
        # Hybrid (NSR-3A): prefer persisted LoanInstallment rows due in the
        # period when any exist for the loan; fall back to in-memory engine
        # schedule when the loan has no materialized rows yet.
        deductions = [employee_share]
        for loan in employee.loans.filter(status="active"):
            schedule, installment = self._loan_installment_for_run(
                loan, loan_rule, run,
            )
            if installment is None:
                continue
            self._loan_line(run, employee, schedule, installment)
            created += 1
            deductions.append(installment["amount"])

        # 4. net pay = gross − (GOSI employee share + loan installments).
        net = calculation_engine.calculate_net_pay(net_rule, gross["value"], deductions)
        self._line_from_result(run, employee, "net", net)
        created += 1

        return created

    # --- line writers ------------------------------------------------------

    def _line_from_result(self, run, employee, line_type, result):
        lineage = result["lineage"]
        self._create_line(
            run, employee, line_type, result["value"],
            lineage["rule_id"], lineage["rule_version"], lineage["inputs"],
        )

    def _loan_line(self, run, employee, schedule, installment):
        lineage = schedule["lineage"]
        inputs = dict(lineage["inputs"])
        inputs["installment_no"] = installment["installment_no"]
        inputs["principal_portion"] = str(installment["principal_portion"])
        inputs["interest_portion"] = str(installment["interest_portion"])
        self._create_line(
            run, employee, "loan_installment", installment["amount"],
            lineage["rule_id"], lineage["rule_version"], inputs,
        )

    def _create_line(self, run, employee, line_type, amount, rule_id, rule_version, inputs):
        if isinstance(line_type, str):
            line_type = _payslip_line_type(line_type)
        PayslipLine.objects.create(
            payroll_run=run,
            employee=employee,
            line_type=line_type,
            amount=amount,
            rule_id=rule_id,
            rule_version=rule_version,
            inputs=_json_safe(inputs),
        )

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _resolve_rule(rules, category, formula_type=None):
        """Return the active AUTHORITATIVE rule for a category (optionally a formula type).

        Regulated payroll figures (GOSI, loan schedule, net pay) may only be
        computed from authoritative rules — the same contract the calculation
        engine's ``_guard`` enforces. Non-authoritative demo/test rows are
        skipped so they can never be selected for a live payroll run.
        """
        qs = rules.filter(category__code=category, is_authoritative=True).order_by("-effective_date", "-updated_at")
        if formula_type is None:
            return qs.first()
        for rule in qs:
            formula = (rule.inputs_schema or {}).get("formula") or {}
            if formula.get("type") == formula_type:
                return rule
        return None

    def _attendance_measurements(self, employee, run):
        """Collect governed-measurement provenance for attendance in the period."""
        measurements = []
        records = AttendanceRecord.objects.filter(
            employee=employee,
            date__range=(run.period_start, run.period_end),
        ).select_related("source_row")
        for record in records:
            if record.source_row_id is None:
                continue
            measurements.append({
                "data_row_id": record.source_row_id,
                "row_hash": record.source_row.row_hash,
                "date": str(record.date),
                "hours_worked": str(record.hours_worked),
                "overtime_hours": str(record.overtime_hours),
            })
        return measurements

    @staticmethod
    def _installment_for_period(schedule, loan, run):
        """Pick the installment whose month matches the run's period_start."""
        installments = schedule["installments"]
        months = (
            (run.period_start.year - loan.start_date.year) * 12
            + (run.period_start.month - loan.start_date.month)
        )
        if months < 0 or months >= len(installments):
            return None
        return installments[months]

    def _loan_installment_for_run(self, loan, loan_rule, run):
        """Resolve the due installment for ``loan`` in ``run``'s period.

        Prefer a persisted ``LoanInstallment`` whose due month matches the
        run period when the loan has any materialized rows. Otherwise
        recompute via ``calculate_loan_schedule`` (legacy / pre-NSR-3A path).
        """
        if loan.installments.exists():
            row = loan.installments.filter(
                due_date__year=run.period_start.year,
                due_date__month=run.period_start.month,
            ).first()
            if row is None:
                return None, None
            schedule = {
                "lineage": {
                    "rule_id": loan_rule.rule_id if loan_rule else "",
                    "rule_version": loan_rule.version if loan_rule else "",
                    "inputs": {
                        "principal": loan.principal,
                        "interest_rate": loan.interest_rate,
                        "term_months": loan.term_months,
                        "source": "persisted_loan_installment",
                        "loan_installment_id": row.pk,
                    },
                },
            }
            installment = {
                "installment_no": row.installment_no,
                "amount": row.amount,
                "principal_portion": row.principal_portion,
                "interest_portion": row.interest_portion,
            }
            return schedule, installment

        schedule = calculation_engine.calculate_loan_schedule(loan_rule, loan)
        return schedule, self._installment_for_period(schedule, loan, run)

    # --- validate ----------------------------------------------------------

    def validate(self, run, *, user=None):
        self._require_status(run, self.ALLOWED_TRANSITIONS["validate"])
        from people.governance.sod import (
            SUBJECT_PAYROLL_RUN,
            get_preparer,
            record_preparer,
        )

        # Fill preparer only if compute stamped nothing (legacy / edge).
        if get_preparer(subject_type=SUBJECT_PAYROLL_RUN, subject_id=run.pk) is None:
            record_preparer(
                subject_type=SUBJECT_PAYROLL_RUN,
                subject_id=run.pk,
                user=user,
                process_key="payroll.run.lifecycle",
            )
        result = self._run_validation(run)
        run.status = "failed" if result["has_errors"] else "validated"
        run.save(update_fields=["status"])
        result["run"] = run.pk
        result["status"] = run.status
        return result

    # --- commit ------------------------------------------------------------

    def commit(self, run, *, user=None):
        self._require_status(run, self.ALLOWED_TRANSITIONS["commit"])
        from people.governance.sod import (
            ACTION_COMMIT,
            SUBJECT_PAYROLL_RUN,
            require_distinct_actor,
        )

        require_distinct_actor(
            subject_type=SUBJECT_PAYROLL_RUN,
            subject_id=run.pk,
            actor=user,
            action=ACTION_COMMIT,
        )
        result = self._run_validation(run)
        if result["has_errors"]:
            run.status = "failed"
            run.save(update_fields=["status"])
            result["run"] = run.pk
            result["status"] = run.status
            return result
        run.status = "committed"
        run.committed_at = timezone.now()
        run.save(update_fields=["status", "committed_at"])
        result["run"] = run.pk
        result["status"] = run.status
        return result

    def _run_validation(self, run):
        findings = self.validation_seam.validate_run(run)
        return summarize(findings)

    # --- WPS export ---------------------------------------------------------

    def wps_export(self, run):
        """Build WPS records for a committed run from the active WPS rule.

        Refuses (``PayrollServiceError``) unless an *authoritative* WPS rule is
        configured — no regulated figure is ever fabricated. Returns
        ``{"rule": rule, "records": [format_wps_record(...), ...]}``; each
        record is the engine's ``{value, lineage, record}`` payload.
        """
        self._require_status(run, ("committed",))
        rule = self._resolve_rule(ComplianceRule.objects, "wps")
        if rule is None:
            raise PayrollServiceError("No WPS compliance rule is configured.")
        if not rule.is_authoritative:
            raise PayrollServiceError(
                f"WPS rule '{rule.rule_id} v{rule.version}' is non-authoritative; "
                "refusing to generate a WPS file."
            )

        lines = list(run.lines.select_related("employee"))
        records = []
        for employee in self._scoped_employees(run):
            employee_lines = [ln for ln in lines if ln.employee_id == employee.id]
            payslip = self._payslip_summary(employee, run, employee_lines)
            records.append(calculation_engine.format_wps_record(rule, payslip))
        return {"rule": rule, "records": records}

    # --- GOSI/WPS SIF filing lifecycle (generate → validate → submit) -------

    def wps_generate(self, run, *, user=None):
        """Generate and persist SIF/WPS artifact for a committed run."""
        import csv
        import hashlib
        import io

        from django.utils import timezone

        from people.governance.sod import (
            SUBJECT_WPS_FILING,
            record_preparer,
        )
        from people.models import WpsFiling

        export = self.wps_export(run)
        records = export["records"]
        if not records:
            csv_text = ""
        else:
            columns = list(records[0]["record"].keys())
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(columns)
            for item in records:
                record = item["record"]
                writer.writerow([record.get(col, "") for col in columns])
            csv_text = buf.getvalue()
        raw = csv_text.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        filing, _ = WpsFiling.objects.update_or_create(
            payroll_run=run,
            defaults={
                "status": "generated",
                "content_hash": digest,
                "record_count": len(records),
                "csv_bytes": raw,
                "generated_at": timezone.now(),
                "validated_at": None,
                "validation_passed": False,
                "validation_issues": [],
                "submitted_at": None,
                "submitted_by": None,
                "receipt_id": "",
                "reconciled": False,
            },
        )
        # New generate cycle resets preparer (overwrite).
        record_preparer(
            subject_type=SUBJECT_WPS_FILING,
            subject_id=filing.pk,
            user=user,
            process_key="gosi_wps.sif.lifecycle",
            overwrite=True,
        )
        return {
            "run_id": run.pk,
            "status": filing.status,
            "content_hash": filing.content_hash,
            "record_count": filing.record_count,
            "generated_at": filing.generated_at.isoformat() if filing.generated_at else None,
            "bytes": len(raw),
        }

    def wps_validate_filing(self, run, *, user=None):
        """Validate a generated WPS filing (structure + authoritative rule)."""
        from django.utils import timezone

        from people.governance.sod import (
            SUBJECT_WPS_FILING,
            get_preparer,
            record_preparer,
        )
        from people.models import WpsFiling

        self._require_status(run, ("committed",))
        try:
            filing = run.wps_filing
        except WpsFiling.DoesNotExist as exc:
            raise PayrollServiceError(
                "No WPS filing generated for this run — call generate first."
            ) from exc
        if filing.status == "submitted":
            raise PayrollServiceError("Filing already submitted; cannot re-validate.")

        if get_preparer(subject_type=SUBJECT_WPS_FILING, subject_id=filing.pk) is None:
            record_preparer(
                subject_type=SUBJECT_WPS_FILING,
                subject_id=filing.pk,
                user=user,
                process_key="gosi_wps.sif.lifecycle",
            )

        issues = []
        if not filing.csv_bytes or filing.record_count < 1:
            issues.append({"code": "empty_artifact", "detail": "Generated SIF has no records."})
        if not filing.content_hash:
            issues.append({"code": "missing_hash", "detail": "Generated SIF missing content hash."})
        rule = self._resolve_rule(ComplianceRule.objects, "wps")
        if rule is None or not rule.is_authoritative:
            issues.append({"code": "no_authoritative_wps_rule", "detail": "No authoritative WPS rule."})

        passed = len(issues) == 0
        filing.validation_passed = passed
        filing.validation_issues = issues
        filing.validated_at = timezone.now()
        filing.status = "validated" if passed else "generated"
        filing.save(
            update_fields=[
                "validation_passed",
                "validation_issues",
                "validated_at",
                "status",
            ]
        )
        return {
            "run_id": run.pk,
            "status": filing.status,
            "passed": passed,
            "issues": issues,
            "content_hash": filing.content_hash,
            "validated_at": filing.validated_at.isoformat() if filing.validated_at else None,
        }

    def wps_submit_filing(self, run, *, user=None):
        """Irreversibly mark a validated WPS filing as submitted (idempotent)."""
        from django.utils import timezone

        from people.governance.sod import (
            ACTION_SUBMIT,
            SUBJECT_WPS_FILING,
            require_distinct_actor,
        )
        from people.models import WpsFiling

        self._require_status(run, ("committed",))
        try:
            filing = run.wps_filing
        except WpsFiling.DoesNotExist as exc:
            raise PayrollServiceError(
                "No WPS filing generated for this run — call generate first."
            ) from exc

        if filing.status == "submitted" and filing.submitted_at:
            return {
                "run_id": run.pk,
                "status": "submitted",
                "receipt_id": filing.receipt_id,
                "submitted_at": filing.submitted_at.isoformat(),
                "reconciled": filing.reconciled,
                "idempotent": True,
            }

        if not filing.validation_passed or filing.status != "validated":
            raise PayrollServiceError(
                "Filing must be validated (passed) before submit."
            )

        require_distinct_actor(
            subject_type=SUBJECT_WPS_FILING,
            subject_id=filing.pk,
            actor=user,
            action=ACTION_SUBMIT,
        )

        now = timezone.now()
        filing.status = "submitted"
        filing.submitted_at = now
        filing.submitted_by = user
        filing.receipt_id = filing.receipt_id or f"WPS-{run.pk}-{now.strftime('%Y%m%d%H%M%S')}"
        filing.reconciled = True
        filing.save(
            update_fields=[
                "status",
                "submitted_at",
                "submitted_by",
                "receipt_id",
                "reconciled",
            ]
        )
        return {
            "run_id": run.pk,
            "status": "submitted",
            "receipt_id": filing.receipt_id,
            "submitted_at": filing.submitted_at.isoformat(),
            "reconciled": filing.reconciled,
            "content_hash": filing.content_hash,
            "idempotent": False,
        }

    @staticmethod
    def _payslip_summary(employee, run, lines):
        """Duck-typed payslip mapping consumed by ``format_wps_record``.

        Exposes employee identifiers plus every payslip line type (gross /
        gosi / loan_installment / net) as its string amount, so a WPS rule's
        ``field_map`` / ``amount_components`` can reference them by name.
        """
        summary = {
            "employee_no": employee.employee_no,
            "employee_name": employee.full_name,
            "basic_salary": str(employee.basic_salary),
            "period_start": str(run.period_start),
            "period_end": str(run.period_end),
        }
        for line in lines:
            code = line.line_type.code if line.line_type_id else str(line.line_type)
            summary[code] = str(line.amount)
        return summary
