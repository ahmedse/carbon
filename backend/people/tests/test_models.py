# File: people/tests/test_models.py
# Model instantiation + constraint regression tests for the NIR-3A models.

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from mdm.models import OrgUnit

from people.models import (
    AttendancePermission,
    AttendanceRecord,
    BenefitType,
    Certification,
    Employee,
    EmployeeBenefit,
    LeaveEntitlement,
    LeaveRecord,
    Loan,
    LoanInstallment,
    Position,
    RotationSchedule,
)


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='Test Org', slug='test-org')


@pytest.fixture
def employee(org):
    return Employee.objects.create(
        org_unit=org,
        employee_no='E-TEST',
        full_name='Test Employee',
        basic_salary='1000.000',
        join_date=date(2026, 1, 1),
    )


# ── (a) instantiation + __str__ ─────────────────────────────────────────────

@pytest.mark.django_db
def test_position_str(org):
    pos = Position.objects.create(org_unit=org, code='P-1', title='Manager')
    assert str(pos) == 'P-1 — Manager'


@pytest.mark.django_db
def test_leave_entitlement_str(employee):
    ent = LeaveEntitlement.objects.create(
        employee=employee, year=2026, leave_type='annual', entitled_days='30.00',
    )
    assert str(ent) == 'E-TEST — Test Employee 2026 annual (30.00 days)'


@pytest.mark.django_db
def test_leave_record_str(employee):
    rec = LeaveRecord.objects.create(
        employee=employee, leave_type='annual',
        start_date=date(2026, 3, 1), end_date=date(2026, 3, 5), days='5.00',
    )
    assert str(rec) == 'E-TEST — Test Employee annual 2026-03-01→2026-03-05 (draft)'


@pytest.mark.django_db
def test_benefit_type_str():
    bt = BenefitType.objects.create(code='housing', name='Housing Allowance', category='accommodation')
    assert str(bt) == 'housing — Housing Allowance'


@pytest.mark.django_db
def test_employee_benefit_str(employee):
    bt = BenefitType.objects.create(code='housing', name='Housing Allowance', category='accommodation')
    eb = EmployeeBenefit.objects.create(
        employee=employee, benefit_type=bt, monthly_amount='500.000',
        effective_start=date(2026, 1, 1),
    )
    assert str(eb) == 'E-TEST — Test Employee — housing — Housing Allowance'


@pytest.mark.django_db
def test_loan_str(employee):
    loan = Loan.objects.create(
        employee=employee, loan_type='personal', principal='5000.000',
        term_months=24, start_date=date(2026, 1, 1),
    )
    assert str(loan) == 'E-TEST — Test Employee personal (5000.000)'


@pytest.mark.django_db
def test_loan_installment_str(employee):
    loan = Loan.objects.create(
        employee=employee, loan_type='personal', principal='5000.000',
        term_months=24, start_date=date(2026, 1, 1),
    )
    inst = LoanInstallment.objects.create(
        loan=loan, installment_no=1, due_date=date(2026, 2, 1),
        amount='100.000', principal_portion='90.000', interest_portion='10.000',
    )
    assert str(inst) == 'E-TEST — Test Employee personal (5000.000) #1 (100.000)'


@pytest.mark.django_db
def test_attendance_record_str(employee):
    rec = AttendanceRecord.objects.create(
        employee=employee, date=date(2026, 1, 1), status='present',
    )
    assert str(rec) == 'E-TEST — Test Employee 2026-01-01 (present)'


@pytest.mark.django_db
def test_attendance_permission_str(employee):
    perm = AttendancePermission.objects.create(
        employee=employee, date=date(2026, 1, 2), permission_type='exit', hours='2.00',
    )
    assert str(perm) == 'E-TEST — Test Employee 2026-01-02 exit (2.00h)'


@pytest.mark.django_db
def test_certification_str(employee):
    cert = Certification.objects.create(
        employee=employee, cert_type='KOC-PTW', number='C-123',
    )
    assert str(cert) == 'E-TEST — Test Employee KOC-PTW (C-123)'


@pytest.mark.django_db
def test_rotation_schedule_str(employee):
    rs = RotationSchedule.objects.create(
        employee=employee, pattern='1/1', start_date=date(2026, 1, 1),
    )
    assert str(rs) == 'E-TEST — Test Employee 1/1 (2026-01-01)'


# ── (b) unique_together constraints ─────────────────────────────────────────

@pytest.mark.django_db
def test_leave_entitlement_unique_together(employee):
    LeaveEntitlement.objects.create(
        employee=employee, year=2026, leave_type='annual', entitled_days='30.00',
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LeaveEntitlement.objects.create(
                employee=employee, year=2026, leave_type='annual', entitled_days='31.00',
            )


@pytest.mark.django_db
def test_loan_installment_unique_together(employee):
    loan = Loan.objects.create(
        employee=employee, loan_type='personal', principal='5000.000',
        term_months=24, start_date=date(2026, 1, 1),
    )
    LoanInstallment.objects.create(
        loan=loan, installment_no=1, due_date=date(2026, 2, 1),
        amount='100.000', principal_portion='90.000', interest_portion='10.000',
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LoanInstallment.objects.create(
                loan=loan, installment_no=1, due_date=date(2026, 2, 1),
                amount='100.000', principal_portion='90.000', interest_portion='10.000',
            )


@pytest.mark.django_db
def test_attendance_unique_together(employee):
    AttendanceRecord.objects.create(
        employee=employee, date=date(2026, 1, 1), status='present',
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AttendanceRecord.objects.create(
                employee=employee, date=date(2026, 1, 1), status='absent',
            )


# ── (c) Position.reports_to self-FK ────────────────────────────────────────

@pytest.mark.django_db
def test_position_reports_to_self_fk(org):
    manager = Position.objects.create(org_unit=org, code='MGR', title='Manager')
    report = Position.objects.create(
        org_unit=org, code='ENG', title='Engineer', reports_to=manager,
    )
    assert report.reports_to == manager
    assert list(manager.direct_reports.all()) == [report]


# ── (d) FK resolution ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_employee_benefit_fks(employee):
    bt = BenefitType.objects.create(code='housing', name='Housing Allowance', category='accommodation')
    eb = EmployeeBenefit.objects.create(
        employee=employee, benefit_type=bt, monthly_amount='500.000',
        effective_start=date(2026, 1, 1),
    )
    assert eb.employee == employee
    assert eb.benefit_type == bt
    assert list(employee.benefits.all()) == [eb]
    assert list(bt.employee_benefits.all()) == [eb]


@pytest.mark.django_db
def test_loan_fk(employee):
    loan = Loan.objects.create(
        employee=employee, loan_type='personal', principal='5000.000',
        term_months=24, start_date=date(2026, 1, 1),
    )
    assert loan.employee == employee
    assert list(employee.loans.all()) == [loan]


@pytest.mark.django_db
def test_leave_record_fk(employee):
    rec = LeaveRecord.objects.create(
        employee=employee, leave_type='annual',
        start_date=date(2026, 3, 1), end_date=date(2026, 3, 5), days='5.00',
    )
    assert rec.employee == employee
    assert list(employee.leave_records.all()) == [rec]


# ── (e) RotationSchedule.config defaults to {} ─────────────────────────────

@pytest.mark.django_db
def test_rotation_schedule_config_defaults_to_empty_dict(employee):
    rs = RotationSchedule.objects.create(
        employee=employee, pattern='1/1', start_date=date(2026, 1, 1),
    )
    assert rs.config == {}
