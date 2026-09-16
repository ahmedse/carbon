# File: people/tests/test_normalize_genders.py
# NSR-7B — Employee.gender is a governed FK; normalize command is a no-op reporter.

from datetime import date

from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from mdm.models import OrgUnit

from people.models import Employee
from people.tests.ref_helpers import ensure_ref


class NormalizeEmployeeGendersTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name="Test Org", slug="test-org")
        self.out = StringIO()

    def _make_employee(self, employee_no, gender=None):
        return Employee.objects.create(
            org_unit=self.org,
            employee_no=employee_no,
            full_name=employee_no,
            basic_salary="1000.000",
            join_date=date(2026, 1, 1),
            gender=gender,
        )

    def test_reports_governed_coverage(self):
        male = ensure_ref("gender", "male")
        self._make_employee("E1", gender=male)
        self._make_employee("E2", gender=None)
        call_command("normalize_employee_genders", stdout=self.out)
        out = self.out.getvalue()
        assert "governed" in out.lower()
        assert "2 employees" in out
        assert "1 set" in out
        assert "1 unset" in out
