# people/compliance.py
# Registers People-domain evaluators into the Regulations Audit Engine registry.
# Imported by PeopleConfig.ready() — never imported by regulations/ directly.
from regulations.registry import register, BaseEvaluator

from people.kuwaitization import KOC_CONTRACT_ORG_UNITS, quota_for_contract


@register('koc_kuwaitization_quota')
class KuwaitizationQuotaEvaluator(BaseEvaluator):
    """Evaluates KOC Kuwaitization headcount quota per contract.

    One AuditFinding is produced per active KOC contract.
    Status: compliant if actual >= required; non_compliant otherwise.
    Severity escalates to critical when supplied = 0 (full vacancy).
    """

    def get_scope_items(self, run) -> list[tuple[str, int, str]]:
        from mdm.models import ReferenceSet, ReferenceValue
        rs = ReferenceSet.objects.filter(slug='koc-contract').first()
        if rs is None:
            return []
        return [
            ('koc_contract', rv.id, f"{rv.label} (contract {rv.metadata.get('contract_no', '?')})")
            for rv in rs.values.filter(is_active=True).order_by('sort_order')
        ]

    def evaluate(self, scope_type: str, scope_id: int, run) -> dict:
        from mdm.models import ReferenceValue
        from people.models import Employee

        rv = ReferenceValue.objects.get(id=scope_id)
        meta = rv.metadata or {}
        row = quota_for_contract(rv, Employee.objects.all())
        if row['deficit'] <= 0:
            severity_override = self.obligation.severity
        else:
            severity_override = 'critical' if row['actual'] == 0 else self.obligation.severity

        return {
            'status': row['status'],
            'actual': row['actual'],
            'expected': row['required'],
            'delta': row['actual'] - row['required'],
            'contract_no': row['contract_no'],
            'contract_name': row['label'],
            'deficit': row['deficit'],
            'fill_rate_pct': row['fill_rate_pct'],
            'reimbursement': meta.get('reimbursement', {}),
            'severity_override': severity_override,
        }


@register('kll_leave_entitlement')
class LeaveEntitlementEvaluator(BaseEvaluator):
    """Verifies every active employee has a leave entitlement for the audit year.

    Returns one finding per employee missing an entitlement.
    Scope: company-level (summary) or per_employee (detailed).
    """

    def get_scope_items(self, run) -> list[tuple[str, int, str]]:
        # Single company-level scope item
        return [('company', 0, 'GOFSCO (all employees)')]

    def evaluate(self, scope_type: str, scope_id: int, run) -> dict:
        from people.models import Employee, LeaveEntitlement
        year = run.run_date.year
        all_emps = Employee.objects.count()
        with_ent = (
            Employee.objects
            .filter(leave_entitlements__leave_type__code__in=['annual', 'sick'], leave_entitlements__year=year)
            .distinct()
            .count()
        )
        missing = all_emps - with_ent
        status = 'compliant' if missing == 0 else ('non_compliant' if missing > 0 else 'na')
        return {
            'status': status,
            'actual': with_ent,
            'expected': all_emps,
            'delta': with_ent - all_emps,
            'year': year,
            'employees_without_entitlement': missing,
        }
