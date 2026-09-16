# people/tests/conftest.py — NSR-7B governed-ref helpers for the people suite.

import pytest

from people.tests.ref_helpers import compliance_rule_defaults, ensure_ref


@pytest.fixture
def ref(db):
    """Factory: ``ref('loan_type', 'personal')`` → ReferenceValue."""
    return ensure_ref


@pytest.fixture
def compliance_defaults(db):
    return compliance_rule_defaults


@pytest.fixture(autouse=True)
def _seed_payslip_line_types(db):
    """Ensure payslip_line_type codes used by payroll_service exist in every test."""
    from people import payroll_service
    payroll_service._line_type_cache.clear()
    for code in (
        'gross', 'basic', 'overtime', 'leave_pay', 'eosi_accrual',
        'gosi', 'wps', 'deduction', 'net', 'loan_installment',
    ):
        ensure_ref('payslip_line_type', code)
