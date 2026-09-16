# people/tests/test_loan_status_sync.py
# F17 — correspondence approval/rejection must propagate to the linked Loan
# status so payroll (which filters `employee.loans.filter(status="active")`)
# picks the deduction up in the next cycle.

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from correspondence import fsm
from correspondence.models import Correspondence
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import ComplianceRule, Employee, Loan
from people.tests.ref_helpers import compliance_rule_defaults, ensure_ref


@pytest.fixture
def loan_workflow(db, create_user):
    """Minimal org, loan_request corr_type, requester/approver users and an
    employee — enough to drive the correspondence FSM and exercise the
    correspondence → Loan status sync signal."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    loan_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='loan_request', label='Loan Request',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    requester_user = create_user('loan_sync_requester')
    approver_user = create_user('loan_sync_finance')
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-LOAN-SYNC', full_name='Sync Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        is_active=True,
    )
    # Authoritative loan_schedule rule required for NSR-3A materialization
    # on approve → active.
    ComplianceRule.objects.create(
        rule_id='kw-loan-sync-test',
        version='2026.1',
        name='[TEST ONLY] Loan schedule (status sync)',
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
    return SimpleNamespace(
        org=org, corr_type=loan_type, requester_user=requester_user,
        approver_user=approver_user, employee=employee,
    )


def _make_loan(employee):
    return Loan.objects.create(
        employee=employee,
        loan_type=ensure_ref('loan_type', 'housing'),
        principal=Decimal('5000.000'),
        interest_rate=Decimal('3.500'),
        term_months=12,
        start_date=date(2026, 6, 1),
        status='draft',
    )


def _submitted_correspondence(wf, loan, reference_no):
    """A single-step (finance) correspondence sitting at the actionable step,
    exactly as ``fsm.submit_correspondence`` would leave it."""
    return Correspondence.objects.create(
        corr_type=wf.corr_type,
        subject_type='people.Loan',
        subject_id=loan.pk,
        org_unit=wf.org,
        requester=wf.requester_user,
        title='Loan request housing 5000.000',
        payload={},
        status='submitted',
        reference_no=reference_no,
        current_step=0,
        current_approver_ids=[wf.approver_user.id],
        approver_chain=[
            {
                'order': 0,
                'role': 'finance',
                'intent': 'approve',
                'user_ids': [wf.approver_user.id],
            },
        ],
    )


@pytest.mark.django_db
def test_approve_loan_correspondence_activates_loan(loan_workflow):
    wf = loan_workflow
    loan = _make_loan(wf.employee)
    corr = _submitted_correspondence(wf, loan, 'LOAN-SYNC-APPROVE-1')

    fsm.approve(corr, wf.approver_user)

    corr.refresh_from_db()
    loan.refresh_from_db()
    assert corr.status == 'approved'
    assert loan.status == 'active'


@pytest.mark.django_db
def test_reject_loan_correspondence_cancels_loan(loan_workflow):
    wf = loan_workflow
    loan = _make_loan(wf.employee)
    corr = _submitted_correspondence(wf, loan, 'LOAN-SYNC-REJECT-1')

    fsm.reject(corr, wf.approver_user, 'Insufficient documentation')

    corr.refresh_from_db()
    loan.refresh_from_db()
    assert corr.status == 'rejected'
    assert loan.status == 'cancelled'


@pytest.mark.django_db
def test_approved_correspondence_does_not_resurrect_cancelled_loan(loan_workflow):
    """Guard: the sync is scoped to ``status='draft'``, so a late approval of a
    correspondence cannot reactivate a loan that was already cancelled."""
    wf = loan_workflow
    loan = _make_loan(wf.employee)
    loan.status = 'cancelled'
    loan.save(update_fields=['status'])
    corr = _submitted_correspondence(wf, loan, 'LOAN-SYNC-GUARD-1')

    fsm.approve(corr, wf.approver_user)

    loan.refresh_from_db()
    assert corr.status == 'approved'
    assert loan.status == 'cancelled'
