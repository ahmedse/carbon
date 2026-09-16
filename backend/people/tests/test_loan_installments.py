# people/tests/test_loan_installments.py
# NSR-3A — approve materializes LoanInstallment rows; re-sync is idempotent;
# payroll prefers persisted rows when present.

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from correspondence import fsm
from correspondence.models import Correspondence
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.loan_service import materialize_loan_installments
from people.models import (
    CompensationComponent,
    ComplianceRule,
    Employee,
    EmployeeCompensation,
    Loan,
    LoanInstallment,
    PayslipLine,
    PayrollRun,
)
from people.payroll_service import PayrollRunService
from people.tests.ref_helpers import compliance_rule_defaults, ensure_ref


def _loan_rule(**overrides):
    defaults = dict(
        rule_id='kw-loan-inst-test',
        version='2026.1',
        name='[TEST ONLY] Loan schedule (installments)',
        category=ensure_ref('compliance_category', 'other'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            'inputs': ['principal', 'interest_rate', 'term_months'],
            'formula': {
                'type': 'loan_schedule',
                'params': {
                    'method': 'flat',
                    'rate_is_annual': True,
                    'rate_is_percent': False,
                },
            },
        },
        is_authoritative=True,
    )
    defaults.update(overrides)
    return ComplianceRule.objects.create(**defaults)


def _gross_gosi_net_rules():
    ComplianceRule.objects.create(
        rule_id='kw-gross-inst-test',
        version='2026.1',
        name='[TEST ONLY] Gross',
        category=ensure_ref('compliance_category', 'payroll'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            'inputs': ['basic'],
            'formula': {
                'type': 'sum',
                'params': {'components': ['basic'], 'base_input': 'basic'},
            },
        },
        is_authoritative=True,
    )
    ComplianceRule.objects.create(
        rule_id='kw-gosi-inst-test',
        version='2026.1',
        name='[TEST ONLY] GOSI',
        category=ensure_ref('compliance_category', 'gosi'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            'inputs': ['gross_salary', 'employee_age'],
            'formula': {
                'type': 'gosi',
                'params': {
                    'employee_bands': [{'max_age': None, 'rate': '0.10'}],
                    'employer_bands': [{'max_age': None, 'rate': '0.10'}],
                },
            },
        },
        is_authoritative=True,
    )
    ComplianceRule.objects.create(
        rule_id='kw-netpay-inst-test',
        version='2026.1',
        name='[TEST ONLY] Net',
        category=ensure_ref('compliance_category', 'other'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            'inputs': ['gross', 'deductions'],
            'formula': {'type': 'net_pay', 'params': {}},
        },
        is_authoritative=True,
    )


def _verified_basic(employee, amount=Decimal('1000.000')):
    component, _ = CompensationComponent.objects.get_or_create(
        code='basic',
        defaults={
            'name': 'Basic Salary',
            'direction': 'earning',
            'is_wps_relevant': True,
            'sort_order': 10,
            'is_active': True,
        },
    )
    return EmployeeCompensation.objects.create(
        employee=employee,
        component=component,
        amount=amount,
        frequency='monthly',
        effective_start=date(2024, 1, 1),
        is_verified=True,
    )


@pytest.fixture
def loan_installment_ctx(db, create_user):
    _loan_rule()
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type-loan-inst',
    )
    loan_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='loan_request', label='Loan Request',
    )
    org = OrgUnit.objects.create(
        name='Finance', slug='finance-loan-inst', code='FIN-LI', org_type='department',
    )
    requester = create_user('loan_inst_requester')
    approver = create_user('loan_inst_finance')
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-LOAN-INST', full_name='Installment Emp',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester,
        is_active=True,
    )
    return SimpleNamespace(
        org=org, corr_type=loan_type, requester=requester,
        approver=approver, employee=employee,
    )


def _draft_loan(employee, *, term_months=6, principal='600.000', start=None):
    return Loan.objects.create(
        employee=employee,
        loan_type=ensure_ref('loan_type', 'advance'),
        principal=Decimal(principal),
        interest_rate=Decimal('0'),
        term_months=term_months,
        start_date=start or date(2026, 8, 1),
        status='draft',
    )


def _submitted_corr(ctx, loan, reference_no):
    return Correspondence.objects.create(
        corr_type=ctx.corr_type,
        subject_type='people.Loan',
        subject_id=loan.pk,
        org_unit=ctx.org,
        requester=ctx.requester,
        title=f'Loan {loan.principal}',
        payload={},
        status='submitted',
        reference_no=reference_no,
        current_step=0,
        current_approver_ids=[ctx.approver.id],
        approver_chain=[{
            'order': 0,
            'role': 'finance',
            'intent': 'approve',
            'user_ids': [ctx.approver.id],
        }],
    )


@pytest.mark.django_db
def test_approve_creates_n_installment_rows(loan_installment_ctx):
    ctx = loan_installment_ctx
    term = 6
    loan = _draft_loan(ctx.employee, term_months=term, principal='600.000')
    corr = _submitted_corr(ctx, loan, 'LOAN-INST-APPROVE-1')

    fsm.approve(corr, ctx.approver)

    loan.refresh_from_db()
    assert loan.status == 'active'
    rows = list(loan.installments.order_by('installment_no'))
    assert len(rows) == term
    assert [r.installment_no for r in rows] == list(range(1, term + 1))
    assert all(r.status == 'scheduled' for r in rows)
    assert rows[0].due_date == date(2026, 8, 1)
    assert rows[1].due_date == date(2026, 9, 1)
    # flat zero-interest → equal principal portions of 100.000
    assert rows[0].amount == Decimal('100.000')
    assert sum((r.amount for r in rows), Decimal('0')) == Decimal('600.000')


@pytest.mark.django_db
def test_reapprove_sync_does_not_duplicate_installments(loan_installment_ctx):
    ctx = loan_installment_ctx
    loan = _draft_loan(ctx.employee, term_months=4, principal='400.000')
    corr = _submitted_corr(ctx, loan, 'LOAN-INST-IDEM-1')

    fsm.approve(corr, ctx.approver)
    assert loan.installments.count() == 4

    # Re-save approved correspondence (signal fires again) + explicit rematerialize.
    corr.save()
    again = materialize_loan_installments(loan)
    assert loan.installments.count() == 4
    assert len(again) == 4
    assert LoanInstallment.objects.filter(loan=loan).count() == 4


@pytest.mark.django_db
def test_payroll_uses_persisted_installment_when_present(loan_installment_ctx):
    ctx = loan_installment_ctx
    _gross_gosi_net_rules()
    _verified_basic(ctx.employee)

    loan = _draft_loan(ctx.employee, term_months=12, principal='1200.000')
    corr = _submitted_corr(ctx, loan, 'LOAN-INST-PAY-1')
    fsm.approve(corr, ctx.approver)
    loan.refresh_from_db()

    # Tamper the persisted Aug row so a pure engine recompute would still be
    # 100.000 — payroll must prefer the persisted amount.
    aug = loan.installments.get(installment_no=1)
    aug.amount = Decimal('77.000')
    aug.principal_portion = Decimal('77.000')
    aug.interest_portion = Decimal('0')
    aug.save(update_fields=['amount', 'principal_portion', 'interest_portion'])

    run = PayrollRun.objects.create(
        org_unit=ctx.org,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    PayrollRunService().compute(run)

    loan_line = PayslipLine.objects.get(
        employee=ctx.employee, line_type=ensure_ref('payslip_line_type', 'loan_installment'),
    )
    assert loan_line.amount == Decimal('77.000')
    assert loan_line.inputs.get('source') == 'persisted_loan_installment'
    assert loan_line.inputs.get('loan_installment_id') == aug.pk


@pytest.mark.django_db
def test_payroll_falls_back_to_engine_when_no_rows(loan_installment_ctx):
    """Active loan with no materialized rows still deducts via engine schedule."""
    ctx = loan_installment_ctx
    _gross_gosi_net_rules()
    _verified_basic(ctx.employee)

    Loan.objects.create(
        employee=ctx.employee,
        loan_type=ensure_ref('loan_type', 'advance'),
        principal=Decimal('1200.000'),
        interest_rate=Decimal('0'),
        term_months=12,
        start_date=date(2026, 8, 1),
        status='active',
    )
    assert LoanInstallment.objects.filter(loan__employee=ctx.employee).count() == 0

    run = PayrollRun.objects.create(
        org_unit=ctx.org,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    PayrollRunService().compute(run)

    loan_line = PayslipLine.objects.get(
        employee=ctx.employee, line_type=ensure_ref('payslip_line_type', 'loan_installment'),
    )
    assert loan_line.amount == Decimal('100.000')
    assert 'source' not in (loan_line.inputs or {}) or \
        loan_line.inputs.get('source') != 'persisted_loan_installment'
