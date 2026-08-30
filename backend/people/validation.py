# File: people/validation.py
# Independent DQ validation for the People payroll pipeline (NIR-3D).
#
# Validation is separate from calculation (docs/NIBRAS-MASTER-STRATEGY.md §8.2):
# the calculation engine computes regulated figures; this module independently
# checks them. It consumes the core ``dq`` typed gate (RULE_3-legal: hosted →
# core) and never imports a hosted sibling app (emissions/healthy/accounts/ai).
#
# Two tiers:
#   * validate_write(instance) — Tier-1 field gate over a single model instance
#     via ``dq.typed_gate.check_instances`` (stateless, no DB writes).
#   * validate_run(run)        — Tier-2 batch business rules over a PayrollRun's
#     computed lines; pure read + pure compute (never mutates run.status).
#
# ADR 0025: findings are run-scoped summaries (``PayrollRunValidation`` rows),
# never a per-row persisted result store.
#
# NOTE: this module does NOT import ``payroll_service`` (the service imports this
# module), so finding dicts are built inline in the exact ``make_finding`` shape.

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from dq.typed_gate import check_instances

from .models import ComplianceRule, PayrollRunValidation

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_QUANT = Decimal("0.001")
# Reconciliation tolerance is an engineering choice (amounts are quantized to
# 0.001), not a law value.
_RECON_TOLERANCE = Decimal("0.01")
_MAX_SAMPLE_FAILURES = 20


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


def _finding(rule_key, *, severity, passed, checked, failed, sample_failures):
    """Build a finding dict in the exact shape ``payroll_service.make_finding``
    produces (rule_key / severity / passed / checked / failed / sample_failures)."""
    return {
        "rule_key": rule_key,
        "severity": severity,
        "passed": bool(passed),
        "checked": int(checked),
        "failed": int(failed),
        "sample_failures": [str(s) for s in (sample_failures or [])][:_MAX_SAMPLE_FAILURES],
    }


def _select_band_rate(bands, age):
    """Return the matching band rate for ``age``.

    Mirrors the engine's selector but returns ``None`` instead of raising so
    validation can skip gracefully when no band matches.
    """
    for band in bands:
        max_age = band.get("max_age")
        if max_age is None or age <= _to_decimal(max_age):
            return _to_decimal(band["rate"])
    return None


def validate_write(instance):
    """Tier-1 field gate: run gate-eligible DQ rules bound to ``instance``'s
    model via ``ModelRuleAssignment`` and report whether the write is blocked.

    Pure — never raises, never writes. The caller (API layer, NIR-3E) decides.
    """
    model_label = f"{instance._meta.app_label}.{instance._meta.object_name}"
    result = check_instances(model_label, [instance])
    summary = result.get("summary", {})
    blocked = int(summary.get("blocked", 0)) > 0
    failed = int(summary.get("blocked", 0))
    checked = len(result.get("row_verdicts", []))
    sample_failures = []
    for row_verdict in result.get("row_verdicts", []):
        for failure in row_verdict.get("failures", []):
            sample_failures.append(failure.get("message", ""))
    return {
        "blocked": blocked,
        "checked": checked,
        "failed": failed,
        "sample_failures": sample_failures[:_MAX_SAMPLE_FAILURES],
    }


def validate_run(run):
    """Tier-2 batch: evaluate business rules over a run's computed lines.

    Returns a list of finding dicts (the ``make_finding`` shape). Pure read +
    pure compute — does NOT change ``run.status`` (the service does that).
    """
    lines = list(run.lines.all())
    findings = []

    # (a) net pay must be non-negative
    net_lines = [ln for ln in lines if ln.line_type == "net"]
    if net_lines:
        failures = [
            f"line #{ln.id} employee={ln.employee_id} net={ln.amount}"
            for ln in net_lines
            if ln.amount < Decimal("0")
        ]
        findings.append(_finding(
            "net_positive", severity=SEVERITY_ERROR,
            passed=not failures, checked=len(net_lines),
            failed=len(failures), sample_failures=failures,
        ))

    # (d) every line must carry rule_id + rule_version lineage
    if lines:
        failures = [
            f"line #{ln.id} {ln.line_type}"
            for ln in lines
            if not (ln.rule_id and ln.rule_version)
        ]
        findings.append(_finding(
            "lineage_present", severity=SEVERITY_ERROR,
            passed=not failures, checked=len(lines),
            failed=len(failures), sample_failures=failures,
        ))

    # (b) gross/net reconciliation
    findings.extend(_reconcile_findings(run, lines))

    # (c) GOSI bounds (skipped when no gosi lines or no configured bounds)
    gosi_finding = _gosi_bounds_finding(lines)
    if gosi_finding is not None:
        findings.append(gosi_finding)

    return findings


def _reconcile_findings(run, lines):
    """(b) Σ net == Σ gross − Σ deductions (gosi employee share + loans).

    Reconciliation is only meaningful when both gross and net lines exist; if the
    GOSI employee share cannot be reconstructed from rule params, skip rather
    than fabricate a false failure.
    """
    gross_lines = [ln for ln in lines if ln.line_type == "gross"]
    net_lines = [ln for ln in lines if ln.line_type == "net"]
    if not gross_lines or not net_lines:
        return []

    loan_lines = [ln for ln in lines if ln.line_type == "loan_installment"]
    gosi_lines = [ln for ln in lines if ln.line_type == "gosi"]

    gross_total = sum((ln.amount for ln in gross_lines), Decimal("0"))
    net_total = sum((ln.amount for ln in net_lines), Decimal("0"))
    loan_total = sum((ln.amount for ln in loan_lines), Decimal("0"))

    employee_share_total = Decimal("0")
    for ln in gosi_lines:
        share = _gosi_employee_share(ln)
        if share is None:
            return []
        employee_share_total += share

    deductions = loan_total + employee_share_total
    expected_net = gross_total - deductions
    diff = abs(net_total - expected_net)
    tolerance = _RECON_TOLERANCE * max(1, len(net_lines))

    if diff <= tolerance:
        return [_finding(
            "net_reconciliation", severity=SEVERITY_ERROR,
            passed=True, checked=len(net_lines), failed=0, sample_failures=[],
        )]

    failures = [
        f"gross={gross_total} net={net_total} deductions={deductions} "
        f"expected_net={expected_net} diff={diff}"
    ]
    return [_finding(
        "net_reconciliation", severity=SEVERITY_ERROR,
        passed=False, checked=len(net_lines), failed=1, sample_failures=failures,
    )]


def _gosi_employee_share(gosi_line):
    """Reconstruct the GOSI employee share from the line's inputs + the bound
    gosi ``ComplianceRule`` params. Returns ``None`` when undeterminable.

    All bounds/rates come from rule params — no law constants in code.
    """
    inputs = gosi_line.inputs or {}
    if "employee_share" in inputs:
        return _to_decimal(inputs["employee_share"])

    rule = ComplianceRule.objects.filter(
        rule_id=gosi_line.rule_id, version=gosi_line.rule_version
    ).first()
    if rule is None:
        return None

    params = ((rule.inputs_schema or {}).get("formula") or {}).get("params") or {}
    salary_input = params.get("salary_input", "gross_salary")
    age_input = params.get("age_input", "employee_age")

    salary = _to_decimal(inputs.get(salary_input) or Decimal("0"))
    cap = params.get("cap")
    if cap is not None:
        salary = min(salary, _to_decimal(cap))

    age = _to_decimal(inputs.get(age_input) or Decimal("0"))
    rate = _select_band_rate(params.get("employee_bands") or [], age)
    if rate is None:
        return None
    return (salary * rate).quantize(_QUANT, rounding=ROUND_HALF_UP)


def _gosi_bounds_finding(lines):
    """(c) GOSI within configured bounds (from the gosi rule params).

    Skips (returns None) when there are no gosi lines or no configured bounds —
    bounds are never hardcoded.
    """
    gosi_lines = [ln for ln in lines if ln.line_type == "gosi"]
    if not gosi_lines:
        return None

    rule = ComplianceRule.objects.filter(
        rule_id=gosi_lines[0].rule_id, version=gosi_lines[0].rule_version
    ).first()
    if rule is None:
        rule = ComplianceRule.objects.filter(category="gosi").order_by(
            "-effective_date", "-updated_at"
        ).first()
    if rule is None:
        return None

    params = ((rule.inputs_schema or {}).get("formula") or {}).get("params") or {}
    lo = params.get("min_amount")
    hi = params.get("max_amount")
    if lo is None and hi is None:
        return None

    failures = []
    for ln in gosi_lines:
        if lo is not None and ln.amount < _to_decimal(lo):
            failures.append(f"line #{ln.id} gosi={ln.amount} < min {lo}")
        if hi is not None and ln.amount > _to_decimal(hi):
            failures.append(f"line #{ln.id} gosi={ln.amount} > max {hi}")

    severity = params.get("severity", SEVERITY_WARNING)
    return _finding(
        "gosi_bounds", severity=severity,
        passed=not failures, checked=len(gosi_lines),
        failed=len(failures), sample_failures=failures,
    )


def persist_findings(run, findings):
    """Persist run-scoped summaries — one ``PayrollRunValidation`` per finding.

    ADR 0025: never a per-row result store (no ``DQResult`` rows). Only this
    function writes, and only when explicitly called.
    """
    created = []
    for finding in (findings or []):
        created.append(PayrollRunValidation.objects.create(
            payroll_run=run,
            rule_key=finding["rule_key"],
            passed=finding["passed"],
            checked=finding.get("checked", 0),
            failed=finding.get("failed", 0),
            sample_failures=list(finding.get("sample_failures", [])),
        ))
    return created
