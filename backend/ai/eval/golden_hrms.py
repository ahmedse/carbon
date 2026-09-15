"""Golden HRMS dataset for deterministic payroll evaluation.

This dataset defines a small KNOWN payroll population for Nibras HRMS checks.
All amounts are Decimal-safe 3dp strings and the arithmetic is explicit:

* HR001: gross 1500.000 - gosi 135.000 - loan_installment 50.000 = net 1315.000
* HR002: gross 2000.000 - gosi 180.000 - loan_installment 125.500 = net 1694.500
* HR003: gross 1234.567 - gosi 111.111 - loan_installment 10.000 = net 1113.456

A fourth employee (HR900) is in a different org unit and is used for
cross-org deny assertions (must not appear in the scoped payroll rows).
"""

from __future__ import annotations


GOLDEN_HRMS_DATASET: dict = {
    "orgs": [
        ("hq", "Nibras HQ"),
        ("remote", "Nibras Remote Unit"),
    ],
    # position key -> (org key, code, title)
    "positions": [
        ("analyst", "hq", "ANL", "Payroll Analyst"),
        ("operator", "hq", "OPR", "Operations Operator"),
        ("remote_analyst", "remote", "RAN", "Remote Analyst"),
    ],
    # employees: exactly three in HQ + one out-of-scope in remote org.
    "employees": [
        {
            "no": "HR001",
            "name": "Amina Saleh",
            "org": "hq",
            "position": "analyst",
            "basic_salary": "1500.000",
            "is_active": True,
        },
        {
            "no": "HR002",
            "name": "Yousef Karim",
            "org": "hq",
            "position": "operator",
            "basic_salary": "2000.000",
            "is_active": True,
        },
        {
            "no": "HR003",
            "name": "Noor Adel",
            "org": "hq",
            "position": "operator",
            "basic_salary": "1234.567",
            "is_active": True,
        },
        {
            "no": "HR900",
            "name": "Layla Remote",
            "org": "remote",
            "position": "remote_analyst",
            "basic_salary": "1800.000",
            "is_active": True,
        },
    ],
    "payroll_run": {
        "org": "hq",
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "status": "committed",
    },
    # Payslip lines are for the single committed HQ run only.
    "payslip_lines": [
        {"employee_no": "HR001", "line_type": "gross", "amount": "1500.000", "rule_id": "kw-gross", "rule_version": "2026.1"},
        {"employee_no": "HR001", "line_type": "gosi", "amount": "135.000", "rule_id": "kw-gosi", "rule_version": "2026.1"},
        {"employee_no": "HR001", "line_type": "loan_installment", "amount": "50.000", "rule_id": "kw-loan", "rule_version": "2026.1"},
        {"employee_no": "HR001", "line_type": "net", "amount": "1315.000", "rule_id": "kw-net", "rule_version": "2026.1"},
        {"employee_no": "HR002", "line_type": "gross", "amount": "2000.000", "rule_id": "kw-gross", "rule_version": "2026.1"},
        {"employee_no": "HR002", "line_type": "gosi", "amount": "180.000", "rule_id": "kw-gosi", "rule_version": "2026.1"},
        {"employee_no": "HR002", "line_type": "loan_installment", "amount": "125.500", "rule_id": "kw-loan", "rule_version": "2026.1"},
        {"employee_no": "HR002", "line_type": "net", "amount": "1694.500", "rule_id": "kw-net", "rule_version": "2026.1"},
        {"employee_no": "HR003", "line_type": "gross", "amount": "1234.567", "rule_id": "kw-gross", "rule_version": "2026.1"},
        {"employee_no": "HR003", "line_type": "gosi", "amount": "111.111", "rule_id": "kw-gosi", "rule_version": "2026.1"},
        {"employee_no": "HR003", "line_type": "loan_installment", "amount": "10.000", "rule_id": "kw-loan", "rule_version": "2026.1"},
        {"employee_no": "HR003", "line_type": "net", "amount": "1113.456", "rule_id": "kw-net", "rule_version": "2026.1"},
    ],
}
