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
# ADR 0029: gross is resolved from verified monthly earnings on the compensation
# ledger (basic required; housing/transport/etc. fold into the package), never
# from ``Employee.basic_salary``. A missing verified basic, a missing join date
# on a gated leave line, or a six-month gate holds that employee only. Everyone
# else is still computed. GOSI withholding applies to Kuwaiti nationals only.
#
# ADR 0025 lineage seam: any payslip line derived from a governed measurement
# (an AttendanceRecord backed by a dataschema.DataRow) carries ``data_row_id`` /
# ``row_hash`` inside its ``inputs``.

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import calculation_engine
from .compensation_service import CompensationService
from .associated_pay import priced_lines
from .calculation_engine import MissingPolicyFactError
from .models import AttendanceRecord, ComplianceRule, Employee, LieuDay, PayrollRun, PayslipLine

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


class PayrollServiceError(Exception):
    """Raised when a payroll run is asked to perform an illegal transition."""

    def __init__(self, message, *, code="payroll_refused"):
        super().__init__(message)
        self.code = code


ACTIVE_PERIOD_STATUSES = ("draft", "computed", "validated", "committed")


def loan_within_policy(rule, wage, amount) -> bool:
    """True when no cap is declared, or the installment is within it.

    The fraction is rule data. This does not recompute the installment.
    """
    if rule is None:
        return True
    params = ((rule.inputs_schema or {}).get("formula") or {}).get("params") or {}
    raw = params.get("max_wage_fraction")
    if raw is None:
        return True
    cap = (Decimal(str(wage)) * Decimal(str(raw))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return Decimal(str(amount)) <= cap


def _refuse_loan_above_policy(rule, wage, amount):
    if loan_within_policy(rule, wage, amount):
        return
    raise PayrollServiceError(
        "Loan deduction exceeds the published wage fraction. "
        "The installment schedule was not rewritten."
    )


def _named_exception(employee, reason, *, detail=""):
    """One employee held on the run. The company compute continues."""
    return {
        "employee_no": employee.employee_no,
        "full_name": employee.full_name,
        "reason": reason,
        "detail": detail,
    }


def _dedupe_exceptions(rows):
    seen = set()
    unique = []
    for row in rows:
        key = (row.get("employee_no"), row.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _fact_window(run):
    """Period whose facts a run prices. A retro keeps its own identity and reads the source period."""
    if getattr(run, "kind", "regular") == "retro" and run.covers_start and run.covers_end:
        return run.covers_start, run.covers_end
    return run.period_start, run.period_end


def assert_unique_active_period(org_unit, period_start, period_end, *, exclude_pk=None):
    """Refuse a second active run for the same org unit and period.

    Failed runs may be superseded. The database enforces the same rule for
    draft, computed, validated, and committed runs. Existing duplicate
    committed rows are not rewritten by this check.
    """
    qs = PayrollRun.objects.filter(
        org_unit=org_unit,
        period_start=period_start,
        period_end=period_end,
        status__in=ACTIVE_PERIOD_STATUSES,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    other = qs.order_by("pk").first()
    if other is not None:
        raise PayrollServiceError(
            f"An active payroll run already exists for this organization and "
            f"period (run #{other.pk}, status={other.status})."
        )


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
        """Employees whose org_unit is the run's org_unit or a descendant.

        Skip people who joined after the period ends — they have no pay due.
        Null ``join_date`` (bulk ERP) stays included.
        """
        ids = run.org_unit.get_descendant_ids(include_self=True)
        cutoff = run.covers_end or run.period_end
        return Employee.objects.filter(org_unit_id__in=ids).filter(
            Q(join_date__isnull=True) | Q(join_date__lte=cutoff),
        )

    # --- compute -----------------------------------------------------------

    def compute(self, run, *, user=None):
        self._require_status(run, self.ALLOWED_TRANSITIONS["compute"])
        assert_unique_active_period(
            run.org_unit, run.period_start, run.period_end, exclude_pk=run.pk,
        )

        rules = ComplianceRule.objects
        as_of = run.period_end
        gosi_rule = self._resolve_rule(rules, "gosi", as_of=as_of)
        loan_rule = self._resolve_rule(rules, "other", formula_type="loan_schedule", as_of=as_of)
        net_rule = self._resolve_rule(rules, "other", formula_type="net_pay", as_of=as_of)

        employees = list(self._scoped_employees(run))
        with transaction.atomic():
            LieuDay.objects.filter(payroll_run=run).delete()
            run.lines.all().delete()
            lines_created = 0
            exceptions: list[dict] = []
            for employee in employees:
                created, holds = self._compute_employee(
                    run, employee, gosi_rule, loan_rule, net_rule, as_of=as_of,
                )
                lines_created += created
                exceptions.extend(holds)
            run.exceptions = _dedupe_exceptions(exceptions)
            run.status = "computed"
            run.save(update_fields=["status", "exceptions"])
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
            "exceptions": list(run.exceptions or []),
        }

    def _compute_employee(self, run, employee, gosi_rule, loan_rule, net_rule, *, as_of=None):
        rules = ComplianceRule.objects
        created = 0
        holds: list[dict] = []

        # 1. gross — verified monthly earnings from the ledger (ADR-0029).
        # ``basic`` is required; housing/transport/etc. fold into the package
        # passed to the gross sum rule (which names the ``basic`` input).
        window_start, window_end = _fact_window(run)
        package = self._verified_earnings_package(employee, as_of=window_end)
        if package is None:
            return 0, [_named_exception(
                employee,
                "missing verified basic",
                detail=(
                    f"Employee {employee.employee_no} has no verified monthly "
                    f"'basic' compensation ledger line for period ending "
                    f"{run.period_end}; refusing to compute payroll from "
                    f"Employee.basic_salary."
                ),
            )]
        measurements = self._attendance_measurements(employee, run)
        gross_inputs = {
            "basic": package,
            "basic_source": "ledger",
        }
        if measurements:
            gross_inputs["measurements"] = measurements
            if len(measurements) == 1:
                gross_inputs["data_row_id"] = measurements[0]["data_row_id"]
                gross_inputs["row_hash"] = measurements[0]["row_hash"]
        gross = calculation_engine.calculate_gross_pay(
            employee, gross_inputs, rules, as_of=as_of or run.period_end,
        )
        self._line_from_result(run, employee, "gross", gross)
        created += 1

        # 2. GOSI — Kuwaiti nationals only (PIFSS). Expatriates: EOSI/gratuity,
        # not monthly social-security withholding.
        employee_share = Decimal("0")
        if getattr(employee, "kuwaitization", False) and gosi_rule is not None:
            gosi = calculation_engine.calculate_gosi(gosi_rule, gross["value"])
            self._line_from_result(run, employee, "gosi", gosi)
            created += 1
            employee_share = gosi["lineage"].get("employee_share", Decimal("0"))

        # 3. Associated pay (leave, absence, overtime, sick, notice, encashment).
        #    Posted only when an authoritative rule names a payslip line and the
        #    employee has the fact. Earnings increase net; deductions reduce it.
        basic_amount = CompensationService.verified_basic_amount(employee, as_of=window_end)
        line_holds: list[dict] = []
        try:
            associated = priced_lines(
                employee, window_start, window_end, package, basic_amount,
                rule_as_of=as_of or run.period_end,
                holds=line_holds,
            )
        except MissingPolicyFactError as exc:
            raise PayrollServiceError(
                f"Employee {employee.employee_no} is missing fact '{exc.fact}'.",
                code="missing_fact",
            ) from exc
        for item in line_holds:
            holds.append(_named_exception(
                employee, item["reason"], detail=item.get("detail") or "",
            ))
        associated_earnings = Decimal("0")
        associated_deductions = []
        for item in associated:
            line = self._line_from_result(
                run, employee, item["line_code"], item, effect=item.get("effect"),
            )
            created += 1
            days = item["lineage"].get("compensatory_days")
            if days not in (None, "", 0, "0"):
                LieuDay.objects.create(
                    employee=employee,
                    payroll_run=run,
                    payslip_line=line,
                    days=Decimal(str(days)),
                    rule_id=item["lineage"]["rule_id"],
                    rule_version=item["lineage"]["rule_version"],
                    earned_on=window_end,
                )
            if item.get("effect") == "deduction":
                associated_deductions.append(item["value"])
            else:
                associated_earnings += Decimal(str(item["value"]))

        # 4. loan installments due this period.
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
            _refuse_loan_above_policy(loan_rule, gross["value"], installment["amount"])
            self._loan_line(run, employee, schedule, installment, loan_rule)
            created += 1
            deductions.append(installment["amount"])

        # 5. net = package + associated earnings − (GOSI share + loans + associated deductions).
        deductions.extend(associated_deductions)
        net = calculation_engine.calculate_net_pay(
            net_rule, Decimal(str(gross["value"])) + associated_earnings, deductions,
        )
        net["lineage"]["inputs"]["package_gross"] = gross["value"]
        net["lineage"]["inputs"]["associated_earnings"] = associated_earnings
        self._line_from_result(run, employee, "net", net)
        created += 1

        return created, holds

    @staticmethod
    def _verified_earnings_package(employee, *, as_of) -> Decimal | None:
        """Sum of verified monthly earning lines as of ``as_of``.

        ``basic`` must be present (ADR-0029). Other verified monthly earnings
        (housing, transport, …) are included so gross reflects the full package.
        When multiple overlapping ``basic`` rows exist, the newest wins for the
        basic component; other components take their current line.
        """
        basic = CompensationService.verified_basic_amount(employee, as_of=as_of)
        if basic is None:
            return None
        total = Decimal(basic)
        extras = (
            CompensationService.current_lines(employee, as_of=as_of)
            .filter(
                component__direction="earning",
                frequency="monthly",
                is_verified=True,
            )
            .exclude(component__code="basic")
            .select_related("component")
        )
        # One amount per component code (newest open line).
        seen: set[str] = set()
        for line in extras.order_by("-effective_start", "-pk"):
            code = line.component.code
            if code in seen:
                continue
            seen.add(code)
            total += Decimal(line.amount)
        return total

    # --- line writers ------------------------------------------------------

    def _line_from_result(self, run, employee, line_type, result, *, effect=None):
        lineage = result["lineage"]
        inputs = dict(lineage.get("inputs") or {})
        for key in (
            "regulation_rule_id",
            "regulation_pack",
            "regulation_version",
            "employee_share",
            "employer_share",
            "compensatory_days",
        ):
            if key in lineage and key not in inputs:
                inputs[key] = lineage[key]
        if effect:
            inputs["effect"] = effect
        return self._create_line(
            run, employee, line_type, result["value"],
            lineage["rule_id"], lineage["rule_version"], inputs,
        )

    def _loan_line(self, run, employee, schedule, installment, loan_rule=None):
        lineage = schedule["lineage"]
        inputs = dict(lineage["inputs"])
        inputs["installment_no"] = installment["installment_no"]
        inputs["principal_portion"] = str(installment["principal_portion"])
        inputs["interest_portion"] = str(installment["interest_portion"])
        if loan_rule is not None:
            ref = (loan_rule.inputs_schema or {}).get("regulation_ref") or {}
            if ref.get("rule_id") and ref.get("version"):
                inputs["regulation_rule_id"] = ref["rule_id"]
                inputs["regulation_version"] = str(ref["version"])
        self._create_line(
            run, employee, "loan_installment", installment["amount"],
            lineage["rule_id"], lineage["rule_version"], inputs,
        )

    def _create_line(self, run, employee, line_type, amount, rule_id, rule_version, inputs):
        if isinstance(line_type, str):
            line_type = _payslip_line_type(line_type)
        return PayslipLine.objects.create(
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
    def _resolve_rule(rules, category, formula_type=None, *, as_of=None):
        """Return the authoritative rule in effect on ``as_of``.

        Regulated payroll figures (GOSI, loan schedule, net pay) may only be
        computed from authoritative rules — the same contract the calculation
        engine's ``_guard`` enforces. Non-authoritative demo/test rows are
        skipped so they can never be selected for a live payroll run.

        When ``as_of`` is set, a version whose effective date is after the
        period end is not eligible. The latest remaining effective date wins.
        Omitting ``as_of`` keeps the previous latest-authoritative pick.
        """
        qs = rules.filter(category__code=category, is_authoritative=True)
        if as_of is not None:
            qs = qs.filter(effective_date__lte=as_of)
        qs = qs.order_by("-effective_date", "-updated_at")
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
        from people.governance.sod import (
            ACTION_COMMIT,
            SUBJECT_PAYROLL_RUN,
            require_distinct_actor,
        )

        with transaction.atomic():
            locked = PayrollRun.objects.select_for_update().get(pk=run.pk)
            if locked.status == "committed":
                return {
                    "run": locked.pk,
                    "status": "committed",
                    "idempotent": True,
                    "has_errors": False,
                }
            self._require_status(locked, self.ALLOWED_TRANSITIONS["commit"])
            require_distinct_actor(
                subject_type=SUBJECT_PAYROLL_RUN,
                subject_id=locked.pk,
                actor=user,
                action=ACTION_COMMIT,
            )
            result = self._run_validation(locked)
            if result["has_errors"]:
                locked.status = "failed"
                locked.save(update_fields=["status"])
                result["run"] = locked.pk
                result["status"] = locked.status
                result["idempotent"] = False
                return result
            locked.status = "committed"
            locked.committed_at = timezone.now()
            locked.save(update_fields=["status", "committed_at"])
            result["run"] = locked.pk
            result["status"] = locked.status
            result["idempotent"] = False
            return result

    def open_retro(self, source, *, period_start, period_end, user=None):
        """Open an off-cycle run tied to a committed period.

        The retro has its own period dates, so ``people_payrollrun_one_active_period``
        still refuses a second run on the source period. The caller does not
        pick a rule version; compute resolves the authoritative rules then.
        ``user`` is unused until compute stamps the preparer on this new run.
        """
        del user
        if source.status != "committed":
            raise PayrollServiceError(
                "A retro run can only be opened from a committed payroll run.",
                code="retro_source_not_committed",
            )
        assert_unique_active_period(source.org_unit, period_start, period_end)
        return PayrollRun.objects.create(
            org_unit=source.org_unit,
            period_start=period_start,
            period_end=period_end,
            kind="retro",
            source_run=source,
            covers_start=source.period_start,
            covers_end=source.period_end,
            status="draft",
        )

    def _run_validation(self, run):
        findings = list(self.validation_seam.validate_run(run))
        holds = list(run.exceptions or [])
        if holds:
            findings.append(make_finding(
                "employee_hold",
                severity=SEVERITY_WARNING,
                passed=False,
                checked=len(holds),
                failed=len(holds),
                sample_failures=[
                    f"{row.get('employee_no')} {row.get('full_name')}: {row.get('reason')}"
                    + (f" ({row.get('detail')})" if row.get("detail") else "")
                    for row in holds
                ],
            ))
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
                "receipt_kind": "local_export",
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
        # Local Carbon export id — not a PAM/bank acknowledgement (NR-WPS-02).
        filing.receipt_id = filing.receipt_id or f"LOCAL-WPS-{run.pk}-{now.strftime('%Y%m%d%H%M%S')}"
        filing.reconciled = False
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
            "receipt_kind": "local_export",
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
